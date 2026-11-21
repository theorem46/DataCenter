"""E6 - The best uses of the secondary energy.

Per megawatt-hour of furnace heat, what is each use worth, and which wins?

Uses compared
  grid electricity     best power cycle of E3 at the supply temperature,
                       rejecting to the ambient sink
  direct process heat  displaces natural-gas-fired heat; reachable only when
                       the coolant return exceeds the process temperature by
                       the process approach (registry approach_process). Bands:
                         plastics pyrolysis (maximal liquid yield)  registry t_pyrolysis
                         steam at three pressures                   registry steam_bands
                         amine solvent regeneration                 registry t_amine_regen
  cascade              electricity first, the cycle condensing at the process
                       temperature plus the approach, all rejected heat to
                       the process (a condensing cycle rejects all its heat
                       at or above its condensing temperature)
  hydrogen             electrolysis of the recovered electricity; no hydrogen
                       price is assumed: the break-even price at which
                       hydrogen equals selling the electricity is derived
  water                multi-effect distillation on rejected heat (E3 config
                       B, or C where no cycle is feasible), at the benchmark
                       desalinated-water price range

Per megawatt-hour of heat, every process-heat use is worth the same: the gas
and carbon it displaces, divided by the efficiency of the gas-fired boiler it
replaces. Bands differ only in the temperature they need, which decides which
chips can serve them. Electricity against heat is decided by the ratio of
electricity to gas prices, so break-even electricity prices are derived.

Energy basis: Henry Hub, TTF (both from published USD/MMBtu series), the EPA
CO2 factor and the DOE boiler efficiency are on the higher-heating-value basis.
European values are before carbon costs, which would raise the value of heat.

Every input is read from registry.py.

Run:  python3 -I Scripts/E6_best_uses.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from conventions import Verdicts, c2k, carnot, T_AMBIENT_C, IT_POWER_MW  # noqa: E402
from registry import v, REG  # noqa: E402
import E3_cascade as E3  # noqa: E402

CO2_T_PER_MWH_GAS = v("co2_t_per_mwh_gas")
ETA_FIRED = v("eta_boiler")
APPROACH = v("approach_process")

REGIONS = {
    "US": dict(label="US (EIA industrial power, Henry Hub, no carbon price)",
               elec=v("elec_price"), gas=v("gas_us"), co2=0.0, cur="USD"),
    "EU-lo": dict(label="Europe (TTF, lowest month; before carbon costs)", elec=None,
                  gas=REG["ttf_2025"].sweep[0] / v("mwh_per_mmbtu"), co2=0.0, cur="USD"),
    "EU": dict(label="Europe (TTF, 2025 average; before carbon costs)", elec=None,
               gas=v("gas_eu"), co2=0.0, cur="USD"),
    "EU-hi": dict(label="Europe (TTF, highest month; before carbon costs)", elec=None,
                  gas=REG["ttf_2025"].sweep[1] / v("mwh_per_mmbtu"), co2=0.0, cur="USD"),
}
LOOP_DROP = v("loop_drop")
BANDS = ([("plastics pyrolysis", v("t_pyrolysis"))]
         + [("steam %.1f bar(a)" % p, t) for t, p in
            sorted(zip(v("steam_bands"), v("steam_sat_bar")), reverse=True)]
         + [("amine solvent regeneration", v("t_amine_regen"))])
SUPPLIES = [(name, t) for name, t, _ in E3.CHIPS]


def inputs_ok(reg, eta_fired=ETA_FIRED):
    """First-law and sign sanity of the valuation inputs."""
    return 0 < eta_fired <= 1.0 and reg["gas"] >= 0 and reg["co2"] >= 0


def heat_value(reg, eta_fired=ETA_FIRED):
    """Value of 1 MWh of delivered heat displacing gas-fired heat."""
    return (reg["gas"] + CO2_T_PER_MWH_GAS * reg["co2"]) / eta_fired


def reach(t_supply):
    """Process bands a supply can serve, hottest first. The coolant leaves the chips at
    t_supply and returns LOOP_DROP cooler; the return must still exceed the process
    temperature by the approach."""
    return [(b, tr) for b, tr in BANDS if t_supply - LOOP_DROP >= tr + APPROACH]


def cycle_to(t_supply, t_cond, prm=E3.NOMINAL):
    """Best cycle from the supply (mean loop temperature) to a condenser."""
    t_src = t_supply - prm["loop_drop_K"] / 2.0
    name, c = E3.best_cycle(t_src, t_cond, prm)
    return (name, c["eta"]) if c else ("none", 0.0)


def bounded(kind, val, t_supply, reg, eta=None):
    """Physical bound on a value per MWh of heat: electricity cannot exceed the
    Carnot fraction of the heat; delivered heat cannot exceed one MWh."""
    cmax = carnot(c2k(t_supply), c2k(T_AMBIENT_C))
    if kind == "elec":
        return 0 <= val and (eta is None or eta < cmax) and val <= cmax * reg["elec"] + 1e-9
    if kind == "heat":
        return 0 <= val <= heat_value(reg) + 1e-9
    if kind == "cascade":
        return 0 <= val <= cmax * reg["elec"] + heat_value(reg) + 1e-9
    return val >= 0


def main():
    V = Verdicts("APPENDIX E6")
    us = REGIONS["US"]
    sink = T_AMBIENT_C + E3.NOMINAL["sink_approach_K"]
    print("E6  THE BEST USES OF THE SECONDARY ENERGY (value per MWh of furnace heat)")
    print("gas CO2 factor %.4f t/MWh; boiler efficiency %.3f; electrolysis %.0f kWh/kg "
          "(range %s)" % (CO2_T_PER_MWH_GAS, ETA_FIRED, v("kwh_per_kg_h2"),
                          REG["kwh_per_kg_h2"].sweep))
    for k, reg in REGIONS.items():
        V.check(f"E6.0 {k}: valuation inputs obey the first law and sign conventions",
                inputs_ok(reg))

    # ------------------------------------------------------------ E6.1
    print("\nE6.1  Which processes each chip class can reach (coolant return >= required + %.0f K)"
          % APPROACH)
    for b, tr in BANDS:
        print("  %-30s %5.0f degC" % (b, tr))
    rch = {}
    for sname, ts in SUPPLIES:
        rch[sname] = [b for b, _ in reach(ts)]
        print("  %-8s %5.1f degC: %s" % (sname, ts, "; ".join(rch[sname]) or "no process band"))
    hottest = max(ts for _, ts in SUPPLIES)
    V.check("E6.1 plastics pyrolysis is beyond every chip class within the demonstrated "
            "SiC junction limit (derived finding)",
            all("plastics pyrolysis" not in r for r in rch.values()),
            "needs coolant %.0f degC, i.e. Tj %.0f degC at Rth %.3f, P %.0f W; "
            "demonstrated %.0f degC" % (v("t_pyrolysis") + APPROACH + LOOP_DROP,
                                       v("t_pyrolysis") + APPROACH + LOOP_DROP
                                       + v("rth") * v("h100_tdp"),
                                       v("rth"), v("h100_tdp"), v("tj_max_sic")))
    V.check("E6.1 pyrolysis unreachable at both ends of its published temperature range",
            all(max(ts for _, ts in SUPPLIES) - LOOP_DROP < end + APPROACH
                for end in REG["t_pyrolysis"].sweep),
            "range %s degC" % (REG["t_pyrolysis"].sweep,))
    V.check("E6.1 silicon reaches no steam or process band", rch["Si"] == [],
            "%.1f degC" % dict(SUPPLIES)["Si"])
    V.check("E6.1 a hotter supply reaches every band a cooler one reaches",
            all(set(rch[a]) <= set(rch[b]) for (a, ta) in SUPPLIES for (b, tb) in SUPPLIES
                if ta <= tb))
    V.check("E6.1 the SiC design point reaches every steam band and amine regeneration",
            all(b in rch["SiC-300"] for b, tr in BANDS if b != "plastics pyrolysis"))

    # ------------------------------------------------------------ E6.2
    hv = heat_value(us)
    print("\nE6.2  Value per MWh of heat, US prices (electricity %.1f, gas %.2f USD/MWh)"
          % (us["elec"], us["gas"]))
    rows = {}
    for sname, ts in SUPPLIES:
        opts = []
        cyc, eta_full = cycle_to(ts, sink)
        opts.append(("grid electricity (%s, %.1f%%)" % (cyc, 100 * eta_full), "elec",
                     eta_full * us["elec"], eta_full))
        bands = reach(ts)
        if bands:
            opts.append(("direct process heat", "heat", hv, None))
            for b, tr in bands:
                cname, eta_c = cycle_to(ts, tr + APPROACH)
                if eta_c > 0:
                    opts.append(("cascade: power (%s, %.1f%%) -> %s" % (cname, 100 * eta_c, b),
                                 "cascade", eta_c * us["elec"] + (1 - eta_c) * hv, eta_c))
        chip = [c for c in E3.CHIPS if c[0] == sname][0]
        rb = E3.scenario(chip, "B", E3.NOMINAL) or E3.scenario(chip, "C", E3.NOMINAL)
        net_e = rb["net"] / 1e6 / IT_POWER_MW
        water = rb["water"]["m3_day"] / 24.0 / IT_POWER_MW
        wl = "power + water" if rb["config"] == "B" else "water first (MED on chip heat)"
        for p_w in REG["water_price"].sweep:
            opts.append(("%s at %.2f USD/m3" % (wl, p_w), "water", net_e * us["elec"] + water * p_w,
                         None))
        opts.sort(key=lambda o: -o[2])
        rows[sname] = opts
        print("  %s (%.1f degC):" % (sname, ts))
        for name, kind, val, _ in opts:
            print("    %-62s %8.2f" % (name, val))
        for name, kind, val, eta in opts:
            V.check(f"E6.2 {sname}: {name} within its physical bound",
                    bounded(kind, val, ts, us, eta), "%.2f" % val)
    best = {s: rows[s][0][0] for s in rows}
    V.check("E6.2 at US prices, every SiC class earns most from an electricity-led option",
            all(rows[s][0][1] in ("elec", "cascade", "water") and "water first" not in rows[s][0][0]
                for s in ("SiC-300", "SiC-max")), "; ".join(best.values()))
    e300 = cycle_to(v("t_sic_design"), sink)[1]
    V.check("E6.2 at US prices, grid electricity beats direct process heat at the SiC "
            "design point", e300 * us["elec"] > hv, "%.2f vs %.2f" % (e300 * us["elec"], hv))
    h2 = [us["elec"] * k / 1000.0 for k in REG["kwh_per_kg_h2"].sweep]
    print("  hydrogen equals selling the electricity at %.2f-%.2f USD/kg (electrolysis %s kWh/kg);"
          % (h2[0], h2[1], REG["kwh_per_kg_h2"].sweep))
    print("  it is worth more only above that price")
    V.check("E6.2 hydrogen break-even = electricity price x electrolysis energy (derived)",
            all(abs(h - us["elec"] * k / 1000.0) < 1e-12
                for h, k in zip(h2, REG["kwh_per_kg_h2"].sweep)))

    # ------------------------------------------------------------ E6.3
    print("\nE6.3  Break-even electricity price above which power beats direct heat")
    print("  %-54s %12s %16s %16s" % ("region", "heat value", "%.0f degC" % v("t_sic_design"),
                                      "%.1f degC" % v("t_coolant_sic_max")))
    emax = cycle_to(v("t_coolant_sic_max"), sink)[1]
    be = {}
    for k, reg in REGIONS.items():
        hvr = heat_value(reg)
        be[k] = (hvr / e300, hvr / emax)
        print("  %-54s %s %7.1f %s %11.1f %s %11.1f" % (reg["label"], reg["cur"], hvr,
                                                      reg["cur"], be[k][0], reg["cur"], be[k][1]))
    V.check("E6.3 US: break-even below the EIA industrial price (electricity wins)",
            be["US"][0] < us["elec"], "%.1f < %.1f USD/MWh" % (be["US"][0], us["elec"]))
    V.check("E6.3 higher gas price raises the break-even",
            be["EU-hi"][0] > be["EU"][0] > be["EU-lo"][0] > be["US"][0] > 0)
    V.check("E6.3 a hotter supply lowers the break-even (better cycle)",
            all(b[1] < b[0] for b in be.values()))
    print("  where the local industrial electricity price lies below the break-even, the")
    print("  furnace heat is worth more delivered as heat than converted to power")

    # ------------------------------------------------------------ E6.4
    print("\nE6.4  Plastics or oil? Per MWh of heat every band is worth the displaced fuel:")
    for k, reg in REGIONS.items():
        print("  %-54s %s %.2f per MWh (gas %.2f + carbon %.2f, / %.3f)" % (
            reg["label"], reg["cur"], heat_value(reg), reg["gas"], CO2_T_PER_MWH_GAS * reg["co2"],
            ETA_FIRED))
    print("  the choice between bands is set by temperature (E6.1) and by the value of the")
    print("  product each band enables, which lies outside an energy valuation")

    # ------------------------------------------------------------ E6.5 faults
    print("\nE6.5  Fault injection (through the same functions)")
    t_si = dict(SUPPLIES)["Si"]
    faults = [
        ("boiler efficiency 1.2 (heat worth more than its fuel)",
         not inputs_ok(us, eta_fired=1.2)),
        ("electricity at the SiC design point valued at 60% conversion",
         not bounded("elec", 0.6 * us["elec"], v("t_sic_design"), us, 0.6)),
        ("silicon heat assigned to plastics pyrolysis",
         ("plastics pyrolysis", v("t_pyrolysis")) not in reach(t_si)),
        ("negative carbon price", not inputs_ok(dict(us, co2=-1.0))),
        ("heat credited at twice its displaced-fuel value",
         not bounded("heat", 2 * hv, v("t_sic_design"), us)),
    ]
    for label, caught in faults:
        print("  %-62s %s" % (label, "caught" if caught else "MISSED"))
        V.check(f"E6.5 fault caught: {label}", caught)
    V.finish()


if __name__ == "__main__":
    main()
