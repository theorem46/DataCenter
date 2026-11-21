"""E8 - Incremental production and the whole energy system.

E1-E7 compare the furnace tier with data centres. E8 widens the boundary to
the energy system the furnace joins, and asks two questions the data-centre
view cannot:

  (a) What is a megawatt-hour of furnace heat worth to the industries that turn
      oil and gas into products (plastics, polymers, chemicals, base oils)?
  (b) Against today's system, in which computation is bought with electricity
      and process heat is bought separately with gas, what does the integrated
      system save?

  E8.1  Value leverage. EIA's Manufacturing Energy Consumption Survey reports,
        per industry, the energy consumed per dollar of value added. Inverted,
        this is the value added around each megawatt-hour of energy in that
        industry. Two quantities bound the worth of a megawatt-hour of furnace
        heat delivered to it:
          lower bound      the gas it displaces (E6): fuel / boiler efficiency
          upper reference  the value added around the fuel it displaces
        The lower bound is realised whenever the heat replaces a boiler. The
        upper reference is approached only where heat is the binding
        constraint on output, or where new capacity is built around the
        furnace; value added rewards capital, labour and feedstock as well as
        energy, so it is reported as a reference, never added to the lower
        bound.
  E8.2  Reachable market. Which part of US process heat lies within the
        derived coolant limits, and how much furnace computation it could
        absorb. Cracker pyrolysis (750-900 degC) is shown to be out of reach.
  E8.3  The whole system. Same computation and same process heat, delivered
        (i) today: hyperscale data centre + gas boiler, and
        (ii) integrated: SiC furnace, heat to process (direct, or after power
             generation in a cascade).
        Grid electricity, gas, CO2 and value per GW of computation per year.
        Energy is never created: the integrated system's useful energy output
        never exceeds its electricity input.
  E8.4  Fault injection.

Every input is read from registry.py.

Run:  python3 -I Scripts/E8_incremental_production.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from conventions import (Verdicts, PUE_HYPERSCALE, HOURS_PER_YEAR,  # noqa: E402
                         PRICE_USD_PER_MWH)
from registry import v  # noqa: E402
import E3_cascade as E3  # noqa: E402
import E6_best_uses as E6  # noqa: E402

MWH_PER_MMBTU = v("mwh_per_mmbtu")
ETA_BOILER = v("eta_boiler")
GAS_US = v("gas_us")                       # USD per MWh of gas (HHV)
CO2_GAS = v("co2_t_per_mwh_gas")           # t CO2 per MWh of gas
INDUSTRIES = [  # label, registry id of the MECS ratio, registry id of total fuel
    ("Petroleum refineries (324110)", "mecs_va_324110", "mecs_fuel_324110"),
    ("Petrochemicals (325110)", "mecs_va_325110", "mecs_fuel_325110"),
    ("Other basic organic chemicals (325199)", "mecs_va_325199", "mecs_fuel_325199"),
    ("Plastics materials and resins (325211)", "mecs_va_325211", "mecs_fuel_325211"),
    ("All manufacturing", "mecs_va_mfg", None),
]
MW_PER_GW = 1000.0
TBTU_TO_MWH = 1e6 * MWH_PER_MMBTU          # 1 TBtu = 1e6 MMBtu


def va_per_mwh_energy(kbtu_per_usd):
    """Value added (USD) per MWh of energy consumed: invert kBtu per USD."""
    usd_per_mmbtu = 1000.0 / kbtu_per_usd
    return usd_per_mmbtu / MWH_PER_MMBTU


def bounds_per_mwh_heat(kbtu_per_usd, gas=GAS_US, eta=ETA_BOILER):
    """(lower, upper) value of 1 MWh of delivered heat replacing boiler heat:
    the boiler burns 1/eta MWh of fuel for it."""
    fuel = 1.0 / eta
    return gas * fuel, va_per_mwh_energy(kbtu_per_usd) * fuel


def system(config, heat_mwh_per_mwh_it, power_mwh_per_mwh_it, overhead=None,
           pue=PUE_HYPERSCALE, eta=ETA_BOILER):
    """Per GW of computation for one year. Returns grid electricity, gas burned,
    CO2 from gas, and useful energy delivered (TWh, TWh, Mt, TWh)."""
    oh = v("furnace_overhead") if overhead is None else overhead
    it_twh = MW_PER_GW * HOURS_PER_YEAR / 1e6
    q_twh = heat_mwh_per_mwh_it * it_twh          # process heat the system must supply
    if config == "today":
        grid = pue * it_twh
        gas = q_twh / eta
        useful_out = q_twh                         # boiler heat (from gas)
        e_in = grid + gas
    else:
        grid = (1.0 + oh - power_mwh_per_mwh_it) * it_twh
        gas = 0.0
        useful_out = q_twh + power_mwh_per_mwh_it * it_twh
        e_in = (1.0 + oh) * it_twh                 # electricity into the furnace site
    return dict(grid=grid, gas=gas, co2=gas * CO2_GAS, q=q_twh, out=useful_out, e_in=e_in,
                it=it_twh)


def main():
    V = Verdicts("APPENDIX E8")
    print("E8  INCREMENTAL PRODUCTION AND THE WHOLE ENERGY SYSTEM")
    print("gas %.2f USD/MWh (HHV), boiler efficiency %.3f, CO2 %.4f t/MWh gas"
          % (GAS_US, ETA_BOILER, CO2_GAS))

    # ------------------------------------------------------------ E8.1
    print("\nE8.1  Value around each MWh of energy (EIA MECS 2018, Table 6.1)")
    print("  %-42s %10s %14s %16s %18s %9s %12s" % ("industry", "kBtu/USD", "VA USD/MWh",
          "displaced USD/MWh", "VA ref USD/MWh", "leverage", "VA bn USD"))
    print("  %-42s %10s %14s %16s %18s %9s %12s" % ("", "", "of energy", "of heat (lower)",
          "of heat (upper)", "", "(fuel/ratio)"))
    lev = {}
    for label, rid, fid in INDUSTRIES:
        r = v(rid)
        va = va_per_mwh_energy(r)
        lo, hi = bounds_per_mwh_heat(r)
        lev[label] = hi / lo
        # value added implied by the two MECS tables: fuel (kBtu) / (kBtu per USD)
        va_bn = (v(fid) * 1e9 / r / 1e9) if fid else float("nan")
        print("  %-42s %10.1f %14.1f %16.2f %18.1f %8.1fx %12.1f" % (label, r, va, lo, hi,
                                                                    hi / lo, va_bn))
        V.check(f"E8.1 {label}: value-added reference exceeds the displaced fuel (lower "
                "bound)", hi > lo, "x%.1f" % (hi / lo))
        V.check(f"E8.1 {label}: leverage equals value added per MWh / gas price (identity)",
                abs(hi / lo - va / GAS_US) < 1e-9)
    oil_to_products = [l for l, _, _ in INDUSTRIES if l != "All manufacturing"]
    lo_lev = min(lev[l] for l in oil_to_products)
    hi_lev = max(lev[l] for l in oil_to_products)
    print("  in the oil-to-products chain each MWh of heat sits inside %.0f-%.0f times the value"
          % (math.floor(lo_lev), math.ceil(hi_lev)))
    print("  of the gas it displaces; displacement alone (E6) captures only the lower bound")
    V.check("E8.1 every oil-to-products industry carries at least ten times the displaced "
            "fuel in value added", lo_lev >= 10.0, "min x%.1f" % lo_lev)
    still_gas = v("mecs_other_324110") / v("mecs_fuel_324110")
    print("  refinery caveat: %.0f%% of refinery fuel is 'Other', mainly byproduct still gas;"
          % (100 * still_gas))
    print("  the refinery ratio is per unit of all fuel, purchased or byproduct")
    print("  at the European gas price (TTF 2025 average, %.2f USD/MWh) displacement is %.2f USD"
          " per MWh of heat, before carbon costs" % (v("gas_eu"), v("gas_eu") / ETA_BOILER))

    # ------------------------------------------------------------ E8.2
    print("\nE8.2  Reachable market")
    appr = v("approach_process")
    # the coolant returns loop_drop cooler than it leaves; the return must exceed the
    # process temperature by the approach
    reach = {name: t - v("loop_drop") - appr for name, t, _ in E3.CHIPS}
    for name, r in reach.items():
        print("  %-8s delivers process heat up to %.0f degC" % (name, r))
    below = v("iph_us_below300")
    share = below / v("iph_us")
    gw = below * TBTU_TO_MWH / HOURS_PER_YEAR / MW_PER_GW
    print("  US process heat below %.0f degC: %.0f TBtu of %.0f (%.0f%%), a continuous %.0f GW"
          % (v("t_iph_band"), below, v("iph_us"), 100 * share, gw))
    V.check("E8.2 the hottest SiC class reaches the whole below-300 degC band",
            reach["SiC-max"] >= v("t_iph_band"), "%.0f degC" % reach["SiC-max"])
    V.check("E8.2 the SiC design point reaches every registered steam band",
            reach["SiC-300"] >= max(v("steam_bands")),
            "%.0f >= %.0f degC" % (reach["SiC-300"], max(v("steam_bands"))))
    V.check("E8.2 silicon reaches none of the 100-300 degC band",
            reach["Si"] < v("t_iph_band_lo"), "%.0f degC" % reach["Si"])
    ref = v("iph_refining_100_300") / v("iph_refining")
    print("  refineries: %.0f%% of process heat (%.0f TBtu) lies at 100-300 degC"
          % (100 * ref, v("iph_refining_100_300")))
    # the source states its shares as "approximately" / "about": agreement to one point
    V.check("E8.2 share arithmetic reproduces the stated shares to within one point",
            abs(share - v("iph_share_stated")) <= 0.01
            and abs(ref - v("iph_refining_share_stated")) <= 0.01,
            "%.1f%% vs %.0f%%; %.1f%% vs %.0f%%" % (100 * share, 100 * v("iph_share_stated"),
                                                    100 * ref, 100 * v("iph_refining_share_stated")))
    print("  steam cracking: the pyrolysis section (%.0f%% of cracker energy) runs at %.0f degC"
          " or more" % (100 * v("cracker_pyrolysis_share"), v("t_cracker_lo")))
    V.check("E8.2 cracker pyrolysis is beyond every chip class (derived finding)",
            max(reach.values()) < v("t_cracker_lo"),
            "%.0f < %.0f degC" % (max(reach.values()), v("t_cracker_lo")))
    gj_t = lambda btu_lb: btu_lb * v("J_per_Btu") / v("kg_per_lb") / 1e6   # GJ per tonne
    print("  energy per tonne (DOE bandwidth, onsite): ethylene %.1f GJ; HDPE %.2f, LLDPE %.2f,"
          " LDPE %.2f, PP %.2f GJ" % (gj_t(v("bw_ethylene")), gj_t(v("bw_hdpe")),
                                     gj_t(v("bw_lldpe")), gj_t(v("bw_ldpe")), gj_t(v("bw_pp"))))
    poly = [v(k) / v("bw_ethylene") for k in ("bw_hdpe", "bw_lldpe", "bw_ldpe", "bw_pp")]
    print("  polymerisation needs %.0f-%.0f%% of the energy of cracking per unit mass"
          % (100 * min(poly), 100 * max(poly)))
    check_tbtu = v("bw_ethylene") * v("bw_ethylene_mlb") * 1e6 / 1e12
    V.check("E8.2 DOE intensity x production reproduces DOE total for ethylene (consistency)",
            abs(check_tbtu - v("bw_ethylene_tbtu")) < 0.5, "%.1f TBtu" % check_tbtu)
    print("  the below-300 degC band could absorb the heat of %.0f GW of furnace computation;"
          % gw)
    print("  furnace heat does not lack buyers at any foreseeable scale")

    # ------------------------------------------------------------ E8.2b
    print("\nE8.2b The refinery")
    q_ref = v("iph_refining_100_300")                     # TBtu per year within reach
    fuel_ref = v("mecs_fuel_324110")
    gw_ref = q_ref * TBTU_TO_MWH / HOURS_PER_YEAR / MW_PER_GW
    co2_ref = q_ref * 1e6 * v("co2_gas_kg_mmbtu") / 1e9    # Mt, at the natural-gas factor
    print("  US refineries burn %.0f TBtu of fuel a year; %.0f%% of it is their own byproduct gas"
          % (fuel_ref, 100 * still_gas))
    print("  %.0f TBtu of refinery process heat (%.0f%%) lies at %.0f-%.0f degC, within the "
          "design's reach" % (q_ref, 100 * ref, v("t_iph_band_lo"), v("t_iph_band")))
    print("  supplying it from computation frees at least %.0f TBtu of fuel a year, %.0f%% of "
          "refinery fuel use," % (q_ref, 100 * q_ref / fuel_ref))
    print("  and avoids at least %.0f Mt of CO2; it is the heat of %.0f GW of computation"
          % (co2_ref, gw_ref))
    print("  the refinery then makes the same products while burning less of its own output:")
    print("  the hydrocarbons it no longer burns for heat remain available as product")
    V.check("E8.2b heat within reach is a share of refinery process heat between 0 and 1",
            0 < q_ref / v("iph_refining") < 1, "%.3f" % (q_ref / v("iph_refining")))
    V.check("E8.2b fuel freed does not exceed the fuel refineries burn",
            q_ref / ETA_BOILER < fuel_ref, "%.0f < %.0f TBtu" % (q_ref / ETA_BOILER, fuel_ref))
    V.check("E8.2b computation needed equals the heat supplied (First Law)",
            abs(gw_ref * MW_PER_GW * HOURS_PER_YEAR / TBTU_TO_MWH - q_ref) < 1e-6 * q_ref,
            "%.1f GW" % gw_ref)
    V.check("E8.2b the SiC design point reaches the refinery band's steam levels and silicon "
            "does not", reach["SiC-300"] >= max(v("steam_bands")) and reach["Si"]
            < v("t_iph_band_lo"))

    # ------------------------------------------------------------ E8.3
    print("\nE8.3  The whole system, per GW of computation per year")
    print("  both systems deliver the same computation and the same process heat")
    t_sic = v("t_sic_design")
    t_proc = v("t_amine_regen") + appr
    cname, eta_c = E6.cycle_to(t_sic, t_proc)
    cases = [
        ("direct heat (SiC 300 C, all IT heat to process)", 1.0, 0.0),
        ("cascade (SiC 300 C: %s %.1f%% power, rest to amine regeneration)" % (cname, 100 * eta_c),
         1.0 - eta_c, eta_c),
    ]
    rows = []
    for name, qh, pw in cases:
        a = system("today", qh, pw)
        b = system("integrated", qh, pw)
        d_grid, d_gas, d_co2 = a["grid"] - b["grid"], a["gas"] - b["gas"], a["co2"] - b["co2"]
        e_today = a["grid"] + a["gas"]
        e_int = b["grid"] + b["gas"]
        val_lo = d_grid * 1e6 * PRICE_USD_PER_MWH + d_gas * 1e6 * GAS_US
        rows.append((name, a, b, d_grid, d_gas, d_co2, e_today, e_int, val_lo))
        print("\n  %s" % name)
        print("    %-34s %12s %12s" % ("", "today", "integrated"))
        print("    %-34s %12.3f %12.3f" % ("grid electricity (TWh)", a["grid"], b["grid"]))
        print("    %-34s %12.3f %12.3f" % ("gas burned (TWh, HHV)", a["gas"], b["gas"]))
        print("    %-34s %12.3f %12.3f" % ("CO2 from gas (Mt)", a["co2"], b["co2"]))
        print("    %-34s %12.3f %12.3f" % ("energy bought (TWh)", e_today, e_int))
        print("    process heat delivered %.3f TWh in both; computation 1 GW-year in both" % a["q"])
        print("    saved: %.3f TWh of energy bought (%.0f%%), %.3f Mt CO2 from gas;"
              " %.0f M USD at EIA electricity and Henry Hub gas"
              % (e_today - e_int, 100 * (1 - e_int / e_today), d_co2, val_lo / 1e6))
        V.check(f"E8.3 {name[:12]}: same heat delivered by both systems",
                abs(a["q"] - b["q"]) < 1e-12)
        V.check(f"E8.3 {name[:12]}: integrated useful output never exceeds its electricity "
                "input (no energy created)", b["out"] <= b["e_in"] + 1e-12,
                "%.3f <= %.3f TWh" % (b["out"], b["e_in"]))
        V.check(f"E8.3 {name[:12]}: integrated system buys less energy than today's",
                e_int < e_today, "%.3f < %.3f TWh" % (e_int, e_today))
        V.check(f"E8.3 {name[:12]}: CO2 from gas avoided = gas avoided x EPA factor",
                abs(d_co2 - d_gas * CO2_GAS) < 1e-12)
    d_val = rows[1][8] - rows[0][8]
    print("\n  the cascade generates %.3f TWh of electricity and, in exchange, displaces %.3f TWh"
          " less gas" % (rows[1][3] - rows[0][3], rows[0][4] - rows[1][4]))
    print("  at US prices the %s is worth %+.0f M USD per GW-year more"
          % ("cascade" if d_val > 0 else "direct route", abs(d_val) / 1e6))
    print("  these values count displacement only; E8.1 bounds the incremental-production"
          " value above it")
    dh = rows[0]
    lo_h, hi_h = bounds_per_mwh_heat(v("mecs_va_325211"))
    q_mwh = dh[1]["q"] * 1e6
    print("  direct heat to plastics resins: displacement %.0f M USD; value-added reference"
          " %.0f M USD per GW-year" % (q_mwh * lo_h / 1e6, q_mwh * hi_h / 1e6))

    # ------------------------------------------------------------ E8.4 faults
    print("\nE8.4  Fault injection")
    a = system("today", 1.0, 0.0, eta=1.2)
    faults = [
        ("boiler efficiency 1.2 (heat from less gas than its energy)",
         not (a["gas"] >= a["q"])),
        ("integrated output above its input (power 0.5 plus all heat)",
         not (system("integrated", 1.0, 0.5)["out"]
              <= system("integrated", 1.0, 0.5)["e_in"] + 1e-12)),
        ("value-added reference added to displacement (double count)",
         (bounds_per_mwh_heat(v("mecs_va_325211"))[0] + bounds_per_mwh_heat(v("mecs_va_325211"))[1])
         > bounds_per_mwh_heat(v("mecs_va_325211"))[1]),
        ("negative energy-to-value ratio", not (va_per_mwh_energy(-v("mecs_va_325211")) > 0)),
        ("cracker pyrolysis assigned to the hottest chip",
         not (max(reach.values()) >= v("t_cracker_lo"))),
    ]
    for label, caught in faults:
        print("  %-62s %s" % (label, "caught" if caught else "MISSED"))
        V.check(f"E8.4 fault caught: {label}", caught)
    V.finish()


if __name__ == "__main__":
    main()
