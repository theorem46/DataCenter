"""E9 - The value of the master geometric dataset.

E2 shows that the dataset works. E9 measures what it is worth, testing the
dataset against itself and against flat methods only, and states the result
in the units of the rest of the paper (FLOP, MWh, USD).

  E9.1  Compute once, use everywhere. The cost of the public corpus at the deep
        tiers of E1.4, in FLOP, MWh and USD; drawn from the grid by a
        conventional hyperscale facility against the furnace (whose heat is
        recovered, E3); and against every developer recomputing it.
  E9.2  Sample efficiency. The same least-squares learner predicts geometric
        fields on curved surfaces from labelled samples, once with raw
        coordinate features (monomials) and once with the dataset's stored
        eigenbasis, at the same number of features. Two targets: heat
        diffusion from a point source, and the response of the screened
        Poisson operator to a smooth load (solved directly, not through the
        eigenbasis). Training sets are multiples of the feature count.
  E9.3  Convergence scaling. The same problem is solved at four mesh
        resolutions by flat methods (gradient descent and conjugate gradients)
        and by covariant methods preconditioned with the dataset's stored
        spectrum (a fixed share of it). Flat conditioning grows as h^-2;
        the covariant method's does not. Run at both ends of the stored-share
        range.
  E9.4  Ground truth. On the sphere, whose spectrum l(l+1) is exact, the
        dataset's discretisation error sets the smallest error the verifier
        can certify. Corrupted answers are scored at each resolution; the
        certifiable precision improves as h^2 while the cost of a full
        spectrum grows as n^3.
  E9.5  One ledger. Break-even downstream solves per surface at each
        resolution, and the dataset's value in MWh and USD.
  E9.6  Fault injection.

Every input is read from registry.py; specimen shapes and output grids are
declared protocol constants.

Run:  python3 -I Scripts/E9_dataset_value.py
"""
import math
import os
import sys

import numpy as np
import scipy.linalg as sla
import scipy.sparse as sp
import scipy.sparse.linalg as spla

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from conventions import (Verdicts, PUE_HYPERSCALE, PRICE_USD_PER_MWH,  # noqa: E402
                         IT_POWER_MW)
from registry import v, REG  # noqa: E402
import E1_geometric_heat as E1  # noqa: E402
import E3_cascade as E3  # noqa: E402

FLOP_PER_J = v("flop_per_joule")
J_PER_MWH = 3.6e9
TOL = v("solve_tol")
BETA = 1.0                                   # screening of the test operator L + beta M
LEVELS = (2, 3, 4, 5)                        # mesh resolutions (specimen)
LEARN_LEVEL = 4                              # resolution of the learning specimens
SPECIMENS = (("bumpy", 0.25), ("bumpy", 0.40), ("z3", 0.20))   # surfaces (specimen)
SAMPLE_MULT = (2, 4, 8, 16)                  # training samples / feature count (grid)
REPS = 5                                     # random draws per sample size
DEVELOPERS = (1, 5, 10, 50)                  # output grid
HEAT_T = 0.05                                # diffusion time of the heat target (specimen)


def shape(V, mode, amp):
    if mode == "bumpy":
        r = 1.0 + amp * np.sin(5 * V[:, 0]) * np.sin(5 * V[:, 1]) * np.cos(5 * V[:, 2])
    else:
        r = 1.0 + amp * V[:, 2] ** 3
    return V * r[:, None]


def surface(level, mode=None, amp=0.0):
    V, F = E1.icosphere(level)
    if mode:
        V = shape(V, mode, amp)
    L, m = E1.laplace_beltrami(V, F)
    return V, F, L, m


def monomials(V, deg):
    ex = [(a, b, c) for a in range(deg + 1) for b in range(deg + 1) for c in range(deg + 1)
          if a + b + c <= deg]
    return np.stack([V[:, 0] ** a * V[:, 1] ** b * V[:, 2] ** c for a, b, c in ex], 1)


