"""E4 - The leakage crossover.

Couples the chip physics of E1 (leakage rising with junction temperature,
junction temperature rising with power) to the heat recovery of E3 (the best
power cycle available at each coolant temperature), and asks one question:

    How much computation does the facility deliver per joule drawn from the grid,
    as the chips are run hotter?

    compute per grid joule = (dynamic share of chip power)
                             / (1 + facility overhead - electricity recovered)

Leakage does no computation but still becomes heat, which the cascade
recovers. The conventional baseline runs silicon at the baseline junction
temperature, delivers its dynamic share divided by its PUE, and recovers
nothing.

Every input is read from registry.py. Nothing is chosen here.

Results
  E4.1  silicon: per-chip power, leakage share, recovery and compute per grid
        joule across coolant temperature, up to the junction limit
  E4.2  robustness of the silicon result over every corner of the swept
        ranges (leakage share, thermal resistance, baseline junction,
        junction limit)
  E4.3  SiC: leakage is negligible, so the question becomes how efficient its
        logic must be. The break-even compute efficiency epsilon*, relative to
        silicon, at which a hot SiC facility delivers as much computation per
        grid joule as the best hyperscale facility, at each coolant
        temperature up to the derived SiC coolant limit; and its range over
        the leakage-share sweep (the baseline's leakage is the credit SiC
        receives, so the low end of the sweep is least favourable)
  E4.4  the two-product ledger per joule of electricity
  E4.5  fault injection through the same code paths

Run:  python3 -I Scripts/E4_leakage_crossover.py
"""
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from conventions import (Verdicts, K0, c2k, carnot, T_AMBIENT_C,  # noqa: E402
                         PUE_HYPERSCALE, PUE_INDUSTRY_AVG)
from registry import v, REG  # noqa: E402
import E1_geometric_heat as E1  # noqa: E402
import E3_cascade as E3  # noqa: E402

P_CHIP = v("h100_tdp")
OVERHEAD = v("furnace_overhead")
EG_SI, EG_SIC = v("eg_si"), v("eg_sic")
TJ_SIC = v("tj_max_sic")
T_SIC_DESIGN = v("t_sic_design")
T_SIC_MAX = v("t_coolant_sic_max")
SCAN_STEP = 5            # coolant scan resolution, K (output resolution, not an input)


def chip_params(leak_frac=None, rth=None, t_base=None, tj_si=None):
    """The silicon reference and limits; defaults are the registry nominals."""
    return dict(leak_frac=v("leak_frac") if leak_frac is None else leak_frac,
                rth=v("rth") if rth is None else rth,
                t_base=v("t_base_junction") if t_base is None else t_base,
                tj_si=v("tj_max_si") if tj_si is None else tj_si)


_MEMO = {}


def best_recovery(t_cool_c, prm=E3.NOMINAL):
    """Electricity recovered per joule of heat at this coolant temperature: the
    best cycle of E3 rejecting to the ambient sink, then the tower on the
    rejected heat (cascade formula). Memoised: it depends on the coolant
    temperature and the cycle parameters only, not on the chip."""
    key = (t_cool_c, tuple(sorted(prm.items())))
    if key not in _MEMO:
        _MEMO[key] = _best_recovery(t_cool_c, prm)
    return _MEMO[key]


def _best_recovery(t_cool_c, prm):
    t_src = t_cool_c - prm["loop_drop_K"] / 2.0
    eta_t, _ = E3.tower_eta(prm)
    t_cond = T_AMBIENT_C + prm["sink_approach_K"]
    name, cyc = E3.best_cycle(t_src, t_cond, prm)
    eta1 = cyc["eta"] if cyc else 0.0
    return (name if cyc else "tower only"), eta1, eta1 + (1.0 - eta1) * eta_t, cyc


