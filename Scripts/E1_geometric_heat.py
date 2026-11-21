"""E1 - Geometric workloads as a heat source.

Four questions, answered in order:

  E1.1  What do the furnace-tier computations look like?
        The covariant (Laplace-Beltrami) operator is built on curved surfaces
        and its spectrum, heat kernel and spectral transforms are computed.
        The geometry is validated against the exact spectrum of the sphere.
  E1.2  Do they produce the heat that is needed?
        Each kernel's arithmetic intensity places it on the roofline of a
        reference accelerator (NVIDIA H100 SXM). Compute-bound kernels hold
        the chip at its power cap: every watt drawn leaves as heat.
  E1.3  How much heat can a chip carry before it fails?
        Junction temperature and leakage are coupled: leakage rises with
        temperature and temperature rises with power. The model finds, for
        each coolant temperature, the largest heat a chip can carry before
        exceeding its junction limit or entering thermal runaway, for
        silicon, silicon carbide, gallium nitride and diamond.
  E1.4  How much heat can the public geometric dataset produce?
        Floating-point work is counted for public geometry corpora at
        increasing depth of computation and converted to furnace energy.

Machine-dependent timings are reported for information only; every check is
on a quantity that does not depend on the machine.

Run:  python3 -I Scripts/E1_geometric_heat.py
"""
import os
import sys
import time
import math

import numpy as np
import scipy.sparse as sp
import scipy.linalg as sla
import scipy.sparse.linalg as spla

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from conventions import Verdicts, IT_POWER_MW, HOURS_PER_YEAR, K0  # noqa: E402
from registry import v  # noqa: E402

# ---------------------------------------------- reference accelerator (registry)
H100_FP64_TC = v("h100_fp64_tc")
H100_BW = v("h100_bw")
H100_TDP = v("h100_tdp")
H100_DIE_CM2 = v("h100_die_cm2")
SUSTAINED = v("sustained")                  # TOP500 H100 Rmax / Rpeak

# ---------------------------------------------- thermal model (registry)
K_B = v("k_B_eV")
R_TH = v("rth")
LEAK_FRAC_REF = v("leak_frac")
T_POST = v("post_t_low")                    # the originating post's coolant temperature
COOLANT_SCAN = (40.0, 120.0)                # extra table rows (output grid), degC
T_REF_K = K0 + v("t_base_junction")
MATERIALS = [                               # name, bandgap eV, junction limit degC
    ("Si", v("eg_si"), v("tj_max_si")),
    ("SiC (4H)", v("eg_sic"), v("tj_max_sic")),
]

# ---------------------------------------------- public geometry corpora (registry)
CORPORA = [
    ("ABC CAD dataset", v("n_abc")),
    ("ShapeNetCore", v("n_shapenet")),
    ("Thingi10K", v("n_thingi")),
    ("Protein Data Bank (molecular surfaces)", v("n_pdb")),
]


# ================================================================ geometry
def icosphere(level):
    t = (1.0 + 5 ** 0.5) / 2.0
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
         (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9),
         (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2),
         (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
         (8, 6, 7), (9, 8, 1)]
    verts = [np.array(p, float) / np.linalg.norm(p) for p in v]
    faces = list(f)
    for _ in range(level):
        cache = {}

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                m = verts[a] + verts[b]
                verts.append(m / np.linalg.norm(m))
                cache[key] = len(verts) - 1
            return cache[key]
        new = []
        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            new += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = new
    return np.array(verts), np.array(faces)