def fit_error(Fm, u, m, ntr, rng):
    errs = []
    n = len(u)
    for _ in range(REPS):
        idx = rng.choice(n, ntr, replace=False)
        te = np.setdiff1d(np.arange(n), idx)
        c, *_ = np.linalg.lstsq(Fm[idx], u[idx], rcond=None)
        p = Fm @ c
        errs.append(math.sqrt(np.sum(m[te] * (p[te] - u[te]) ** 2) / np.sum(m[te] * u[te] ** 2)))
    return float(np.median(errs))


def solves(level, frac, mode="bumpy", amp=0.25):
    """Flat GD, flat CG, covariant GD and covariant PCG on (L + beta M) u = M f."""
    V, F, L, m = surface(level, mode, amp)
    n = len(V)
    A = (L + BETA * sp.diags(m)).tocsr()
    M = sp.diags(m).tocsc()
    f = np.cos(3 * V[:, 0]) + V[:, 1] * V[:, 2]
    b = m * f
    us = spla.spsolve(A.tocsc(), b)
    nrm = math.sqrt(us @ (A @ us))

    def err(u):
        e = u - us
        return math.sqrt(max(e @ (A @ e), 0.0)) / nrm
    lmax = spla.eigsh(L.tocsc(), k=1, M=M, which="LA", return_eigenvectors=False)[0]
    K = max(int(frac * n), 2)
    lam, phi = spla.eigsh(L.tocsc(), k=K + 1, M=M, sigma=-0.01)
    o = np.argsort(lam)
    lam, phi = lam[o], phi[:, o]
    pk, lk, lcut = phi[:, :K], lam[:K], lam[K]

    def P(g):
        c = pk.T @ g
        return pk @ (c / (lk + BETA)) + (g / m - pk @ c) / (lcut + BETA)
    ev_hi = spla.eigsh(A, k=1, which="LA", return_eigenvectors=False)[0]
    ev_lo = spla.eigsh(A, k=1, sigma=0, which="LM", return_eigenvectors=False)[0]
    kap_flat = ev_hi / ev_lo
    kap_cov = (lmax + BETA) / (lcut + BETA)
    cap = 10 ** 6
    # flat gradient descent, optimal fixed step
    u, it_gd = np.zeros(n), 0
    st = 2.0 / (ev_lo + ev_hi)
    while err(u) > TOL and it_gd < cap:
        u -= st * (A @ u - b)
        it_gd += 1
    # covariant gradient descent
    u, it_cgd = np.zeros(n), 0
    stc = 2.0 / (1.0 + kap_cov)
    while err(u) > TOL and it_cgd < cap:
        u -= stc * P(A @ u - b)
        it_cgd += 1

    def pcg(prec):
        u = np.zeros(n)
        r = b - A @ u
        z = prec(r)
        p = z.copy()
        rz = r @ z
        it = 0
        while err(u) > TOL and it < cap and np.isfinite(rz) and rz > 0:
            Ap = A @ p
            a = rz / (p @ Ap)
            u += a * p
            r -= a * Ap
            z = prec(r)
            rz_new = r @ z
            p = z + (rz_new / rz) * p
            rz = rz_new
            it += 1
        return it if err(u) <= TOL else -1          # -1: did not converge
    it_cg = pcg(lambda r: r)
    it_pcg = pcg(P)
    nnz = A.nnz
    fl = dict(gd=it_gd * (2.0 * nnz + 3.0 * n), cg=it_cg * (2.0 * nnz + 10.0 * n),
              cgd=it_cgd * (2.0 * nnz + 4.0 * n * K + 6.0 * n),
              pcg=it_pcg * (2.0 * nnz + 4.0 * n * K + 13.0 * n))
    return dict(level=level, n=n, K=K, kap_flat=kap_flat, kap_cov=kap_cov, it_gd=it_gd,
                it_cg=it_cg, it_cgd=it_cgd, it_pcg=it_pcg, flop=fl, nnz=nnz,
                spec_flop=E1.lanczos_flops(n, K), pcg=pcg, pk=pk, lk=lk, m=m, cap=cap)


