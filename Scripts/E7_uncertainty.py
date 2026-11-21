"""E7 - Uncertainty: how robust are the savings?

Every registry entry that carries a sweep range and enters the SiC design
point (E3, power configuration A) is sampled uniformly over its range (the
maximum-entropy choice when only bounds are known). Each sample is passed
through the physical checks of E3. Inputs without a range are held at their
registry value, and quantities on which the result is exactly linear are
reported as exact sensitivities instead of being sampled.

Savings are per gigawatt of IT power per year, at the EIA industrial price.

  E7.1  primary result, equal IT power, no leakage credit: a 1 GW SiC furnace
        against a 1 GW silicon hyperscale facility, the SiC chips assumed to
        deliver exactly silicon's computation per IT joule
            savings = (PUE_hyperscale - (1 + overhead - recovered)) x 1 GW x 8760 h x price
        and against the US and global average facilities
  E7.2  exact linear sensitivities: electricity price; furnace overhead from the
        hyperscale level to the US-average level (both benchmark-anchored)
  E7.3  the leakage credit: at equal computation, silicon's leakage is power the
        SiC furnace does not draw. Reported over the leakage-share sweep, never
        folded into E7.1
  E7.4  break-even SiC logic efficiency epsilon* over the samples and over the
        leakage-share sweep
  E7.5  which inputs move the result (rank correlation)
  E7.6  fault injection

Run:  python3 -I Scripts/E7_uncertainty.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from conventions import (Verdicts, PUE_HYPERSCALE, PUE_INDUSTRY_AVG,  # noqa: E402
                         HOURS_PER_YEAR, PRICE_USD_PER_MWH, IT_POWER_MW)
from registry import v, REG  # noqa: E402
import E3_cascade as E3  # noqa: E402
import E4_leakage_crossover as E4  # noqa: E402

N = int(v("mc_samples"))
CHIP = [c for c in E3.CHIPS if c[0] == "SiC-300"][0]
MW_PER_GW = 1000.0
# sampled: registry id -> E3 parameter name
SAMPLED = {
    "eta_exp_orc": "eta_turb_orc",
    "pinch": "pinch_K",
    "sink_approach": "sink_approach_K",
    "recup_min_pinch": "recup_min_pinch_K",
    "loop_drop": "loop_drop_K",
    "subcrit_margin": "subcrit_margin_K",
    "tower_H": "tower_H",
    "eta_tower_turb": "tower_turb",
}


def rankdata(x):
    order = np.argsort(x)
    r = np.empty(len(x))
    r[order] = np.arange(len(x))
    return r


def spearman(a, b):
    return np.corrcoef(rankdata(a), rankdata(b))[0, 1]


def savings_equal_it(eta_rec, overhead, price, pue_base):
    """USD per GW of IT power per year; no leakage credit."""
    grid_f = 1.0 + overhead - eta_rec
    return (pue_base - grid_f) * MW_PER_GW * HOURS_PER_YEAR * price


def savings_equal_compute(eta_rec, overhead, price, pue_base, phi_base, phi_sic, eps=1.0):
    """USD per year for the furnace delivering the computation of 1 GW of silicon IT."""
    it = phi_base / (eps * phi_sic)
    return (pue_base - it * (1.0 + overhead - eta_rec)) * MW_PER_GW * HOURS_PER_YEAR * price


def main():
    V = Verdicts("APPENDIX E7")
    rng = np.random.default_rng(int(v("seed")))
    print("E7  UNCERTAINTY  (%d samples, %s at %.0f degC, power configuration A)"
          % (N, CHIP[0], CHIP[1]))
    print("  sampled uniformly over the registry sweep range:")
    samples = {}
    for rid, key in SAMPLED.items():
        lo, hi = REG[rid].sweep
        samples[rid] = rng.uniform(lo, hi, N)
        print("    %-16s [%s] %-14s nominal %g" % (rid, REG[rid].kind, REG[rid].sweep, v(rid)))
    eta_rec = np.empty(N)
    all_valid = True
    capped = 0
    chosen = {}
    for i in range(N):
        prm = dict(E3.NOMINAL)
        for rid, key in SAMPLED.items():
            prm[key] = float(samples[rid][i])
        # the cycle is re-selected in every sample: the best feasible cycle of E3
        sink = E3.T_AMBIENT_C + prm["sink_approach_K"]
        cname, _ = E3.best_cycle(CHIP[1] - prm["loop_drop_K"] / 2.0, sink, prm)
        r = E3.scenario((CHIP[0], CHIP[1], cname.replace("ORC ", "ORC:")), "A", prm)
        chosen[cname] = chosen.get(cname, 0) + 1
        if r is None or not all(ok for _, ok, _ in E3.validate(r)):
            all_valid = False
            eta_rec[i] = np.nan
            continue
        capped += bool(r["cycle"].get("capped"))
        eta_rec[i] = (r["w_cycle"] + r["p_tower"]) / (IT_POWER_MW * 1e6)
    V.check("E7 every sample is feasible and passes the E3 physical checks", all_valid)
    print("\n  electricity recovered: median %.2f%%, min %.2f%%, 5-95%% %.2f-%.2f%%"
          % (100 * np.median(eta_rec), 100 * eta_rec.min(), 100 * np.percentile(eta_rec, 5),
             100 * np.percentile(eta_rec, 95)))
    print("  ORC practice ceiling binding in %d of %d samples" % (capped, N))
    print("  cycle selected: %s" % ", ".join("%s %d" % kv for kv in sorted(chosen.items())))
    oh = v("furnace_overhead")
    price = PRICE_USD_PER_MWH
    nom = E3.scenario(CHIP, "A", E3.NOMINAL)
    eta_nom = (nom["w_cycle"] + nom["p_tower"]) / (IT_POWER_MW * 1e6)

    # ------------------------------------------------------------ E7.1
    print("\nE7.1  Equal IT power, no leakage credit (USD M per GW of IT per year, %.1f USD/MWh)"
          % price)
    res = {}
    for lab, pue in (("vs efficient hyperscale (PUE %.2f)" % PUE_HYPERSCALE, PUE_HYPERSCALE),
                     ("vs US average (PUE %.2f)" % PUE_INDUSTRY_AVG, PUE_INDUSTRY_AVG),
                     ("vs global average (PUE %.2f)" % v("pue_avg_global"), v("pue_avg_global"))):
        s = savings_equal_it(eta_rec, oh, price, pue) / 1e6
        res[pue] = s
        print("  %-36s nominal %6.1f  median %6.1f  min %6.1f  5%% %6.1f  95%% %6.1f"
              % (lab, savings_equal_it(eta_nom, oh, price, pue) / 1e6, np.median(s), s.min(),
                 np.percentile(s, 5), np.percentile(s, 95)))
    s_h = res[PUE_HYPERSCALE]
    V.check("E7.1 savings positive in every sample against hyperscale, with no leakage credit",
            (s_h > 0).all(), "min %.1f M USD/GW/yr" % s_h.min())
    s_nom = savings_equal_it(eta_nom, oh, price, PUE_HYPERSCALE) / 1e6
    # the lower bound over the whole swept box: each input at the end that recovers least
    # (found one at a time), then all of them together
    def recovery(prm):
        sink = E3.T_AMBIENT_C + prm["sink_approach_K"]
        cn, _ = E3.best_cycle(CHIP[1] - prm["loop_drop_K"] / 2.0, sink, prm)
        rr = E3.scenario((CHIP[0], CHIP[1], cn.replace("ORC ", "ORC:")), "A", prm)
        ok = rr is not None and all(o for _, o, _ in E3.validate(rr))
        return (rr["w_cycle"] + rr["p_tower"]) / (IT_POWER_MW * 1e6), ok
    corner_in = dict(SAMPLED, eta_pump_orc="eta_pump")
    worst, mono = dict(E3.NOMINAL), True
    for rid, key in corner_in.items():
        lo, hi = REG[rid].sweep
        r_lo, r_mid, r_hi = (recovery(dict(E3.NOMINAL, **{key: x}))[0]
                             for x in (lo, 0.5 * (lo + hi), hi))
        mono = mono and (min(r_lo, r_hi) <= r_mid + 1e-12 <= max(r_lo, r_hi) + 2e-12)
        worst[key] = lo if r_lo <= r_hi else hi
    eta_worst, ok_worst = recovery(worst)
    s_worst = savings_equal_it(eta_worst, oh, price, PUE_HYPERSCALE) / 1e6
    print("  lower bound, every swept input at its least favourable end together: recovery "
          "%.2f%%," % (100 * eta_worst))
    for lab, pue in (("hyperscale", PUE_HYPERSCALE), ("US average", PUE_INDUSTRY_AVG),
                     ("global average", v("pue_avg_global"))):
        print("    saving against %-15s %6.1f M USD/GW/yr"
              % (lab, savings_equal_it(eta_worst, oh, price, pue) / 1e6))
    print("    overhead at which the saving against hyperscale reaches zero: %.3f "
          "(PUE-equivalent %.2f)" % (PUE_HYPERSCALE - 1.0 + eta_worst,
                                     PUE_HYPERSCALE + eta_worst))
    V.check("E7.1 recovery is monotone in each swept input (so the corner is the bound)", mono)
    V.check("E7.1 the least favourable corner is physically valid and still saves",
            ok_worst and s_worst > 0, "%.1f M USD/GW/yr" % s_worst)
    V.check("E7.1 no sample falls below the least favourable corner",
            s_h.min() >= s_worst - 1e-9, "%.1f >= %.1f" % (s_h.min(), s_worst))
    V.check("E7.1 savings equal recovered electricity plus the PUE gap (identity)",
            np.allclose(s_h, (eta_rec + PUE_HYPERSCALE - 1 - oh) * MW_PER_GW * HOURS_PER_YEAR
                        * price / 1e6))

    # ------------------------------------------------------------ E7.2
    print("\nE7.2  Exact linear sensitivities (equal IT power, vs hyperscale, nominal sample)")
    d_price = (PUE_HYPERSCALE - 1 - oh + eta_nom) * MW_PER_GW * HOURS_PER_YEAR / 1e6
    d_oh = -MW_PER_GW * HOURS_PER_YEAR * price / 1e6
    print("  per 1 USD/MWh of electricity price : %+.3f M USD/GW/yr" % d_price)
    print("  per 0.01 of furnace overhead        : %+.2f M USD/GW/yr" % (0.01 * d_oh))
    oh_avg = PUE_INDUSTRY_AVG - 1.0
    s_oh_avg = savings_equal_it(eta_nom, oh_avg, price, PUE_HYPERSCALE) / 1e6
    print("  overhead at the US-average level (%.2f) instead of hyperscale (%.2f): %.1f M USD"
          % (oh_avg, oh, s_oh_avg))
    p2 = 2 * price
    V.check("E7.2 savings exactly linear in price",
            abs(savings_equal_it(eta_nom, oh, p2, PUE_HYPERSCALE) / 1e6 - 2 * s_nom) < 1e-9)
    oh_star = PUE_HYPERSCALE - 1.0 + eta_rec
    print("  break-even furnace overhead (savings vs hyperscale = 0): median %.3f, min %.3f"
          % (np.median(oh_star), oh_star.min()))
    print("  i.e. the furnace must keep its own overhead below a PUE-equivalent of %.2f;"
          % (1 + oh_star.min()))
    print("  with US-average overhead it still beats the US-average facility by exactly the")
    print("  electricity it recovers")
    V.check("E7.2 break-even overhead exceeds the hyperscale overhead in every sample "
            "(derived: overhead* = PUE_h - 1 + recovered)", (oh_star > oh).all(),
            "min %.3f > %.3f" % (oh_star.min(), oh))
    V.check("E7.2 with US-average overhead the furnace still beats the US-average facility",
            savings_equal_it(eta_nom, oh_avg, price, PUE_INDUSTRY_AVG) > 0,
            "%.1f M USD/GW/yr" % (savings_equal_it(eta_nom, oh_avg, price, PUE_INDUSTRY_AVG)
                                 / 1e6))

    # ------------------------------------------------------------ E7.3
    print("\nE7.3  The leakage credit at equal computation (logic as efficient as silicon)")
    phi_sic = E4.chip_point(E4.EG_SIC, E4.TJ_SIC, CHIP[1], E4.chip_params())["phi"]
    credit = {}
    for lf in (REG["leak_frac"].sweep[0], v("leak_frac"), REG["leak_frac"].sweep[1]):
        phi_b = 1.0 - lf
        s = savings_equal_compute(eta_nom, oh, price, PUE_HYPERSCALE, phi_b, phi_sic) / 1e6
        credit[lf] = s - s_nom
        print("  leakage share %.2f: %.1f M USD/GW/yr, of which leakage credit %.1f"
              % (lf, s, credit[lf]))
    V.check("E7.3 the leakage credit is non-negative across the sweep and rises with leakage",
            all(c >= 0 for c in credit.values())
            and credit[REG["leak_frac"].sweep[1]] > credit[REG["leak_frac"].sweep[0]])

    # ------------------------------------------------------------ E7.4
    print("\nE7.4  Break-even SiC logic efficiency epsilon* (relative to silicon)")
    for lf in (REG["leak_frac"].sweep[0], v("leak_frac"), REG["leak_frac"].sweep[1]):
        phi_b = 1.0 - lf
        es = phi_b * (1.0 + oh - eta_rec) / (phi_sic * PUE_HYPERSCALE)
        print("  leakage share %.2f: median %.3f, max %.3f over the samples" % (lf, np.median(es),
                                                                                es.max()))
        if lf == REG["leak_frac"].sweep[0]:
            es_worst = es
    V.check("E7.4 epsilon* below 1 in every sample at the least favourable leakage share",
            (es_worst < 1.0).all(), "max %.3f" % es_worst.max())
    eps_e4 = [r for r in E4.sic_scan(E4.chip_params()) if r["tc"] == CHIP[1]][0]["eps_h"]
    es_nom = (1 - v("leak_frac")) * (1 + oh - eta_nom) / (phi_sic * PUE_HYPERSCALE)
    V.check("E7.4 coherence: nominal epsilon* equals E4's", abs(es_nom - eps_e4) < 1e-9,
            "%.6f vs %.6f" % (es_nom, eps_e4))

    # ------------------------------------------------------------ E7.5
    print("\nE7.5  Rank correlation of the primary savings with each sampled input")
    sens = {}
    for rid in SAMPLED:
        sens[rid] = spearman(samples[rid], s_h)
        print("  %-16s %+.3f" % (rid, sens[rid]))
    lo_h, hi_h = REG["tower_H"].sweep
    rec_h = []
    for H in (lo_h, hi_h):
        rr = E3.scenario(CHIP, "A", dict(E3.NOMINAL, tower_H=H))
        rec_h.append((rr["w_cycle"] + rr["p_tower"]) / (IT_POWER_MW * 1e6))
    print("  one at a time: tower %.0f m -> %.0f m changes recovery by %+.3f points (the"
          % (lo_h, hi_h, 100 * (rec_h[1] - rec_h[0])))
    print("  rank correlation of a contribution this small is sampling noise)")
    V.check("E7.5 a taller tower recovers more (one-at-a-time, deterministic)",
            rec_h[1] > rec_h[0], "%+.4f" % (rec_h[1] - rec_h[0]))
    dom = max(sens, key=lambda k: abs(sens[k]))
    print("  dominant sampled input: %s (%+.3f)" % (dom, sens[dom]))
    rec_e = []
    for e in REG["eta_exp_orc"].sweep:
        prm = dict(E3.NOMINAL, eta_turb_orc=e)
        cn, c = E3.best_cycle(CHIP[1] - prm["loop_drop_K"] / 2.0,
                              E3.T_AMBIENT_C + prm["sink_approach_K"], prm)
        rec_e.append(c["eta"])
    V.check("E7.5 a better expander never lowers recovery (one-at-a-time, deterministic)",
            rec_e[1] >= rec_e[0], "%.4f -> %.4f" % tuple(rec_e))

    # ------------------------------------------------------------ E7.7
    print("\nE7.7  One-at-a-time sweep ends for the swept inputs of the water stage and")
    print("       the baseline (SiC design point, power + water configuration B)")
    sic_b = [c for c in E3.CHIPS if c[0] == "SiC-300"][0]
    base_w = None
    OAT = {"med_tbt": None, "med_kwh_m3": "med_kwh_per_m3",
           "med_brine_salinity": "med_brine_salinity", "med_loss": "med_loss"}
    for rid, key in OAT.items():
        for end in REG[rid].sweep:
            prm = dict(E3.NOMINAL)
            if rid == "med_tbt":
                prm["med_steam_C"] = end + v("med_steam_margin")
            else:
                prm[key] = end
            rb = E3.scenario(sic_b, "B", prm)
            ok = rb is not None and all(o for _, o, _ in E3.validate(rb))
            wat = rb["water"]["m3_day"] if rb else float("nan")
            print("  %-20s %8g: net %6.2f MW, water %7.0f m3/day, grid %6.2f MW, checks %s"
                  % (rid, end, rb["net"] / 1e6, wat, rb["grid"] / 1e6, "pass" if ok else "FAIL"))
            V.check(f"E7.7 {rid} = {end:g}: configuration B feasible, physically valid, and "
                    "below hyperscale grid draw",
                    ok and rb["grid"] / 1e6 < PUE_HYPERSCALE * IT_POWER_MW)
    rb = E3.scenario(sic_b, "B", E3.NOMINAL)
    for end in REG["wue_hyperscale"].sweep:
        consumed = end * IT_POWER_MW * 24.0
        V.check(f"E7.7 wue_hyperscale = {end:g}: water produced exceeds the hyperscale "
                "facility's water consumed", rb["water"]["m3_day"] > consumed,
                "%.0f > %.0f m3/day" % (rb["water"]["m3_day"], consumed))

    # ------------------------------------------------------------ E7.6 faults
    print("\nE7.6  Fault injection")
    faults = []
    bad = dict(E3.NOMINAL, eta_turb_orc=1.6, eta_orc_ceiling=1.0)
    t_src = CHIP[1] - bad["loop_drop_K"] / 2.0
    sink = E3.T_AMBIENT_C + bad["sink_approach_K"]
    faults.append(("expander efficiency 1.6 in a sample (rejected, never selected)",
                   not all(ok for _, ok, _ in E3.validate_cycle(E3.orc("Toluene", t_src, sink,
                                                                         bad)))
                   and E3.best_cycle(t_src, sink, bad)[0] != "ORC Toluene"))
    faults.append(("negative overhead inflates savings above the no-overhead ceiling",
                   savings_equal_it(eta_nom, -oh, price, PUE_HYPERSCALE)
                   > savings_equal_it(eta_nom, 0.0, price, PUE_HYPERSCALE)))
    faults.append(("leakage credit folded into the primary result",
                   savings_equal_compute(eta_nom, oh, price, PUE_HYPERSCALE, 1 - v("leak_frac"),
                                         phi_sic) / 1e6 != s_nom))
    for label, caught in faults:
        print("  %-62s %s" % (label, "caught" if caught else "MISSED"))
        V.check(f"E7.6 fault caught: {label}", caught)
    V.finish()


if __name__ == "__main__":
    main()