def laplace_beltrami(V, F):
    """Cotangent stiffness L (symmetric PSD) and lumped mass M (diagonal)."""
    n = len(V)
    rows, cols, vals = [], [], []
    mass = np.zeros(n)
    for i, j, k in F:
        for a, b, c in ((i, j, k), (j, k, i), (k, i, j)):
            u, w = V[a] - V[c], V[b] - V[c]
            cot = np.dot(u, w) / np.linalg.norm(np.cross(u, w))
            rows += [a, b, a, b]
            cols += [b, a, a, b]
            vals += [-0.5 * cot, -0.5 * cot, 0.5 * cot, 0.5 * cot]
        area = 0.5 * np.linalg.norm(np.cross(V[j] - V[i], V[k] - V[i]))
        mass[[i, j, k]] += area / 3.0
    L = sp.csr_matrix((vals, (rows, cols)), shape=(n, n))
    return L, mass


# ================================================================ thermal
def n_i_rel(T_k, eg):
    """Intrinsic carrier density, up to a material constant: T^1.5 exp(-Eg/2kT)."""
    return T_k ** 1.5 * math.exp(-eg / (2.0 * K_B * T_k))


def leak_power(T_k, eg, p_ref, t_ref_k=None):
    """Leakage power scaled from silicon's reference by intrinsic carrier density."""
    t_ref_k = T_REF_K if t_ref_k is None else t_ref_k
    return p_ref * n_i_rel(T_k, eg) / n_i_rel(t_ref_k, v("eg_si"))


def operating_point(t_cool_c, p_dyn, eg, p_ref, r_th=R_TH, t_ref_k=None):
    """Smallest stable junction temperature solving T = Tc + R (Pdyn + Pleak(T)).
    Returns (T_j degC, total heat W) or None if thermal runaway (no fixed point)."""
    tc = t_cool_c + K0
    T = tc
    for _ in range(20000):
        T_new = tc + r_th * (p_dyn + leak_power(T, eg, p_ref, t_ref_k))
        if abs(T_new - T) < 1e-9:
            # stability: loop gain below one
            dT = 1e-3
            gain = r_th * (leak_power(T + dT, eg, p_ref, t_ref_k)
                           - leak_power(T, eg, p_ref, t_ref_k)) / dT
            if gain >= 1.0:
                return None
            return T - K0, p_dyn + leak_power(T, eg, p_ref, t_ref_k)
        if T_new > 5000.0:
            return None
        T = T_new
    return None


def max_heat(t_cool_c, eg, tj_max, p_ref, r_th=R_TH, t_ref_k=None):
    """Largest dynamic power such that the chip is stable and below its limit."""
    lo, hi = 0.0, 1e6
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        op = operating_point(t_cool_c, mid, eg, p_ref, r_th, t_ref_k)
        if op is not None and op[0] <= tj_max:
            lo = mid
        else:
            hi = mid
    op = operating_point(t_cool_c, lo, eg, p_ref, r_th, t_ref_k)
    return lo, op


# ================================================================ depth tiers
def lanczos_flops(nv, k):
    """Lanczos with full reorthogonalisation (registry): m = 2k steps, ~2 n m^2
    flops plus m sparse products; a closed triangle mesh has on average six
    neighbours per vertex, so nnz ~ 7n."""
    m = 2.0 * k
    return v("eq_lanczos_flops") * nv * m * m + m * 2.0 * 7.0 * nv


def tier_flops():
    """FLOP per geometry at each depth of computation (E1.4, reused by E9)."""
    c_e = v("eq_eig_flops")
    fam = v("depth_families")
    ns, nl = v("tier_n_small"), v("tier_n_large")
    ks, kl = v("tier_k_small"), v("tier_k_large")
    return [
        ("T1 partial spectrum   n=%.0e, k=%.0e" % (ns, ks), lanczos_flops(ns, ks)),
        ("T2 deep partial       n=%.0e, k=%.0e" % (nl, kl), lanczos_flops(nl, kl)),
        ("T3 full spectrum      n=%.0e" % ns, c_e * ns ** 3),
        ("T4 full spectrum      n=%.0e" % nl, c_e * nl ** 3),
        ("T5 T4 x %d metric families" % fam, fam * c_e * nl ** 3),
    ]


