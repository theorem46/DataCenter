"""E2 - The insight baseline: a public master geometric dataset.

The furnace tier's computation is not discarded. It is published once as a
master geometric dataset that every downstream developer builds on, adding its
own weights and methods, and that serves as ground truth for checking model
outputs. This experiment builds a prototype slice of that dataset and tests
the four claims made for it.

  E2a  The master slice. A family of curved surfaces (the sphere and smooth
       deformations of it) with full spectra of the covariant operator,
       stored eigenbases and heat-kernel signatures; versioned, with SHA-256
       checksums and provenance in a manifest.
  E2b  One dataset, three downstream architectures, as three different
       developers would use it:
         (1) a reduced-order spectral model (uses the stored eigenbasis)
         (2) a learned spectral filter of the kind used in graph networks,
             fitted on training spectra and applied to unseen surfaces with
             sparse operations only
         (3) a parameter-to-spectrum regressor that predicts eigenvalues of
             unseen surfaces from their shape parameter
  E2c  Ground truth. A verification harness scores candidate answers against
       the dataset; its resolution is set by the dataset's resolution.
  E2d  Amortisation. The energy to compute the slice once against every
       developer computing it separately, and the break-even number of
       downstream queries.
  E2e  Covariant against flat. Minimising a geometric energy by plain
       gradient descent in vertex coordinates, against descent that uses the
       geometry supplied by the furnace tier.

Run:  python3 -I Scripts/E2_insight_baseline.py
"""
import os
import sys
import json
import hashlib

import numpy as np
import scipy.linalg as sla
import scipy.sparse as sp
import scipy.sparse.linalg as spla

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from conventions import Verdicts  # noqa: E402
from registry import v  # noqa: E402
import E1_geometric_heat as E1  # noqa: E402

LEVEL = int(v("slice_level"))  # 2562 vertices
K_STORE = int(v("slice_k"))    # eigenpairs stored per surface
HKS_TIMES = np.geomspace(0.005, 2.0, 16)
DATA_DIR = os.path.join(ROOT, "dataset_slice")
VERSION = "0.1.0"
FLOP_PER_J = v("flop_per_joule")

# the family: one parameter sweep for the regressor, plus other deformation modes
SWEEP = [0.0, 0.04, 0.08, 0.12, 0.16, 0.20, 0.24, 0.28, 0.32]
HELD_OUT_A = [0.12, 0.24]
MODES = {
    "quad": lambda V: V[:, 0] ** 2 - V[:, 1] ** 2,
    "xy": lambda V: V[:, 0] * V[:, 1],
    "xz": lambda V: V[:, 0] * V[:, 2],
    "z3": lambda V: V[:, 2] ** 3,
}
GEOMS = [("quad", a) for a in SWEEP] + [("xy", 0.2), ("xz", 0.2), ("z3", 0.2)]


def gid(mode, a):
    return f"{mode}_{a:.2f}"


def surface(mode, a):
    V, F = E1.icosphere(LEVEL)
    V = V * (1.0 + a * MODES[mode](V))[:, None]
    L, m = E1.laplace_beltrami(V, F)
    return V, F, L, m


def full_spectrum(L, m):
    Mi = 1.0 / np.sqrt(m)
    A = (L.toarray() * Mi[:, None]) * Mi[None, :]
    lam, U = sla.eigh(A)
    return lam, U * Mi[:, None]                    # M-orthonormal eigenfunctions


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_entry(L, m, lam, phi, tol=1e-8):
    """Residual of the generalised eigenproblem and M-orthonormality."""
    R = L @ phi - (m[:, None] * phi) * lam[None, :]
    res = np.abs(R).max() / max(1.0, np.abs(lam).max())
    G = phi.T @ (m[:, None] * phi)
    orth = np.abs(G - np.eye(G.shape[0])).max()
    return res < tol and orth < tol, res, orth