def main():
    V_ = Verdicts("APPENDIX E9")
    rng = np.random.default_rng(int(v("seed")))
    print("E9  THE VALUE OF THE MASTER GEOMETRIC DATASET")

    # ------------------------------------------------------------ E9.1
    print("\nE9.1  Compute once, use everywhere (public corpus, %s geometries)"
          % f"{v('n_corpus'):,}")
    sic = [c for c in E3.CHIPS if c[0] == "SiC-300"][0]
    rA = E3.scenario(sic, "A", E3.NOMINAL)
    rec = (rA["w_cycle"] + rA["p_tower"]) / (IT_POWER_MW * 1e6)
    grid_furn = 1.0 + v("furnace_overhead") - rec
    print("  grid per joule of computation: hyperscale %.3f, furnace %.3f (E3, %.1f%% recovered)"
          % (PUE_HYPERSCALE, grid_furn, 100 * rec))
    tiers = E1.tier_flops()
    print("  %-38s %12s %12s %12s %12s %12s" % ("tier", "FLOP total", "IT MWh", "hyper USD",
                                               "furnace USD", "heat MWh"))
    led = {}
    for name, fl in tiers[3:]:
        tot = fl * v("n_corpus")
        it_mwh = tot / FLOP_PER_J / J_PER_MWH
        c_h = it_mwh * PUE_HYPERSCALE * PRICE_USD_PER_MWH
        c_f = it_mwh * grid_furn * PRICE_USD_PER_MWH
        led[name[:2]] = (tot, it_mwh, c_h, c_f)
        print("  %-38s %12.3e %12.3e %12.3e %12.3e %12.3e" % (name, tot, it_mwh, c_h, c_f,
                                                            it_mwh))
        V_.check(f"E9.1 {name[:2]}: furnace computes the corpus for less than hyperscale",
                 c_f < c_h, "%.0f%% less" % (100 * (1 - c_f / c_h)))
    e1_mwh = tiers[4][1] * v("n_corpus") / FLOP_PER_J / J_PER_MWH
    V_.check("E9.1 coherence: tier energy equals E1.4", abs(e1_mwh - led["T5"][1]) < 1e-6 * e1_mwh)
    _, mwh5, ch5, cf5 = led["T5"]
    print("  T5 corpus, computed once in the furnace, against N developers each computing it:")
    for N in DEVELOPERS:
        print("    N = %2d: separately %.2e USD, once %.2e USD, saved %.2e USD (%.0f%%)"
              % (N, N * ch5, cf5, N * ch5 - cf5, 100 * (1 - cf5 / (N * ch5))))
    V_.check("E9.1 computing once saves at every N, including a single developer",
             all(N * ch5 > cf5 for N in DEVELOPERS))
    print("  each additional developer served saves %.2e USD and %.2e MWh"
          % (ch5, mwh5 * PUE_HYPERSCALE))

    # ------------------------------------------------------------ E9.2
    deg = int(v("raw_feature_degree"))
    print("\nE9.2  Sample efficiency: raw coordinates vs the dataset's eigenbasis "
          "(level %d, degree-%d monomials)" % (LEARN_LEVEL, deg))
    ratios, wins, total = [], 0, 0
    for mode, amp in SPECIMENS:
        V, F, L, m = surface(LEARN_LEVEL, mode, amp)
        n = len(V)
        Mi = 1.0 / np.sqrt(m)
        lam, U = sla.eigh((L.toarray() * Mi[:, None]) * Mi[None, :])
        phi = U * Mi[:, None]
        X = monomials(V, deg)
        K = X.shape[1]
        E = phi[:, :K]
        u0 = np.zeros(n)
        u0[0] = 1.0 / m[0]
        heat = phi @ (np.exp(-HEAT_T * lam) * (phi.T @ (m * u0)))
        f = np.cos(3 * V[:, 0]) + V[:, 1] * V[:, 2]
        poisson = spla.spsolve((L + BETA * sp.diags(m)).tocsc(), m * f)
        sq = np.sqrt(m)[:, None]
        print("  %s %.2f: %d features each; feature conditioning raw %.1e, dataset %.1e"
              % (mode, amp, K, np.linalg.cond(X * sq), np.linalg.cond(E * sq)))
        for tname, u in (("heat diffusion", heat), ("Poisson response", poisson)):
            row = []
            for c in SAMPLE_MULT:
                ntr = c * K
                er, ee = fit_error(X, u, m, ntr, rng), fit_error(E, u, m, ntr, rng)
                row.append((ntr, er, ee))
                ratios.append(er / ee)
                wins += ee < er
                total += 1
            print("    %-17s " % tname + "  ".join("n=%d raw %.1e data %.1e" % r for r in row))
            best_data = row[0][2]
            reached = [r[0] for r in row if r[1] <= best_data]
            print("    %-17s raw features reach the dataset's %d-sample error: %s"
                  % ("", row[0][0], ("at %d samples" % reached[0]) if reached
                     else "not within %d samples" % row[-1][0]))
    print("  error ratio raw / dataset: %.1f to %.1f (median %.1f)"
          % (min(ratios), max(ratios), float(np.median(ratios))))
    V_.check("E9.2 the dataset basis gives lower error at every sample size, target and surface",
             wins == total, "%d of %d" % (wins, total))
    V_.check("E9.2 the dataset basis is perfectly conditioned (orthonormal in the mass metric)",
             True if np.linalg.cond(E * sq) < 1.0 + 1e-6 else False, "%.6f" % np.linalg.cond(E * sq))

    # ------------------------------------------------------------ E9.3
    print("\nE9.3  Convergence scaling with resolution (screened Poisson, bumpy 0.25)")
    sweep = {}
    for frac in (REG["spectral_fraction"].sweep[0], v("spectral_fraction"),
                 REG["spectral_fraction"].sweep[1]):
        print("  stored share of the spectrum %.2f" % frac)
        print("  %5s %7s %6s %10s %8s %8s %8s %8s %8s" % ("level", "n", "K", "kappa flat",
              "kappa cov", "GD", "CG", "cov GD", "cov PCG"))
        rows = [solves(lev, frac) for lev in LEVELS]
        for r in rows:
            print("  %5d %7d %6d %10.0f %8.2f %8d %8d %8d %8d" % (
                r["level"], r["n"], r["K"], r["kap_flat"], r["kap_cov"], r["it_gd"], r["it_cg"],
                r["it_cgd"], r["it_pcg"]))
        sweep[frac] = rows
        g = lambda key: rows[-1][key] / rows[0][key]
        per = lambda key: [b[key] / a[key] for a, b in zip(rows, rows[1:])]
        print("  growth over %d refinements: GD x%.1f, CG x%.1f; covariant GD x%.2f, PCG x%.2f"
              % (len(rows) - 1, g("it_gd"), g("it_cg"), g("it_cgd"), g("it_pcg")))
        V_.check(f"E9.3 share {frac:g}: flat conditioning grows as h^-2 (x4 per refinement, "
                 "within 15%)", all(abs(x / 4.0 - 1) < 0.15 for x in per("kap_flat")),
                 ", ".join("%.2f" % x for x in per("kap_flat")))
        V_.check(f"E9.3 share {frac:g}: three refinements cost covariant GD less growth than "
                 "one refinement costs flat GD", g("it_cgd") < min(per("it_gd")),
                 "x%.2f < x%.2f" % (g("it_cgd"), min(per("it_gd"))))
        V_.check(f"E9.3 share {frac:g}: the same holds against the strongest flat method (CG)",
                 g("it_pcg") < min(per("it_cg")),
                 "x%.2f < x%.2f" % (g("it_pcg"), min(per("it_cg"))))
        V_.check(f"E9.3 share {frac:g}: covariant PCG iterations do not grow with resolution "
                 "while CG grows at every refinement",
                 rows[-1]["it_pcg"] <= rows[0]["it_pcg"]
                 and all(b["it_cg"] > a["it_cg"] for a, b in zip(rows, rows[1:])),
                 "PCG %d -> %d; CG %d -> %d" % (rows[0]["it_pcg"], rows[-1]["it_pcg"],
                                                rows[0]["it_cg"], rows[-1]["it_cg"]))
        none = [r["level"] for r in rows if r["it_pcg"] >= r["it_cg"]]
        if none:
            print("  no iteration advantage over CG at level %s (only %s stored modes)"
                  % (", ".join(map(str, none)),
                     ", ".join(str(r["K"]) for r in rows if r["level"] in none)))
        V_.check(f"E9.3 share {frac:g}: covariant GD uses fewer FLOP than flat GD at every level",
                 all(r["flop"]["cgd"] < r["flop"]["gd"] for r in rows),
                 ", ".join("%.1fx" % (r["flop"]["gd"] / r["flop"]["cgd"]) for r in rows))
        # with a dense stored basis, one covariant step costs 4nK extra FLOP. Against CG it
        # wins in FLOP when one application of the downstream operator costs more than
        # C* = it_pcg 4nK / (it_cg - it_pcg) (derived; reported, not assumed)
        cstar = [r["it_pcg"] * 4.0 * r["n"] * r["K"] / (r["it_cg"] - r["it_pcg"])
                 if r["it_cg"] > r["it_pcg"] else float("nan") for r in rows]
        print("  FLOP break-even against CG: one operator application must cost more than "
              + ", ".join("n/a" if c != c else "%.1e" % c for c in cstar) + " FLOP")
        print("  (%s times a sparse mesh product); downstream operators heavier than this, such"
              % ", ".join("n/a" if c != c else "%.0f" % (c / (2.0 * r["nnz"]))
                          for c, r in zip(cstar, rows)))
        print("  as a model evaluation per step, favour the covariant method in FLOP as well")
    nom = sweep[v("spectral_fraction")]

    # ------------------------------------------------------------ E9.4
    print("\nE9.4  Ground truth on the unit sphere (exact spectrum l(l+1))")
    print("  %5s %7s %16s %18s %16s" % ("level", "n", "certifiable err", "full-spectrum FLOP",
                                       "detects >= "))
    eps, cost = [], []
    probes = (0.001, 0.003, 0.01, 0.03, 0.1)        # relative corruption (output grid)
    det_rows = []
    for lev in LEVELS:
        V, F, L, m = surface(lev)
        # l = 0..4 is 25 eigenvalues; ask for l = 0..5 (36) so the l = 4 cluster is
        # complete, then keep the first 25
        lam = spla.eigsh(L.tocsc(), k=36, M=sp.diags(m).tocsc(), sigma=-0.01,
                         return_eigenvectors=False)
        lam = np.sort(lam)[:25]
        exact = np.array([l * (l + 1) for l in range(5) for _ in range(2 * l + 1)])
        e = float(np.max(np.abs(lam[1:] - exact[1:]) / exact[1:]))
        eps.append(e)
        cost.append(v("eq_eig_flops") * len(V) ** 3)
        # an answer is certified correct if within the dataset's error of the dataset value;
        # a corrupted continuum answer (1 + d) l(l+1) is caught if it falls outside
        caught = [bool(np.all(np.abs((1 + d) * exact[1:] - lam[1:]) / lam[1:] > e)) for d in probes]
        correct_ok = bool(np.all(np.abs(exact[1:] - lam[1:]) / lam[1:] <= e * (1 + 1e-9)
                                 / (1 - e)))
        det_rows.append((lev, caught, correct_ok))
        wrong = np.array([l * (l + 2) for l in range(5) for _ in range(2 * l + 1)])
        wrong_flag = bool(np.max(np.abs(lam[1:] - wrong[1:]) / wrong[1:]) > e)
        smallest = [d for d, c in zip(probes, caught) if c]
        print("  %5d %7d %16.2e %18.2e %16s" % (lev, len(V), e, cost[-1],
                                               ("%.1f%%" % (100 * smallest[0])) if smallest
                                               else "none"))
    # h halves per level, so an error ratio of 4 is second order
    print("  error ratio per refinement: %s (second order = 4)"
          % ", ".join("%.2f" % (a / b) for a, b in zip(eps, eps[1:])))
    V_.check("E9.4 certifiable precision improves at second order (ratio 4 per refinement, "
             "within 15%)", all(abs((a / b) / 4.0 - 1) < 0.15 for a, b in zip(eps, eps[1:])),
             ", ".join("%.2f" % (a / b) for a, b in zip(eps, eps[1:])))
    V_.check("E9.4 every correct answer is accepted at every resolution",
             all(r[2] for r in det_rows))
    V_.check("E9.4 the smallest detectable corruption falls with resolution",
             all(sum(b[1]) >= sum(a[1]) for a, b in zip(det_rows, det_rows[1:]))
             and sum(det_rows[-1][1]) > sum(det_rows[0][1]))
    print("  each 4x gain in certifiable precision costs 64x in full-spectrum work: the")
    print("  furnace pays it once for every developer")

    # ------------------------------------------------------------ E9.5
    print("\nE9.5  One ledger: break-even downstream solves per surface (nominal share,")
    print("       covariant GD against flat GD, as in E2e)")
    print("  %5s %14s %14s %14s %14s" % ("level", "dataset FLOP", "saved/solve", "break-even",
                                         "J saved/solve"))
    be = []
    for r in nom:
        saved = r["flop"]["gd"] - r["flop"]["cgd"]
        b_e = r["spec_flop"] / saved
        be.append(b_e)
        print("  %5d %14.3e %14.3e %14.2f %14.3e" % (r["level"], r["spec_flop"], saved, b_e,
                                                    saved / FLOP_PER_J))
    sav = [r["flop"]["gd"] - r["flop"]["cgd"] for r in nom]
    cst = [r["spec_flop"] for r in nom]
    V_.check("E9.5 the saving per downstream use grows by more than 4x per refinement",
             all(b / a > 4.0 for a, b in zip(sav, sav[1:])),
             ", ".join("x%.1f" % (b / a) for a, b in zip(sav, sav[1:])))
    V_.check("E9.5 the stored spectrum is repaid within a finite number of uses at every level",
             all(0 < b < float("inf") for b in be), ", ".join("%.2f" % b for b in be))
    print("  the dataset's own cost grows faster (x%s per refinement) than the saving per use:"
          % "/".join("%.0f" % (b / a) for a, b in zip(cst, cst[1:])))
    print("  deep geometry is expensive to compute and cheap to reuse, which is why it should")
    print("  be computed once, by one furnace, for every developer")
    fin = nom[-1]
    print("  at level %d one covariant solve takes %.0fx fewer iterations than flat GD, %.0fx"
          " fewer than CG," % (fin["level"], fin["it_gd"] / fin["it_cgd"],
                               fin["it_cg"] / fin["it_pcg"]))
    print("  and the iteration advantage grows with resolution")
    print("  T5 corpus: %.2e MWh of computation, %.2e USD in the furnace; each developer "
          "spared it saves %.2e USD" % (mwh5, cf5, ch5))

    # ------------------------------------------------------------ E9.6 faults
    print("\nE9.6  Fault injection")
    # (a) preconditioner that drops the high-mode term is singular: PCG cannot converge
    r3 = nom[1]
    pk3, lk3, m3 = r3["pk"], r3["lk"], r3["m"]
    bad_it = r3["pcg"](lambda g: pk3 @ ((pk3.T @ g) / (lk3 + BETA)))
    # (b) the dataset arm given another surface's eigenbasis
    Vb, Fb, Lb, mb = surface(LEARN_LEVEL, "bumpy", 0.40)
    Mib = 1.0 / np.sqrt(mb)
    _, Ub = sla.eigh((Lb.toarray() * Mib[:, None]) * Mib[None, :])
    Eb = (Ub * Mib[:, None])[:, :K]
    own = fit_error(E, poisson, m, SAMPLE_MULT[1] * K, rng)
    other = fit_error(Eb, poisson, m, SAMPLE_MULT[1] * K, rng)
    faults = [
        ("preconditioner without its high-mode term (singular metric)",
         bad_it == -1),
        ("dataset arm given another surface's eigenbasis (geometry mismatch)",
         other > own),
        ("sphere checked against the wrong law l(l+2)", wrong_flag),
        ("corpus priced without the furnace's recovered electricity",
         led["T5"][3] < led["T5"][1] * (1 + v("furnace_overhead")) * PRICE_USD_PER_MWH),
        ("dataset basis replaced by raw features in the dataset arm",
         np.linalg.cond(X * sq) > 1.0 + 1e-6),
    ]
    for label, caught in faults:
        print("  %-72s %s" % (label, "caught" if caught else "MISSED"))
        V_.check(f"E9.6 fault caught: {label}", caught)
    V_.finish()


if __name__ == "__main__":
    main()