# ================================================================ main
def main():
    V_ = Verdicts("APPENDIX E1")
    rng = np.random.default_rng(v("seed"))

    # ---------------------------------------------------------- E1.1
    print("E1.1  The covariant operator on curved surfaces")
    print("Laplace-Beltrami on the unit sphere; exact spectrum l(l+1), multiplicity 2l+1")
    exact = [0.0, 2.0, 6.0, 12.0, 20.0]
    errs_by_level = []
    for level in (2, 3, 4):
        V, F = icosphere(level)
        L, m = laplace_beltrami(V, F)
        n = L.shape[0]
        Ld = L.toarray()
        Mi = 1.0 / np.sqrt(m)
        A = (Ld * Mi[:, None]) * Mi[None, :]        # symmetric M^-1/2 L M^-1/2
        lam = sla.eigh(A, eigvals_only=True, subset_by_index=[0, 35])
        groups, errs, k = [], [], 0
        for l, ex in enumerate(exact):
            mult = 2 * l + 1
            g = lam[k:k + mult]
            groups.append(g)
            errs.append(abs(np.mean(g) - ex) / max(ex, 1.0))
            k += mult
        errs_by_level.append(errs)
        print("  level %d: %5d vertices; modes l=0..4 mean: %s" % (
            level, n, ", ".join("%.4f" % np.mean(g) for g in groups)))
        if level == 4:
            sym = abs(L - L.T).max()
            V_.check("E1.1 operator symmetric (self-adjoint)", sym < 1e-12, f"{sym:.1e}")
            V_.check("E1.1 operator positive semidefinite", lam[0] > -1e-9, f"min {lam[0]:.2e}")
            V_.check("E1.1 kernel is the constants (lambda_0 = 0)", abs(lam[0]) < 1e-9,
                     f"{lam[0]:.2e}")
            ones = np.ones(n)
            V_.check("E1.1 operator annihilates constants", np.abs(L @ ones).max() < 1e-12)
            for l in range(1, 5):
                g = groups[l]
                spread = (g.max() - g.min()) / exact[l]
                gap_next = (lam[sum(2 * j + 1 for j in range(l + 1))] - g.max()) / exact[l]
                V_.check(f"E1.1 multiplicity 2l+1 = {2 * l + 1} recovered for l = {l}",
                         spread < 0.02 and gap_next > 0.2,
                         f"spread {spread:.4f}, gap {gap_next:.3f}")
    for l in range(1, 5):
        e = [row[l] for row in errs_by_level]
        V_.check(f"E1.1 eigenvalue l = {l} converges under refinement",
                 e[0] > e[1] > e[2] and e[2] < 0.02,
                 " > ".join("%.4f" % x for x in e))

    # heat kernel on the level-4 sphere
    V, F = icosphere(4)
    L, m = laplace_beltrami(V, F)
    n = L.shape[0]
    Mi = 1.0 / np.sqrt(m)
    A = (L.toarray() * Mi[:, None]) * Mi[None, :]
    lam, U = sla.eigh(A)
    Phi = U * Mi[:, None]                             # M-orthonormal eigenfunctions
    t = 0.1
    H = (Phi * np.exp(-t * lam)) @ Phi.T              # heat kernel
    mass_total = (H * m[None, :]).sum(axis=1)         # integral of H_t(x, .) = 1
    V_.check("E1.1 heat kernel conserves heat (integral = 1)",
             np.abs(mass_total - 1).max() < 1e-9, f"{np.abs(mass_total - 1).max():.1e}")
    V_.check("E1.1 heat kernel symmetric and positive",
             np.abs(H - H.T).max() < 1e-12 and H.min() > -1e-12)

    # ---------------------------------------------------------- E1.2
    print("\nE1.2  Roofline: arithmetic intensity and the power the chip draws")
    ridge = v("ridge")
    print("  reference accelerator H100 SXM: FP64 tensor %.0f TFLOP/s, %.2f TB/s, ridge %.1f FLOP/byte"
          % (H100_FP64_TC / 1e12, H100_BW / 1e12, ridge))
    kernels = []
    nnz = L.nnz
    x = rng.standard_normal(n)
    reps = 400
    t0 = time.perf_counter()
    for _ in range(reps):
        y = L @ x
    dt = (time.perf_counter() - t0) / reps
    kernels.append(("operator application (sparse)", 2.0 * nnz, 12.0 * nnz + 20.0 * n, dt))
    k_modes, b_fields = 1000, 1000
    Pk = Phi[:, :k_modes].copy()
    Fb = rng.standard_normal((n, b_fields))
    t0 = time.perf_counter()
    C = Pk.T @ Fb
    dt = time.perf_counter() - t0
    kernels.append(("spectral transform of 1000 fields (dense)", 2.0 * n * k_modes * b_fields,
                    8.0 * (n * k_modes + n * b_fields + k_modes * b_fields), dt))
    t0 = time.perf_counter()
    H2 = (Phi[:, :k_modes] * np.exp(-t * lam[:k_modes])) @ Phi[:, :k_modes].T
    dt = time.perf_counter() - t0
    kernels.append(("heat kernel from 1000 modes (dense)", 2.0 * n * n * k_modes,
                    8.0 * (2 * n * k_modes + n * n), dt))
    t0 = time.perf_counter()
    sla.eigh(A)
    dt = time.perf_counter() - t0
    kernels.append(("full spectrum, %d vertices (dense)" % n, 9.0 * n ** 3,
                    8.0 * n * n * 64.0, dt))     # blocked LAPACK, block 64 (model)
    print("  %-44s %12s %10s %12s %10s" % ("kernel", "FLOP", "FLOP/byte", "bound on H100",
                                            "local GF/s"))
    for name, fl, by, dt in kernels:
        ai = fl / by
        bound = "compute" if ai >= ridge else "memory"
        print("  %-44s %12.3e %10.2f %12s %10.2f" % (name, fl, ai, bound, fl / dt / 1e9))
    ai_sparse = kernels[0][1] / kernels[0][2]
    V_.check("E1.2 sparse operator application is memory-bound on the reference chip",
             ai_sparse < ridge, f"{ai_sparse:.3f} < {ridge:.1f}")
    for name, fl, by, _ in kernels[1:]:
        V_.check(f"E1.2 {name} is compute-bound on the reference chip",
                 fl / by > ridge, f"{fl / by:.1f} > {ridge:.1f}")
    print("  local rates are machine-dependent and shown for information; no check uses them")
    print("  the dense kernels are compute-bound; the facility runs its chips at rated power,")
    print("  and by the First Law that power is the heat output")

    # ---------------------------------------------------------- E1.3
    print("\nE1.3  How much heat a chip carries before it fails (R_th = %.3f K/W; best "
          "demonstrated %.4f K/W)" % (R_TH, v("rth_best_demo")))
    p_ref = LEAK_FRAC_REF * H100_TDP
    t_eq = None
    sic = [m_ for m_ in MATERIALS if m_[0].startswith("SiC")][0]
    target = n_i_rel(sic[2] + K0, sic[1])
    lo, hi = 200.0, 2000.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if n_i_rel(mid, v("eg_si")) < target:
            lo = mid
        else:
            hi = mid
    t_eq = lo - K0
    print("  silicon carbide at %.0f degC has the intrinsic carrier density of silicon at %.1f degC"
          % (sic[2], t_eq))
    V_.check("E1.3 SiC at its junction limit leaks like Si at room temperature or below",
             t_eq < v("t_ambient"), f"{t_eq:.1f} degC")
    print("  %-10s %10s %10s %12s %12s %10s %12s" % ("material", "coolant", "limit", "max heat W",
                                                       "x H100 TDP", "leak share", "W/cm2 die"))
    table = {}
    for name, eg, tj in MATERIALS:
        for tcool in (COOLANT_SCAN[0], v("t_coolant_si"), T_POST, COOLANT_SCAN[1],
                      v("t_sic_design"),
                      v("t_coolant_sic_max")):
            if tcool >= tj:
                continue
            pdyn, op = max_heat(tcool, eg, tj, p_ref)
            if op is None:
                continue
            tj_op, heat = op
            leak = heat - pdyn
            table[(name, tcool)] = (heat, tj_op, leak)
            print("  %-10s %8d C %8d C %12.0f %12.2f %9.1f%% %12.0f" % (
                name, tcool, tj, heat, heat / H100_TDP, 100 * leak / heat,
                heat / H100_DIE_CM2))
            V_.check(f"E1.3 {name} at {tcool:.0f} degC coolant: junction within limit",
                     tj_op <= tj + 1e-6, f"Tj {tj_op:.2f} <= {tj}")
            V_.check(f"E1.3 {name} at {tcool:.0f} degC coolant: energy closes (heat = power drawn)",
                     abs(heat - (pdyn + leak)) < 1e-9)
    # runaway: silicon at its limit with leakage forced high must show no fixed point
    run = operating_point(T_POST, 2000.0, v("eg_si"), p_ref)
    V_.check("E1.3 silicon driven past its limit enters thermal runaway or exceeds Tj",
             run is None or run[0] > v("tj_max_si"))
    si80 = table.get(("Si", T_POST))
    V_.check("E1.3 silicon at the post's %.0f degC coolant cannot carry its full design power"
             % T_POST,
             si80 is not None and si80[0] < H100_TDP, "%.0f W" % si80[0])
    sic300 = table.get(("SiC (4H)", v("t_sic_design")))
    V_.check("E1.3 SiC at its design coolant carries more heat per chip than Si at the "
             "coolest scan point",
             sic300[0] > table[("Si", COOLANT_SCAN[0])][0],
             "%.0f vs %.0f W" % (sic300[0], table[("Si", COOLANT_SCAN[0])][0]))
    sicmax = table.get(("SiC (4H)", v("t_coolant_sic_max")))
    V_.check("E1.3 SiC at its hottest coolant still carries the full design power",
             sicmax is not None and sicmax[0] >= H100_TDP - 1e-6, "%.0f W" % sicmax[0])
    leak_si = [table[("Si", tc)][2] / table[("Si", tc)][0] for tc in (COOLANT_SCAN[0], T_POST)
               if ("Si", tc) in table]
    V_.check("E1.3 silicon leakage share rises with coolant temperature",
             leak_si[1] > leak_si[0], " < ".join("%.3f" % s for s in leak_si))

    # ---------------------------------------------------------- E1.4
    print("\nE1.4  How much heat the public geometric dataset can produce")
    n_geo = v("n_corpus")
    V_.check("E1.4 corpus total equals the sum of its benchmarked parts",
             n_geo == sum(c for _, c in CORPORA), "%d" % n_geo)
    for name, cnt in CORPORA:
        print("  %-44s %10s geometries" % (name, f"{cnt:,}"))
    print("  %-44s %10s" % ("total", f"{n_geo:,}"))
    flop_per_joule = v("flop_per_joule")
    furnace_J_per_year = IT_POWER_MW * 1e6 * HOURS_PER_YEAR * 3600.0
    flop_per_year = furnace_J_per_year * flop_per_joule
    print("  energy efficiency %.2e FLOP/J (H100 FP64 tensor, %.1f%% sustained = TOP500 Rmax/Rpeak)"
          % (flop_per_joule, 100 * SUSTAINED))
    print("  a %.0f MW furnace consumes, and releases as heat, %.3e J/yr = %.2e FLOP/yr"
          % (IT_POWER_MW, furnace_J_per_year, flop_per_year))
    tiers = tier_flops()
    print("  %-50s %12s %12s %14s %12s" % ("depth of computation", "FLOP/geom", "MWh total",
                                           "furnace-years", "heat GW-yr"))
    years = []
    for name, fl in tiers:
        total = fl * n_geo
        joules = total / flop_per_joule
        yrs = joules / furnace_J_per_year
        years.append(yrs)
        print("  %-50s %12.3e %12.3e %14.3e %12.3e" % (
            name, fl, joules / 3.6e9, yrs, yrs * IT_POWER_MW / 1000.0))
    V_.check("E1.4 heat budget grows monotonically with depth of computation",
             all(b > a for a, b in zip(years, years[1:])))
    V_.check("E1.4 full-spectrum families keep a 100 MW furnace saturated for over a year",
             years[-1] > 1.0, "%.2f furnace-years" % years[-1])
    V_.check("E1.4 partial spectra alone cannot keep a 100 MW furnace saturated for a day",
             years[0] * 365.0 < 1.0, "%.2e days" % (years[0] * 365.0))
    # what tier T5 publishes: every eigenvalue (8 bytes each) for every geometry and metric
    # family; eigenvectors are published for the stored share of the spectrum (E9)
    ev_bytes = 8.0 * v("tier_n_large") * v("depth_families") * n_geo
    print("  T5 publishes the full eigenvalue spectra: %.2f PB for the corpus" % (ev_bytes / 1e15))
    V_.check("E1.4 the published eigenvalue spectra of the T5 corpus fit in petabytes",
             ev_bytes < 1e18, "%.2f PB" % (ev_bytes / 1e15))

    # ---------------------------------------------------------- E1.5 faults
    print("\nE1.5  Fault injection")
    faults = []
    # (a) the spectral checks must discriminate geometry: an ellipsoid presented
    #     as a sphere must break the l = 1 multiplicity
    Vf, Ff = icosphere(3)
    Vf = Vf * np.array([1.0, 1.0, 1.3])
    Lf, mf = laplace_beltrami(Vf, Ff)
    Mif = 1.0 / np.sqrt(mf)
    Af = (Lf.toarray() * Mif[:, None]) * Mif[None, :]
    lf = sla.eigh(Af, eigvals_only=True, subset_by_index=[0, 3])
    faults.append(("ellipsoid presented as a sphere (multiplicity check breaks)",
                   (lf[1:4].max() - lf[1:4].min()) / 2.0 >= 0.02))
    # (b) heat kernel built without the mass matrix fails conservation
    Hb = (U * np.exp(-t * lam)) @ U.T
    faults.append(("heat kernel without mass weighting (heat not conserved)",
                   np.abs((Hb * m[None, :]).sum(axis=1) - 1).max() > 1e-6))
    # (c) negative thermal resistance gives a junction colder than its coolant
    op = operating_point(T_POST, v("h100_tdp"), v("eg_si"), p_ref, r_th=-R_TH)
    faults.append(("negative thermal resistance (junction below coolant)",
                   op is None or op[0] < T_POST))
    # (d) leakage that falls with temperature contradicts carrier physics
    faults.append(("bandgap sign reversed (leakage falls with heat)",
                   n_i_rel(400.0, -v("eg_si")) / n_i_rel(300.0, -v("eg_si"))
                   < n_i_rel(400.0, v("eg_si")) / n_i_rel(300.0, v("eg_si"))))
    # (e) a full spectrum costed at n^2 instead of n^3 breaks the ordering of the tiers
    bad = [fl for _, fl in tiers]
    bad[2] = v("eq_eig_flops") * v("tier_n_small") ** 2
    faults.append(("full spectrum costed at n^2 instead of n^3 (tier order breaks)",
                   not all(b > a for a, b in zip(bad, bad[1:]))))
    for label, caught in faults:
        print("  %-62s %s" % (label, "caught" if caught else "MISSED"))
        V_.check(f"E1.5 fault caught: {label}", caught)

    V_.finish()


if __name__ == "__main__":
    main()