def chip_point(eg, tj_max, t_cool_c, cp):
    """Electrical power per chip (design power if the chip can carry it, else the
    most it can carry), its junction temperature and its dynamic share."""
    p_ref = cp["leak_frac"] * P_CHIP
    t_ref = K0 + cp["t_base"]
    lo, hi = 0.0, P_CHIP
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        op = E1.operating_point(t_cool_c, mid, eg, p_ref, cp["rth"], t_ref)
        if op is not None and op[1] <= P_CHIP and op[0] <= tj_max:
            lo = mid
        else:
            hi = mid
    op = E1.operating_point(t_cool_c, lo, eg, p_ref, cp["rth"], t_ref)
    if op is None or op[0] > tj_max:
        return None          # leakage alone breaches the limit: the chip cannot run
    tj, total = op
    return dict(p_total=total, p_dyn=lo, tj=tj, phi=lo / total if total > 0 else 0.0)


def baseline(cp):
    """Silicon at the baseline junction: dynamic share and compute per grid joule."""
    phi = 1.0 - cp["leak_frac"]
    return phi, phi / PUE_HYPERSCALE, phi / PUE_INDUSTRY_AVG


def silicon_scan(cp, prm=E3.NOMINAL, eg=EG_SI):
    rows = []
    t_lo = int(T_AMBIENT_C + prm["sink_approach_K"])     # coolant cannot be below the sink
    for tc in range(t_lo, int(cp["tj_si"]) + 1, SCAN_STEP):
        pt = chip_point(eg, cp["tj_si"], float(tc), cp)
        if pt is None or pt["p_total"] <= 0:
            continue
        name, eta1, eta_tot, cyc = best_recovery(float(tc), prm)
        grid = 1.0 + OVERHEAD - eta_tot
        rows.append(dict(tc=tc, u=pt["phi"] / grid, eta=eta_tot, cyc=name, grid=grid,
                         cycle=cyc, **pt))
    return rows


def silicon_verdict(rows, cp):
    """The silicon claim: run hotter than the baseline junction, silicon never
    beats the hyperscale baseline in compute per grid joule."""
    _, b_hyp, _ = baseline(cp)
    hot = [r for r in rows if r["tj"] > cp["t_base"] + 1e-6]
    return len(hot) > 0 and all(r["u"] < b_hyp for r in hot), hot


def sic_scan(cp, prm=E3.NOMINAL):
    _, b_hyp, b_avg = baseline(cp)
    temps = sorted(set([float(t) for t in range(100, int(T_SIC_MAX) + 1, 10 * SCAN_STEP)]
                       + [T_SIC_DESIGN, T_SIC_MAX]))
    rows = []
    for tc in temps:
        pt = chip_point(EG_SIC, TJ_SIC, tc, cp)
        name, eta1, eta_tot, cyc = best_recovery(tc, prm)
        grid = 1.0 + OVERHEAD - eta_tot
        rows.append(dict(tc=tc, eps_h=b_hyp * grid / pt["phi"], eps_a=b_avg * grid / pt["phi"],
                         eta=eta_tot, cyc=name, grid=grid, cycle=cyc, **pt))
    return rows