def main():
    V_ = Verdicts("APPENDIX E2")
    os.makedirs(DATA_DIR, exist_ok=True)
    gen_hash = sha256_file(os.path.abspath(__file__))

    # =========================================================== E2a
    print("E2a  The master slice: %d surfaces, %d vertices, full spectra, %d stored modes"
          % (len(GEOMS), len(E1.icosphere(LEVEL)[0]), K_STORE))
    store = {}
    manifest = dict(name="master geometric dataset (prototype slice)", version=VERSION,
                    operator="cotangent Laplace-Beltrami with lumped mass",
                    generator_sha256=gen_hash, level=LEVEL, k_stored=K_STORE,
                    hks_times=[float(t) for t in HKS_TIMES], entries=[])
    flops_slice = 0.0
    for mode, a in GEOMS:
        V, F, L, m = surface(mode, a)
        lam, phi = full_spectrum(L, m)
        n = len(m)
        flops_slice += 9.0 * n ** 3
        hks = (phi ** 2) @ np.exp(-np.outer(lam, HKS_TIMES))   # n x T
        ok, res, orth = validate_entry(L, m, lam[:K_STORE], phi[:, :K_STORE])
        V_.check(f"E2a {gid(mode, a)}: eigen-residual and M-orthonormality", ok,
                 f"res {res:.1e}, orth {orth:.1e}")
        V_.check(f"E2a {gid(mode, a)}: constant mode at lambda = 0",
                 abs(lam[0]) < 1e-9 and np.ptp(phi[:, 0]) < 1e-9, f"{lam[0]:.1e}")
        V_.check(f"E2a {gid(mode, a)}: heat-kernel signature integrates to the heat trace",
                 np.allclose(m @ hks, np.exp(-np.outer(HKS_TIMES, lam)).sum(axis=1),
                             rtol=1e-9))
        path = os.path.join(DATA_DIR, gid(mode, a) + ".npz")
        np.savez_compressed(path, vertices=V, lam=lam, phi=phi[:, :K_STORE], mass=m, hks=hks)
        manifest["entries"].append(dict(id=gid(mode, a), mode=mode, amplitude=a,
                                        n_vertices=n, file=os.path.basename(path),
                                        sha256=sha256_file(path)))
        store[(mode, a)] = dict(V=V, F=F, L=L, m=m, lam=lam, phi=phi, hks=hks)
    with open(os.path.join(DATA_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    size_mb = sum(os.path.getsize(os.path.join(DATA_DIR, e["file"]))
                  for e in manifest["entries"]) / 1e6
    print("  written %d entries, %.1f MB compressed, manifest with SHA-256 per entry"
          % (len(manifest["entries"]), size_mb))
    for e in manifest["entries"]:
        ok = sha256_file(os.path.join(DATA_DIR, e["file"])) == e["sha256"]
        V_.check(f"E2a {e['id']}: checksum verifies against manifest", ok)
    lam_s = store[("quad", 0.0)]["lam"]
    exact = [2.0, 6.0, 12.0, 20.0]
    k0 = 1
    for l, ex in enumerate(exact, start=1):
        g = lam_s[k0:k0 + 2 * l + 1]
        k0 += 2 * l + 1
        V_.check(f"E2a sphere entry matches exact eigenvalue l(l+1) = {ex:.0f}",
                 abs(g.mean() - ex) / ex < 0.01, "%.4f" % g.mean())

    # =========================================================== E2b
    print("\nE2b  One dataset, three downstream architectures")
    t_q = 0.05
    errs1, errs2 = [], []
    # (1) reduced-order spectral model
    print("  (1) reduced-order spectral model, %d stored modes, heat diffusion to t = %.2f"
          % (K_STORE, t_q))
    for (mode, a), d in store.items():
        V, m, lam, phi = d["V"], d["m"], d["lam"], d["phi"]
        u0 = np.exp(-((V - V[0]) ** 2).sum(axis=1) / 0.05)
        c = phi.T @ (m * u0)
        exact_u = phi @ (np.exp(-t_q * lam) * c)
        pk = phi[:, :K_STORE]
        sur = pk @ (np.exp(-t_q * lam[:K_STORE]) * (pk.T @ (m * u0)))
        err = np.sqrt(m @ (sur - exact_u) ** 2) / np.sqrt(m @ exact_u ** 2)
        errs1.append(err)
    print("      relative error over %d surfaces: max %.2e" % (len(errs1), max(errs1)))
    V_.check("E2b (1) reduced-order model within 1e-3 of the exact solution on every surface",
             max(errs1) < 1e-3, "%.2e" % max(errs1))
    # full-solve comparator: backward Euler with a sparse factorisation
    d = store[("quad", 0.2)]
    L, m, V = d["L"], d["m"], d["V"]
    dt, steps = 1e-3, int(round(t_q / 1e-3))
    Mm = sp.diags(m)
    lu = spla.splu((Mm + dt * L).tocsc())
    u = np.exp(-((V - V[0]) ** 2).sum(axis=1) / 0.05)
    for _ in range(steps):
        u = lu.solve(m * u)
    c = d["phi"].T @ (m * np.exp(-((V - V[0]) ** 2).sum(axis=1) / 0.05))
    ex_u = d["phi"] @ (np.exp(-t_q * d["lam"]) * c)
    err_be = np.sqrt(m @ (u - ex_u) ** 2) / np.sqrt(m @ ex_u ** 2)
    n = len(m)
    flop_be = steps * (2.0 * (lu.L.nnz + lu.U.nnz) + 2.0 * n)
    flop_rom = 4.0 * n * K_STORE
    print("      full solve (backward Euler, %d steps): error %.2e, %.3e FLOP per query"
          % (steps, err_be, flop_be))
    print("      reduced-order query: error %.2e, %.3e FLOP per query (%.1fx fewer)"
          % (errs1[GEOMS.index(("quad", 0.2))], flop_rom, flop_be / flop_rom))
    V_.check("E2b (1) reduced-order query is cheaper and more accurate than the full solve",
             flop_rom < flop_be and max(errs1) < err_be,
             "%.1fx fewer FLOP" % (flop_be / flop_rom))

    # (2) learned spectral filter: fitted on training spectra, applied to unseen surfaces
    print("  (2) learned spectral filter (degree-40 Chebyshev in the operator), sparse ops only")
    test_ids = [("xy", 0.2), ("xz", 0.2), ("z3", 0.2)]
    train_ids = [k for k in store if k not in test_ids]
    lam_train = np.concatenate([store[k]["lam"] for k in train_ids])
    lmax = 1.05 * max(store[k]["lam"].max() for k in store)
    deg = 40
    x = 2.0 * lam_train / lmax - 1.0
    Tm = np.polynomial.chebyshev.chebvander(x, deg)
    coef, *_ = np.linalg.lstsq(Tm, np.exp(-t_q * lam_train), rcond=None)
    for k in test_ids:
        dd = store[k]
        Lk, mk, Vk = dd["L"], dd["m"], dd["V"]
        u0 = np.exp(-((Vk - Vk[0]) ** 2).sum(axis=1) / 0.05)

        def S(v):                                   # scaled operator, sparse
            return 2.0 * (Lk @ v) / mk / lmax - v
        t0v, t1v = u0, S(u0)
        out = coef[0] * t0v + coef[1] * t1v
        for j in range(2, deg + 1):
            t0v, t1v = t1v, 2.0 * S(t1v) - t0v
            out += coef[j] * t1v
        cc = dd["phi"].T @ (mk * u0)
        ex = dd["phi"] @ (np.exp(-t_q * dd["lam"]) * cc)
        errs2.append(np.sqrt(mk @ (out - ex) ** 2) / np.sqrt(mk @ ex ** 2))
    flop_filter = deg * (2.0 * store[test_ids[0]]["L"].nnz + 4.0 * n)
    print("      held-out surfaces %s: max error %.2e, %.3e FLOP per query, no eigen-solve"
          % (", ".join(gid(*k) for k in test_ids), max(errs2), flop_filter))
    V_.check("E2b (2) learned filter generalises to unseen surfaces within 1e-3",
             max(errs2) < 1e-3, "%.2e" % max(errs2))

    # (3) parameter-to-spectrum regressor
    print("  (3) parameter-to-spectrum regressor: eigenvalues 1-10 from the shape amplitude")
    train_a = [a for a in SWEEP if a not in HELD_OUT_A]
    Y = np.array([store[("quad", a)]["lam"][1:11] for a in train_a])
    P = np.vander(np.array(train_a), 5, increasing=True)
    W, *_ = np.linalg.lstsq(P, Y, rcond=None)
    worst = 0.0
    for a in HELD_OUT_A:
        pred = np.vander(np.array([a]), 5, increasing=True) @ W
        true = store[("quad", a)]["lam"][1:11]
        worst = max(worst, np.abs(pred[0] - true).max() / true.min())
    print("      held-out amplitudes %s: max relative error %.2e" % (HELD_OUT_A, worst))
    V_.check("E2b (3) regressor predicts unseen spectra within 0.5%", worst < 5e-3,
             "%.2e" % worst)

    # =========================================================== E2c
    print("\nE2c  Ground-truth verification harness")
    def sphere_low(level, k=25):
        Ls, ms = E1.laplace_beltrami(*E1.icosphere(level))
        vals = spla.eigsh(Ls.tocsc(), k=k, M=sp.diags(ms).tocsc(), sigma=-0.01,
                          which="LM", return_eigenvectors=False)
        return np.sort(vals)
    sph = {lv: sphere_low(lv) for lv in (LEVEL - 1, LEVEL, LEVEL + 1)}

    def group_mean(lams, l):
        k = l * l                                      # first index of degree l
        return lams[k:k + 2 * l + 1].mean()
    cont_q, thresholds = [], {}
    for l, ex in enumerate(exact, start=1):
        th = [3.0 * abs(group_mean(sph[lv + 1], l) - group_mean(sph[lv], l)) / ex
              for lv in (LEVEL - 1, LEVEL)]
        thresholds[l] = th
        # truth = this dataset's value; tolerance = its estimated distance to the continuum
        cont_q.append((f"sphere eigenvalue l={l}", group_mean(lam_s, l),
                       max(th[0], 1e-9)))
    disc_q = []
    for (mode, a), dd in list(store.items())[:6]:
        for j in (1, 5, 10, 20):
            disc_q.append((f"{gid(mode, a)} lambda_{j}", dd["lam"][j], 1e-9))
        Z = np.exp(-0.1 * dd["lam"]).sum()
        disc_q.append((f"{gid(mode, a)} heat trace Z(0.1)", Z, 1e-9))

    def verify(q, answer):
        name, truth, tol = q
        return abs(answer - truth) <= tol * abs(truth)

    probes = [("correct", 0.0), ("+0.5%", 0.005), ("+1%", 0.01), ("+5%", 0.05),
              ("+20%", 0.20)]
    print("  %-26s %18s %18s" % ("candidate answers", "continuum (sphere)", "dataset-exact"))
    rates = {}
    for label, eps in probes:
        acc_c = sum(verify(q, q[1] * (1 + eps)) for q in cont_q) / len(cont_q)
        acc_d = sum(verify(q, q[1] * (1 + eps)) for q in disc_q) / len(disc_q)
        rates[label] = (acc_c, acc_d)
        print("  %-26s %17.0f%% %17.0f%%   accepted" % (label, 100 * acc_c, 100 * acc_d))
    print("  continuum detection threshold by resolution (l = 1..4):")
    for l in range(1, 5):
        print("    l = %d: %d vertices %.3f%%  ->  %d vertices %.3f%%"
              % (l, 10 * 4 ** LEVEL + 2, 100 * thresholds[l][0],
                 10 * 4 ** (LEVEL + 1) + 2, 100 * thresholds[l][1]))
    V_.check("E2c every correct continuum answer accepted", rates["correct"][0] == 1.0)
    V_.check("E2c every correct dataset-exact answer accepted", rates["correct"][1] == 1.0)
    V_.check("E2c dataset-exact questions reject every error of 0.5% or more",
             all(rates[k][1] == 0.0 for k in ("+0.5%", "+1%", "+5%", "+20%")))
    V_.check("E2c continuum questions reject every 20% error", rates["+20%"][0] == 0.0)
    V_.check("E2c higher resolution tightens continuum verification for every l >= 2",
             all(thresholds[l][1] < thresholds[l][0] for l in range(2, 5)),
             "; ".join("l=%d %.2f%%->%.2f%%" % (l, 100 * thresholds[l][0],
                                              100 * thresholds[l][1]) for l in range(2, 5)))
    # truth for the continuum is l(l+1); the dataset value must sit within its own tolerance
    for l, ex in enumerate(exact, start=1):
        V_.check(f"E2c exact value {ex:.0f} lies within the dataset tolerance (l = {l})",
                 verify(cont_q[l - 1], ex))
    # wrong multiplicity claim
    mult_true = int(np.sum(np.abs(lam_s[1:16] - lam_s[1]) < 0.01 * lam_s[1]))
    V_.check("E2c multiplicity claim 'l = 1 has multiplicity 2' rejected",
             mult_true != 2 and mult_true == 3, f"dataset multiplicity {mult_true}")

    # =========================================================== E2d
    print("\nE2d  Amortisation")
    e_slice = flops_slice / FLOP_PER_J
    print("  slice computation: %.3e FLOP = %.1f J at reference efficiency" % (flops_slice, e_slice))
    for n_dev in (1, 5, 10, 50):
        print("  %3d developers: computed once %.1f J; each separately %.1f J; saved %.0f%%"
              % (n_dev, e_slice, n_dev * e_slice, 100 * (1 - 1 / n_dev)))
    per_geom = e_slice / len(GEOMS)
    saved_per_query = (flop_be - flop_rom) / FLOP_PER_J
    breakeven = per_geom / saved_per_query
    print("  break-even: %.0f downstream queries per surface repay its spectrum" % breakeven)
    V_.check("E2d break-even is finite and positive", 0 < breakeven < 1e9, "%.0f" % breakeven)

    # =========================================================== E2e
    print("\nE2e  Covariant against flat descent on a geometric energy")
    d = store[("quad", 0.2)]
    L, m, V, lam, phi = d["L"], d["m"], d["V"], d["lam"], d["phi"]
    beta = 1.0
    A = (L + beta * sp.diags(m)).tocsr()
    f = np.cos(3 * V[:, 0]) + V[:, 1] * V[:, 2]
    b = m * f
    u_star = spla.spsolve(A.tocsc(), b)
    tol = v("solve_tol")

    def rel_err(u):
        e = u - u_star
        return np.sqrt(e @ (A @ e)) / np.sqrt(u_star @ (A @ u_star))
    # flat: Euclidean gradient, optimal fixed step 2/(lmin+lmax)
    ev_hi = spla.eigsh(A, k=1, which="LA", return_eigenvectors=False)[0]
    ev_lo = spla.eigsh(A, k=1, sigma=0, which="LM", return_eigenvectors=False)[0]
    step = 2.0 / (ev_lo + ev_hi)
    u = np.zeros(n)
    it_flat = 0
    cap = 400000
    while rel_err(u) > tol and it_flat < cap:
        u -= step * (A @ u - b)
        it_flat += 1
    # covariant: preconditioned by the furnace-supplied eigenbasis
    pk, lk = phi[:, :K_STORE], lam[:K_STORE]
    lam_cut = lam[K_STORE]

    def P(g):                                     # inverse metric from upstream geometry
        c = pk.T @ g
        low = pk @ (c / (lk + beta))
        high = (g / m - pk @ c) / (lam_cut + beta)
        return low + high
    # optimal step for the preconditioned operator: spectrum in [1, (lmax+b)/(lcut+b)]
    lam_max_gen = lam[-1]
    kappa_cov = (lam_max_gen + beta) / (lam_cut + beta)
    step_c = 2.0 / (1.0 + kappa_cov)
    u = np.zeros(n)
    it_cov = 0
    while rel_err(u) > tol and it_cov < cap:
        u -= step_c * P(A @ u - b)
        it_cov += 1
    flop_flat = it_flat * (2.0 * A.nnz + 3.0 * n)
    flop_cov = it_cov * (2.0 * A.nnz + 4.0 * n * K_STORE + 6.0 * n)
    kappa_flat = ev_hi / ev_lo
    print("  condition number: flat %.0f, covariant %.1f" % (kappa_flat, kappa_cov))
    print("  iterations to %.0e: flat %d, covariant %d" % (tol, it_flat, it_cov))
    print("  downstream FLOP:   flat %.3e, covariant %.3e (%.1fx fewer)"
          % (flop_flat, flop_cov, flop_flat / flop_cov))
    V_.check("E2e both descents converge to the exact minimiser",
             it_flat < cap and it_cov < cap)
    V_.check("E2e covariant descent uses fewer downstream FLOP than flat descent",
             flop_cov < flop_flat, "%.1fx" % (flop_flat / flop_cov))
    V_.check("E2e upstream geometry reduces the condition number by over 100x",
             kappa_flat / kappa_cov > 100, "%.0fx" % (kappa_flat / kappa_cov))

    # =========================================================== faults
    print("\nE2f  Fault injection")
    faults = []
    # (a) one byte altered in a dataset file
    e0 = manifest["entries"][3]
    p0 = os.path.join(DATA_DIR, e0["file"])
    raw = bytearray(open(p0, "rb").read())
    tmp = p0 + ".tampered"
    raw[len(raw) // 2] ^= 0xFF
    open(tmp, "wb").write(raw)
    faults.append(("one byte altered in a dataset entry", sha256_file(tmp) != e0["sha256"]))
    os.remove(tmp)
    # (b) eigen-data of one surface stored under another's label
    a1, a2 = store[("quad", 0.0)], store[("quad", 0.32)]
    ok, _, _ = validate_entry(a1["L"], a1["m"], a2["lam"][:K_STORE], a2["phi"][:, :K_STORE])
    faults.append(("eigen-data stored under the wrong surface", not ok))
    # (c) reduced-order model with too few modes
    pk5 = phi[:, :5]
    u0 = np.exp(-((V - V[0]) ** 2).sum(axis=1) / 0.05)
    sur = pk5 @ (np.exp(-t_q * lam[:5]) * (pk5.T @ (m * u0)))
    exu = phi @ (np.exp(-t_q * lam) * (phi.T @ (m * u0)))
    e5 = np.sqrt(m @ (sur - exu) ** 2) / np.sqrt(m @ exu ** 2)
    faults.append(("reduced-order model truncated to 5 modes", not e5 < 1e-3))
    # (d) verifier tolerance loosened to 10% accepts a 5% error (self-test probe)
    loose = [(q[0], q[1], 0.10) for q in disc_q]
    faults.append(("verifier tolerance loosened to 10%",
                   any(verify(q, q[1] * 1.05) for q in loose)))
    # (e) flat descent with a step beyond 2/lmax diverges
    u = np.zeros(n)
    for _ in range(200):
        u -= (2.2 / ev_hi) * (A @ u - b)
    faults.append(("flat descent with step 2.2/lambda_max", not rel_err(u) < 1.0))
    for label, caught in faults:
        print("  %-55s %s" % (label, "caught" if caught else "MISSED"))
        V_.check(f"E2f fault caught: {label}", caught)
    V_.finish()


if __name__ == "__main__":
    main()