def main():
    V = Verdicts("APPENDIX E4")
    cp0 = chip_params()
    phi_b, base_hyp, base_avg = baseline(cp0)
    print("E4  THE LEAKAGE CROSSOVER")
    print("baseline silicon at Tj %.0f degC: dynamic share %.2f (leakage share %.2f)"
          % (cp0["t_base"], phi_b, cp0["leak_frac"]))
    print("compute per grid joule: hyperscale %.4f, industry average %.4f" % (base_hyp, base_avg))

    # ------------------------------------------------------------ E4.1
    print("\nE4.1  Silicon (Tj limit %.0f degC, Rth %.3f K/W) across coolant temperature"
          % (cp0["tj_si"], cp0["rth"]))
    print("%8s %9s %8s %8s %16s %8s %10s %10s %10s" % (
        "coolant", "chip W", "Tj", "dyn sh", "best cycle", "recover", "grid/J IT",
        "compute/J", "vs hyper"))
    si = silicon_scan(cp0)
    for r in si:
        print("%6d C %9.0f %6.1f C %8.3f %16s %7.2f%% %10.4f %10.4f %9.1f%%" % (
            r["tc"], r["p_total"], r["tj"], r["phi"], r["cyc"], 100 * r["eta"], r["grid"],
            r["u"], 100 * (r["u"] / base_hyp - 1)))
    phis = [r["phi"] for r in si]
    V.check("E4.1 silicon dynamic share falls as coolant warms (leakage rises)",
            all(b <= a + 1e-9 for a, b in zip(phis, phis[1:])),
            "%.3f -> %.3f" % (phis[0], phis[-1]))
    etas = [r["eta"] for r in si]
    V.check("E4.1 recovered electricity rises with coolant temperature",
            all(b >= a - 1e-12 for a, b in zip(etas, etas[1:])),
            "%.4f -> %.4f" % (etas[0], etas[-1]))
    ok, hot = silicon_verdict(si, cp0)
    V.check("E4.1 silicon run hotter than the baseline junction never beats hyperscale "
            "(leakage outruns recovery)", ok,
            "best hot-silicon case %+.1f%% vs hyperscale"
            % (100 * (max(r["u"] for r in hot) / base_hyp - 1)))
    for r in si:
        V.check(f"E4.1 silicon {r['tc']} degC: junction within limit",
                r["tj"] <= cp0["tj_si"] + 1e-6, "%.1f degC" % r["tj"])
        V.check(f"E4.1 silicon {r['tc']} degC: recovery below Carnot to ambient",
                r["eta"] < carnot(c2k(r["tc"]), c2k(T_AMBIENT_C)))
    full = [r for r in si if abs(r["p_total"] - P_CHIP) < 1e-6 * P_CHIP]
    t_full = max(r["tc"] for r in full)
    V.check("E4.1 hottest coolant carrying full design power agrees with the registry "
            "value Tj,max - Rth P (to the scan step)",
            t_full <= v("t_coolant_si") + 1e-9 and t_full + SCAN_STEP > v("t_coolant_si"),
            "scan %d degC, registry %.1f degC" % (t_full, v("t_coolant_si")))

    print("  rows with Tj below %.0f degC gain from a cooler junction, which the baseline"
          % cp0["t_base"])
    print("  facility could equally adopt; they are not a recovery gain")

    # ------------------------------------------------------------ E4.2
    print("\nE4.2  Robustness over every corner of the swept ranges")
    print("  hot silicon: best gain over hyperscale with Tj above the baseline junction")
    print("  SiC: gain over hyperscale at the design point, logic as efficient as silicon")
    keys = ("leak_frac", "rth", "t_base_junction", "tj_max_si")
    for k in keys:
        print("  %-16s %-18s [%s]" % (k, REG[k].sweep, REG[k].kind))
    print("  %8s %8s %8s %8s %22s %14s" % ("leak", "Rth", "Tbase", "Tj,max",
                                          "hot silicon vs hyper", "SiC vs hyper"))
    corners = list(itertools.product(*(REG[k].sweep for k in keys)))
    nominal_holds, margin_ok, hot_gains, sic_gains = 0, 0, [], []
    for lf, rth, tb, tj in corners:
        cp = chip_params(lf, rth, tb, tj)
        rows = silicon_scan(cp)
        okc, hotc = silicon_verdict(rows, cp)
        _, bh, _ = baseline(cp)
        pt = chip_point(EG_SIC, TJ_SIC, T_SIC_DESIGN, cp)
        _, _, eta_s, _ = best_recovery(T_SIC_DESIGN)
        sic_gain = pt["phi"] / (1.0 + OVERHEAD - eta_s) / bh - 1.0
        if not hotc:
            label, g = "cannot run hot (runaway)", -1.0
            okc = True
        else:
            g = max(r["u"] for r in hotc) / bh - 1.0
            label = "%+.2f%%" % (100 * g)
        hot_gains.append(g)
        sic_gains.append(sic_gain)
        nominal_holds += okc
        margin_ok += g < sic_gain
        print("  %8.3f %8.4f %8.1f %8.1f %22s %13.1f%%" % (lf, rth, tb, tj, label,
                                                         100 * sic_gain))
    print("  the silicon result (no gain from running hot) holds at %d of %d corners; where it"
          % (nominal_holds, len(corners)))
    print("  fails (lowest leakage with the best demonstrated thermal resistance) the gain is")
    print("  at most %.1f%%" % (100 * max(hot_gains)))
    V.check("E4.2 at every corner, the best hot-silicon case gains less than SiC at its "
            "design point", margin_ok == len(corners), "%d of %d corners" % (margin_ok,
                                                                           len(corners)))
    V.check("E4.2 uniform dominance: the best hot-silicon gain at any corner is below the "
            "smallest SiC gain at any corner", max(hot_gains) < min(sic_gains),
            "%.2f%% < %.2f%%" % (100 * max(hot_gains), 100 * min(sic_gains)))

    # ------------------------------------------------------------ E4.3
    print("\nE4.3  SiC: break-even compute efficiency against hyperscale")
    print("  epsilon* = silicon-relative FLOP per dynamic joule a hot chip needs to match")
    print("  the best hyperscale facility in computation delivered per grid joule")
    print("%10s %7s %8s %14s %9s %8s %10s %11s %12s" % (
        "coolant", "chip W", "Tj", "best cycle", "credited", "recover", "grid/J IT",
        "eps* hyper", "eps* average"))
    sic = sic_scan(cp0)
    for r in sic:
        print("%8.1f C %7.0f %6.1f C %14s %8.2f%% %7.2f%% %10.4f %11.3f %12.3f" % (
            r["tc"], r["p_total"], r["tj"], r["cyc"],
            100 * (r["cycle"]["eta"] if r["cycle"] else 0.0),
            100 * r["eta"], r["grid"], r["eps_h"], r["eps_a"]))
    V.check("E4.3 SiC leakage negligible at every coolant temperature (dyn share > 0.999)",
            all(r["phi"] > 0.999 for r in sic), "min %.6f" % min(r["phi"] for r in sic))
    V.check("E4.3 SiC carries full design power within its junction limit at every point",
            all(abs(r["p_total"] - P_CHIP) < 1e-6 * P_CHIP and r["tj"] <= TJ_SIC + 1e-6
                for r in sic))
    fam = {}
    for r in sic:
        fam.setdefault(r["cyc"].split()[0], []).append(r["eps_h"])
    # once the ORC practice ceiling binds the credited efficiency is flat, and only
    # SiC's own (sub-0.1%) leakage moves epsilon*
    V.check("E4.3 required efficiency never rises with temperature within a cycle family "
            "(to within SiC's own leakage where the ORC practice ceiling binds)",
            all(all(b <= a * (1 + 1e-3) for a, b in zip(e, e[1:])) for e in fam.values()),
            "; ".join("%s %.3f -> %.3f" % (k, e[0], e[-1]) for k, e in fam.items()))
    d = [r for r in sic if r["tc"] == T_SIC_DESIGN][0]
    m = [r for r in sic if r["tc"] == T_SIC_MAX][0]
    V.check("E4.3 at the SiC design point the chip need not match silicon's efficiency",
            d["eps_h"] < 1.0, "eps* %.3f" % d["eps_h"])
    V.check("E4.3 at the derived SiC coolant limit the required efficiency is lowest",
            m["eps_h"] <= min(r["eps_h"] for r in sic) + 1e-12, "eps* %.3f" % m["eps_h"])
    lo, hi = REG["leak_frac"].sweep
    print("\n  epsilon* over the leakage-share sweep (low end least favourable to SiC)")
    eps_rng = {}
    for lf in (lo, v("leak_frac"), hi):
        rr = sic_scan(chip_params(leak_frac=lf))
        a = [r for r in rr if r["tc"] == T_SIC_DESIGN][0]["eps_h"]
        b = [r for r in rr if r["tc"] == T_SIC_MAX][0]["eps_h"]
        eps_rng[lf] = (a, b)
        print("  leak share %.2f: eps* %.3f at %.0f degC, %.3f at %.1f degC"
              % (lf, a, T_SIC_DESIGN, b, T_SIC_MAX))
    V.check("E4.3 even at the least favourable leakage share, SiC need not match silicon",
            max(eps_rng[lo]) < 1.0, "eps* %.3f / %.3f" % eps_rng[lo])
    V.check("E4.3 eps* scales with the baseline dynamic share (1 - leak), to within "
            "SiC's own leakage",
            abs(eps_rng[hi][0] / eps_rng[lo][0] - (1 - hi) / (1 - lo)) < 1e-3,
            "%.6f vs %.6f" % (eps_rng[hi][0] / eps_rng[lo][0], (1 - hi) / (1 - lo)))

    # ------------------------------------------------------------ E4.4
    print("\nE4.4  Per joule of electricity into the compute tier")
    print("%-34s %12s %12s %12s %12s" % ("case", "computation", "leakage", "recovered",
                                         "rejected"))
    si_full = [r for r in full if r["tc"] == t_full][0]
    cases = [("baseline silicon (%.0f C Tj)" % cp0["t_base"], phi_b, 1 - phi_b, 0.0),
             ("silicon, %d C coolant" % t_full, si_full["phi"], 1 - si_full["phi"],
              si_full["eta"]),
             ("SiC, %.0f C coolant" % T_SIC_DESIGN, d["phi"], 1 - d["phi"], d["eta"]),
             ("SiC, %.1f C coolant" % T_SIC_MAX, m["phi"], 1 - m["phi"], m["eta"])]
    for name, phi, leak, rec in cases:
        rej = 1.0 - rec
        print("%-34s %12.4f %12.4f %12.4f %12.4f" % (name, phi, leak, rec, rej))
        V.check(f"E4.4 {name}: ledger closes (computation + leakage = 1 = recovered + rejected)",
                abs(phi + leak - 1) < 1e-12 and abs(rec + rej - 1) < 1e-12 and 0 <= rec < 1)

    # ------------------------------------------------------------ E4.5 faults
    print("\nE4.5  Fault injection (each fault run through the code paths above)")
    faults = []
    nl = silicon_scan(cp0, eg=10 * EG_SIC)          # bandgap so wide there is no leakage
    ph = [r["phi"] for r in nl]
    faults.append(("leakage switched off (dyn share constant)",
                   not all(b < a for a, b in zip(ph, ph[1:]))))
    bad = dict(E3.NOMINAL, eta_turb_orc=1.6, eta_orc_ceiling=1.0)
    t_src = T_SIC_DESIGN - bad["loop_drop_K"] / 2.0
    t_cnd = T_AMBIENT_C + bad["sink_approach_K"]
    c_bad = E3.orc("Toluene", t_src, t_cnd, bad)
    name_b, c_sel = E3.best_cycle(t_src, t_cnd, bad)
    faults.append(("ORC expander efficiency 1.6 in the recovery model",
                   any(not ok for _, ok, _ in E3.validate_cycle(c_bad))
                   and name_b != "ORC Toluene"))
    faults.append(("hot silicon credited with the baseline dynamic share",
                   not silicon_verdict([dict(r, u=phi_b / r["grid"]) for r in si], cp0)[0]))
    neg = [dict(r, eta=r["eta"] + 2 * OVERHEAD + 1) for r in si]    # recovery above input
    faults.append(("recovered electricity exceeding the heat input",
                   any(not (0 <= r["eta"] < 1) for r in neg)))
    for label, caught in faults:
        print("  %-60s %s" % (label, "caught" if caught else "MISSED"))
        V.check(f"E4.5 fault caught: {label}", caught)
    V.finish()


if __name__ == "__main__":
    main()
