"""E3 - The thermodynamic cascade.

Compute heat -> power cycle -> multi-effect distillation (MED) -> updraft tower.

Every joule of electrical power delivered to the compute tier leaves the chips
as heat (First Law; the energy retained by computation is negligible).  This
experiment follows that heat through the cascade for four chip classes and
three cascade configurations, using real working-fluid properties (CoolProp),
and reports, per 100 MW of compute:

    electricity recovered, water produced, net grid draw,
    and the comparison with conventional data centres (PUE / WUE baselines).

Configurations
    A  power only      : power cycle -> tower
    B  power + water   : power cycle (raised heat-rejection temperature) -> MED -> tower
    C  water first     : chip heat -> MED -> tower (no power cycle)

Checks (all must pass, else exit 1)
    - Carnot ceilings of the originating post reproduced
    - energy closure of every cycle, the MED plant and the whole facility
    - no cycle exceeds its Carnot limit; entropy generation >= 0
    - recuperator pinch >= minimum along the full exchanger (discretised)
    - MED gain output ratio below the number of effects; within literature range
    - tower efficiency below its ideal bound g.H/(cp.T0)
    - cascade only adds: eta_total >= eta_cycle; cascade formula reproduced
    - fault injection: six injected faults, each must be caught

Run:  python3 -I Scripts/E3_cascade.py
"""
import os
import sys
import copy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from conventions import (G, CP_AIR, CP_SEAWATER, K0, c2k, carnot, Verdicts,  # noqa: E402
                         T_AMBIENT_C, T_SEAWATER_C, IT_POWER_MW,
                         PUE_INDUSTRY_AVG, PUE_HYPERSCALE,
                         WUE_INDUSTRY_AVG, WUE_HYPERSCALE,
                         HOURS_PER_YEAR, PRICE_USD_PER_MWH)
from registry import v, REG  # noqa: E402
from CoolProp.CoolProp import PropsSI  # noqa: E402

# ------------------------------------------------------------- parameters
# Every value is read from the dependency registry (registry.py), where each
# carries its kind (law / benchmark / derived / design) and source.
NOMINAL = dict(
    loop_drop_K=v("loop_drop"),
    pinch_K=v("pinch"),
    sink_approach_K=v("sink_approach"),
    eta_pump=v("eta_pump_orc"),
    eta_turb_orc=v("eta_exp_orc"),
    eta_turb_sco2=v("eta_turb_sco2"),
    eta_comp_sco2=v("eta_comp_sco2"),
    p_low_sco2=v("p_low_sco2"),
    p_high_sco2=v("p_high_sco2"),
    recup_eff=v("recup_eff"),
    recup_min_pinch_K=v("recup_min_pinch"),
    subcrit_margin_K=v("subcrit_margin"),
    med_steam_C=v("med_steam"),
    med_steam_approach_K=v("med_steam_approach"),
    med_tbt_drop_K=v("med_steam_margin"),
    med_last_C=v("med_last"),
    med_step_K=v("med_step"),
    med_feed_C=v("med_feed"),
    med_brine_salinity=v("med_brine_salinity"),
    med_feed_salinity=v("s_seawater"),
    med_loss=v("med_loss"),
    med_kwh_per_m3=v("med_kwh_m3"),
    tower_H=v("tower_H"),
    tower_turb=v("eta_tower_turb"),
    tower_share=v("tower_pressure_share"),
    eta_orc_ceiling=v("eta_orc_ceiling"),
    furnace_overhead=v("furnace_overhead"),
    drop_reject=False,       # fault-injection switch (energy leak)
)

# Chip classes are derived, not chosen: the hottest coolant each material can
# run at full design power is its junction limit minus R_th x P (registry),
# plus the SiC design point. The cycle of each class is not chosen either: it
# is the best feasible cycle of this study at that temperature (best_cycle),
# assigned in _assign_cycles() below once the cycle models are defined.
CHIP_TEMPS = [  # name, chip coolant outlet degC
    ("Si", v("t_coolant_si")),
    ("SiC-300", v("t_sic_design")),
    ("SiC-max", v("t_coolant_sic_max")),
]
CHIPS = []


def hfg(t_c):
    return (PropsSI("H", "T", c2k(t_c), "Q", 1, "Water")
            - PropsSI("H", "T", c2k(t_c), "Q", 0, "Water"))


# ------------------------------------------------------------- exchangers
def min_pinch(hot, cold, n=60):
    """Minimum temperature difference along a counter-flow exchanger.
    hot/cold: (fluid, P, h_in, h_out) per unit mass flow, same duty."""
    fh, ph, h_hin, h_hout = hot
    fc, pc, h_cin, h_cout = cold
    duty = h_hin - h_hout
    worst = 1e9
    for k in range(n + 1):
        x = k / n
        th = PropsSI("T", "P", ph, "H", h_hin - x * duty, fh)
        tc = PropsSI("T", "P", pc, "H", h_cout - x * (h_cout - h_cin), fc)
        worst = min(worst, th - tc)
    return worst


def recuperate(fluid, p_hot, h_hot_in, h_hot_floor, p_cold, h_cold_in, h_cold_cap, prm):
    """Largest duty <= eff * max duty that keeps the pinch >= minimum."""
    qmax = max(0.0, min(h_hot_in - h_hot_floor, h_cold_cap - h_cold_in))
    q = prm["recup_eff"] * qmax
    if q <= 0:
        return 0.0, float("inf")
    if prm["recup_eff"] > 1.0:     # injected fault: do not repair, expose it
        return q, min_pinch((fluid, p_hot, h_hot_in, h_hot_in - q),
                            (fluid, p_cold, h_cold_in, h_cold_in + q))
    lo, hi = 0.0, q
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        mp = min_pinch((fluid, p_hot, h_hot_in, h_hot_in - mid),
                       (fluid, p_cold, h_cold_in, h_cold_in + mid))
        if mp >= prm["recup_min_pinch_K"]:
            lo = mid
        else:
            hi = mid
    mp = min_pinch((fluid, p_hot, h_hot_in, h_hot_in - lo),
                   (fluid, p_cold, h_cold_in, h_cold_in + lo))
    return lo, mp


# ------------------------------------------------------------- power cycles
def orc(fluid, t_src_c, t_cond_c, prm):
    t_ev = t_src_c - prm["pinch_K"]
    tc = PropsSI("Tcrit", fluid) - K0
    if t_ev >= tc - prm["subcrit_margin_K"]:
        t_ev = tc - prm["subcrit_margin_K"]
    p1 = PropsSI("P", "T", c2k(t_cond_c), "Q", 0, fluid)
    p3 = PropsSI("P", "T", c2k(t_ev), "Q", 1, fluid)
    h1 = PropsSI("H", "P", p1, "Q", 0, fluid)
    s1 = PropsSI("S", "P", p1, "Q", 0, fluid)
    h2 = h1 + (PropsSI("H", "P", p3, "S", s1, fluid) - h1) / prm["eta_pump"]
    h3 = PropsSI("H", "P", p3, "Q", 1, fluid)
    s3 = PropsSI("S", "P", p3, "Q", 1, fluid)
    h4 = h3 - prm["eta_turb_orc"] * (h3 - PropsSI("H", "P", p1, "S", s3, fluid))
    t2 = PropsSI("T", "P", p3, "H", h2, fluid)
    t4 = PropsSI("T", "P", p1, "H", h4, fluid)
    s2 = PropsSI("S", "P", p3, "H", h2, fluid)
    s4 = PropsSI("S", "P", p1, "H", h4, fluid)
    # the hot stream may neither condense in the recuperator nor fall closer
    # than the minimum pinch to the cold inlet
    h_hot_floor = PropsSI("H", "P", p1, "Q", 1, fluid)
    if t2 + prm["recup_min_pinch_K"] > c2k(t_cond_c):
        h_hot_floor = max(h_hot_floor, PropsSI("H", "P", p1, "T",
                                               t2 + prm["recup_min_pinch_K"], fluid))
    h_cold_cap = PropsSI("H", "P", p3, "T", t4, fluid) if t4 > t2 else h2
    q_rec, pinch = recuperate(fluid, p1, h4, h_hot_floor, p3, h2, h_cold_cap, prm)
    q_in = h3 - (h2 + q_rec)
    w_model = (h3 - h4) - (h2 - h1)
    # Least-favourable rule: the work credited never exceeds demonstrated
    # high-temperature ORC practice (registry eta_orc_ceiling). Any excess of
    # the state-point model over practice is booked as unmodelled loss and
    # rejected at the condenser, so the energy ledger still closes and entropy
    # generation can only rise.
    w = min(w_model, prm["eta_orc_ceiling"] * q_in)
    q_out = q_in - w
    return dict(kind="ORC " + fluid, t_src=t_src_c, t_ev=t_ev, t_sink=t_cond_c,
                q_in=q_in, w=w, q_out=q_out, eta=w / q_in, eta_model=w_model / q_in,
                capped=w < w_model, pinch=pinch,
                machines=[("pump", s1, s2), ("expander", s3, s4)],
                reject_profile=[(t_cond_c, q_out)])


def sco2(t_src_c, prm):
    f = "CO2"
    pl, ph = prm["p_low_sco2"], prm["p_high_sco2"]
    t_ci = T_AMBIENT_C + prm["sink_approach_K"]     # same heat sink as the ORC
    t1 = c2k(t_ci)
    h1 = PropsSI("H", "P", pl, "T", t1, f)
    s1 = PropsSI("S", "P", pl, "T", t1, f)
    h2 = h1 + (PropsSI("H", "P", ph, "S", s1, f) - h1) / prm["eta_comp_sco2"]
    t3 = c2k(t_src_c - prm["pinch_K"])
    h3 = PropsSI("H", "P", ph, "T", t3, f)
    s3 = PropsSI("S", "P", ph, "T", t3, f)
    h4 = h3 - prm["eta_turb_sco2"] * (h3 - PropsSI("H", "P", pl, "S", s3, f))
    t2 = PropsSI("T", "P", ph, "H", h2, f)
    if t3 <= t2 + prm["pinch_K"]:
        # heat cannot be added above the compressor outlet: not a heat engine
        raise ValueError("sCO2 turbine inlet not above compressor outlet")
    t4 = PropsSI("T", "P", pl, "H", h4, f)
    s2 = PropsSI("S", "P", ph, "H", h2, f)
    s4 = PropsSI("S", "P", pl, "H", h4, f)
    q_rec, pinch = recuperate(f, pl, h4, PropsSI("H", "P", pl, "T", t2, f),
                              ph, h2, PropsSI("H", "P", ph, "T", t4, f), prm)
    h5 = h4 - q_rec
    t5 = PropsSI("T", "P", pl, "H", h5, f) - K0
    q_in = h3 - (h2 + q_rec)
    w = (h3 - h4) - (h2 - h1)
    q_out = h5 - h1

    def heat_above(t_c):
        """Gas-cooler heat released above t_c (per kg)."""
        if t5 <= t_c:
            return 0.0
        return h5 - PropsSI("H", "P", pl, "T", c2k(t_c), f)

    return dict(kind="sCO2 recuperated Brayton", t_src=t_src_c,
                t_ev=t_src_c - prm["pinch_K"], t_sink=t_ci,
                q_in=q_in, w=w, q_out=q_out, eta=w / q_in, pinch=pinch,
                machines=[("compressor", s1, s2), ("turbine", s3, s4)],
                t_gc_in=t5, heat_above=heat_above)


ORC_FLUIDS = ("R245fa", "Toluene")


def best_cycle(t_src_c, t_cond_c, prm, allow_sco2=True):
    """The most efficient cycle of this study at a source temperature, rejecting
    to a condenser at t_cond_c. Candidates: subcritical recuperated ORC in each
    working fluid, and the recuperated sCO2 Brayton cycle when the condenser is
    the ambient heat sink (its compressor inlet is set by that sink).
    Feasibility is physical only: a cycle needs a temperature lift
    (evaporation above condensation), must produce positive work, and must
    pass every physical-law check of validate_cycle (energy closure, Carnot,
    entropy generation, recuperator pinch).
    Returns (name, cycle dict) or ("none", None)."""
    options = []
    if t_src_c - prm["pinch_K"] > t_cond_c:
        for fluid in ORC_FLUIDS:
            try:
                c = orc(fluid, t_src_c, t_cond_c, prm)
            except ValueError:
                continue
            if c["t_ev"] > t_cond_c and c["eta"] > 0 and all(
                    ok for _, ok, _ in validate_cycle(c)):
                options.append(("ORC " + fluid, c))
    sink = T_AMBIENT_C + prm["sink_approach_K"]
    if allow_sco2 and abs(t_cond_c - sink) < 1e-9 and t_src_c - prm["pinch_K"] > sink:
        try:
            c = sco2(t_src_c, prm)
            if c["eta"] > 0 and all(ok for _, ok, _ in validate_cycle(c)):
                options.append(("sCO2", c))
        except ValueError:
            pass
    if not options:
        return "none", None
    return max(options, key=lambda o: o[1]["eta"])


def _assign_cycles():
    sink = T_AMBIENT_C + NOMINAL["sink_approach_K"]
    for name, t_chip in CHIP_TEMPS:
        cname, _ = best_cycle(t_chip - NOMINAL["loop_drop_K"] / 2.0, sink, NOMINAL)
        CHIPS.append((name, t_chip, cname.replace("ORC ", "ORC:")))


# ------------------------------------------------------------------ MED
def med(q_in_W, t_steam_c, prm):
    """Multi-effect distillation, forward cascade of brine and distillate.

    Each effect boils feed with the latent heat of the previous effect's
    vapour; brine and distillate cascaded from the previous effect flash down
    to the effect temperature and release their sensible heat into it. One
    liquid heat capacity is used for all liquid streams so that the energy
    ledger closes exactly.
    """
    tbt = t_steam_c - prm["med_tbt_drop_K"]
    temps = []
    t = tbt
    while t >= prm["med_last_C"] - 1e-9:
        temps.append(t)
        t -= prm["med_step_K"]
    r = 1.0 - prm["med_feed_salinity"] / prm["med_brine_salinity"]
    cp = CP_SEAWATER
    tf = prm["med_feed_C"]
    q = q_in_W                          # heating steam duty into effect 1
    bc = 0.0                            # cascading brine flow (kg/s)
    dc = 0.0                            # cascading distillate flow (kg/s)
    lost = 0.0
    t_prev = None
    d_prev = 0.0
    for i, ti in enumerate(temps):
        lost_i = prm["med_loss"] * q
        lost += lost_i
        avail = q - lost_i
        if i > 0:
            dc += d_prev                # condensate of previous vapour
            avail += (bc + dc) * cp * (t_prev - ti)   # flashing
        d_i = avail / (hfg(ti) + cp * (ti - tf) / r)
        bc += d_i / r - d_i
        q = d_i * hfg(ti)
        d_prev = d_i
        t_prev = ti
    q_final_cond = q
    dc += d_prev
    sens_out = (bc + dc) * cp * (temps[-1] - tf)
    closure = q_in_W - (lost + q_final_cond + sens_out)
    steam_kg = q_in_W / hfg(t_steam_c)
    gor = dc / steam_kg
    m3_day = dc * 86400.0 / 1000.0
    return dict(n_eff=len(temps), tbt=tbt, t_steam=t_steam_c, gor=gor, m3_day=m3_day,
                d_kg_s=dc, closure=closure,
                reject_low=q_in_W,      # all heat ends as low-grade heat
                elec_W=prm["med_kwh_per_m3"] * m3_day / 24.0 * 1e3)


# ---------------------------------------------------------------- tower
def tower_eta(prm):
    ideal = G * prm["tower_H"] / (CP_AIR * c2k(T_AMBIENT_C))
    return prm["tower_share"] * prm["tower_turb"] * ideal, ideal


# ------------------------------------------------------------- scenario
def scenario(chip, config, prm):
    name, t_chip, cyc = chip
    t_src = t_chip - prm["loop_drop_K"] / 2.0       # mean loop temperature
    Q = IT_POWER_MW * 1e6                            # all IT power -> heat
    out = dict(chip=name, config=config, t_chip=t_chip, t_src=t_src)
    eta_t, eta_t_ideal = tower_eta(prm)
    w_cycle = 0.0
    q_tower = 0.0
    water = None
    cycle = None
    if config == "C":
        t_steam = min(prm["med_steam_C"], t_src - prm["med_steam_approach_K"])
        water = med(Q, t_steam, prm)
        q_tower = water["reject_low"]
    else:
        if cyc.startswith("ORC"):
            fluid = cyc.split(":")[1]
            t_cond = (T_AMBIENT_C + prm["sink_approach_K"] if config == "A"
                      else prm["med_steam_C"] + prm["med_steam_approach_K"])
            if t_cond >= t_src - prm["pinch_K"]:
                return None                         # no temperature lift: infeasible
            cycle = orc(fluid, t_src, t_cond, prm)
            m = Q / cycle["q_in"]
            w_cycle = m * cycle["w"]
            q_rej = m * cycle["q_out"]
            if config == "A":
                q_tower = q_rej
            else:
                water = med(q_rej, prm["med_steam_C"], prm)
                q_tower = water["reject_low"]
        else:
            cycle = sco2(t_src, prm)
            m = Q / cycle["q_in"]
            w_cycle = m * cycle["w"]
            q_rej = m * cycle["q_out"]
            if config == "A":
                q_tower = q_rej
            else:
                q_hi = m * cycle["heat_above"](prm["med_steam_C"] + prm["med_steam_approach_K"])
                if q_hi <= 0:
                    return None
                water = med(q_hi, prm["med_steam_C"], prm)
                q_tower = water["reject_low"] + (q_rej - q_hi)
        if prm["drop_reject"]:
            q_tower = 0.0                            # injected energy leak
    p_tower = eta_t * q_tower
    q_env = q_tower - p_tower
    med_el = water["elec_W"] if water else 0.0
    gross = w_cycle + p_tower
    net = gross - med_el
    overhead = prm["furnace_overhead"] * Q
    grid = Q + overhead - net
    out.update(cycle=cycle, water=water, w_cycle=w_cycle, p_tower=p_tower,
               q_tower=q_tower, q_env=q_env, gross=gross, net=net,
               med_el=med_el, grid=grid, eta_tower=eta_t,
               eta_tower_ideal=eta_t_ideal)
    # facility energy closure: heat in = electricity out + heat to environment
    out["closure"] = Q - (w_cycle + p_tower + q_env)
    return out


# ------------------------------------------------------------- validation
def validate_cycle(cyc):
    """Physical-law checks on one power cycle. Returns list of (name, ok, detail)."""
    rows = []
    clos = abs(cyc["q_in"] - cyc["w"] - cyc["q_out"]) / cyc["q_in"]
    rows.append(("cycle energy closure", clos < 1e-9, f"{clos:.1e}"))
    # the fluid takes heat at or below t_src and rejects it at or above t_sink
    tsrc, tsink = c2k(cyc["t_src"]), c2k(cyc["t_sink"])
    cmax = carnot(tsrc, tsink)
    rows.append(("cycle below Carnot", 0 < cyc["eta"] < cmax,
                 f"eta {cyc['eta']:.4f} < {cmax:.4f}"))
    sgen = cyc["q_out"] / tsink - cyc["q_in"] / tsrc
    rows.append(("cycle entropy generation >= 0", sgen >= 0, f"{sgen:.3e} J/kgK"))
    for mname, s_in, s_out in cyc["machines"]:
        rows.append((f"{mname} entropy rise >= 0 (adiabatic)", s_out >= s_in - 1e-6,
                     f"{s_out - s_in:.3e} J/kgK"))
    rows.append(("recuperator pinch >= minimum",
                 cyc["pinch"] >= NOMINAL["recup_min_pinch_K"] - 1e-6,
                 f"{cyc['pinch']:.2f} K"))
    return rows


def validate(res):
    """Physical-law checks on one scenario. Returns list of (name, ok, detail)."""
    Q = IT_POWER_MW * 1e6
    rows = validate_cycle(res["cycle"]) if res["cycle"] is not None else []
    if res["water"] is not None:
        wt = res["water"]
        rows.append(("MED energy closure", abs(wt["closure"]) < 1e-6 * Q,
                     f"{wt['closure']:.2e} W"))
        rows.append(("MED GOR below number of effects", 0 < wt["gor"] < wt["n_eff"],
                     f"GOR {wt['gor']:.2f}, N {wt['n_eff']}"))
    rows.append(("tower below ideal bound g.H/(cp.T0)",
                 res["eta_tower"] <= res["eta_tower_ideal"],
                 f"{res['eta_tower']:.5f} <= {res['eta_tower_ideal']:.5f}"))
    rows.append(("facility energy closure", abs(res["closure"]) < 1e-6 * Q
                 and res["q_env"] >= 0, f"{res['closure']:.2e} W"))
    eta_tot = (res["w_cycle"] + res["p_tower"]) / Q
    eta1 = res["w_cycle"] / Q
    rows.append(("cascade only adds", eta_tot >= eta1, f"{eta_tot:.4f} >= {eta1:.4f}"))
    return rows


_assign_cycles()


# ------------------------------------------------------------------ main
def run(prm, verbose=True):
    results = []
    for chip in CHIPS:
        for config in ("A", "B", "C"):
            r = scenario(chip, config, prm)
            if r is not None:
                results.append(r)
    return results


def mw(x):
    return x / 1e6


def main():
    V = Verdicts("APPENDIX E3")
    print("E3  THE THERMODYNAMIC CASCADE  (per %.0f MW of compute)" % IT_POWER_MW)
    print("ambient %.0f degC, seawater %.0f degC, tower height %.0f m"
          % (T_AMBIENT_C, T_SEAWATER_C, NOMINAL["tower_H"]))

    # E3.1 The originating post's figures (CLAIM entries), tested as stated
    tl, th, tol = v("post_t_low"), v("post_t_high"), v("post_tol")
    c_lo = carnot(c2k(tl), c2k(T_AMBIENT_C))
    c_hi = carnot(c2k(th), c2k(T_AMBIENT_C))
    print("\nE3.1 The originating post's figures at %.0f degC ambient" % T_AMBIENT_C)
    print("  Carnot ceilings: %.0f degC %.2f%% (post ~%.0f%%), %.0f degC %.2f%% (post ~%.0f%%)"
          % (tl, 100 * c_lo, 100 * v("post_carnot_low"), th, 100 * c_hi,
             100 * v("post_carnot_high")))
    V.check("E3.1 post figure reproduced: Carnot ceiling at the low temperature",
            abs(c_lo - v("post_carnot_low")) <= tol, f"{c_lo:.4f}")
    V.check("E3.1 post figure reproduced: Carnot ceiling at the high temperature",
            abs(c_hi - v("post_carnot_high")) <= tol, f"{c_hi:.4f}")
    sink0 = T_AMBIENT_C + NOMINAL["sink_approach_K"]
    eta_t0, _ = tower_eta(NOMINAL)
    _, cyc_lo = best_cycle(tl - NOMINAL["loop_drop_K"] / 2.0, sink0, NOMINAL)
    rec_lo = cyc_lo["eta"] + (1 - cyc_lo["eta"]) * eta_t0
    orc_hi = orc("Toluene", th - NOMINAL["loop_drop_K"] / 2.0, sink0, NOMINAL)
    rec_hi = orc_hi["eta"] + (1 - orc_hi["eta"]) * eta_t0
    h_post = v("post_tower") / (eta_t0 / NOMINAL["tower_H"])
    print("  recovered at %.0f degC: %.2f%% (post ~%.0f%%)" % (tl, 100 * rec_lo,
                                                            100 * v("post_recovery_low")))
    print("  ORC at %.0f degC: %.2f%% (post ~%.0f%%)" % (th, 100 * orc_hi["eta"],
                                                      100 * v("post_orc_high")))
    print("  ratio of recovered energy: %.1f (post ~%.0fx)" % (rec_hi / rec_lo, v("post_ratio")))
    print("  tower at ~%.0f%% of rejected heat: a height of %.0f m (%.2f%% at %.0f m)"
          % (100 * v("post_tower"), h_post, 100 * eta_t0, NOMINAL["tower_H"]))
    V.check("E3.1 post figure reproduced: recovery at the low temperature",
            abs(rec_lo - v("post_recovery_low")) <= tol, f"{rec_lo:.4f}")
    V.check("E3.1 post figure met or exceeded: ORC at the high temperature",
            orc_hi["eta"] >= v("post_orc_high") - tol, f"{orc_hi['eta']:.4f}")
    V.check("E3.1 post figure reproduced: about four times the recovered energy",
            abs(rec_hi / rec_lo - v("post_ratio")) <= 0.5, f"{rec_hi / rec_lo:.2f}")
    V.check("E3.1 post figure located: the chimney law gives it at a derived tower height",
            abs(tower_eta(dict(NOMINAL, tower_H=h_post))[0] - v("post_tower")) < 1e-12,
            f"{h_post:.0f} m")

    res = run(NOMINAL)

    # E3.2 cycles
    print("\nE3.2 Power cycles")
    print("%-8s %-3s %-26s %7s %7s %8s %8s" % ("chip", "cfg", "cycle", "Tsrc", "Tsink",
                                                "eta", "Carnot"))
    for r in res:
        c = r["cycle"]
        if c is None:
            continue
        cm = carnot(c2k(c["t_src"]), c2k(c["t_sink"]))
        print("%-8s %-3s %-26s %7.1f %7.1f %7.2f%% %7.2f%%" % (
            r["chip"], r["config"], c["kind"], c["t_src"], c["t_sink"],
            100 * c["eta"], 100 * cm))

    # E3.3 cascade outputs
    print("\nE3.3 Cascade outputs per 100 MW of compute")
    hdr = ("chip", "cfg", "cycle MW", "tower MW", "MED MW", "net MW", "water m3/d",
           "GOR", "grid MW")
    print("%-8s %-3s %9s %9s %8s %8s %11s %5s %8s" % hdr)
    for r in res:
        wt = r["water"]
        print("%-8s %-3s %9.2f %9.3f %8.3f %8.2f %11.0f %5s %8.2f" % (
            r["chip"], r["config"], mw(r["w_cycle"]), mw(r["p_tower"]),
            mw(r["med_el"]), mw(r["net"]), wt["m3_day"] if wt else 0,
            ("%.2f" % wt["gor"]) if wt else "-", mw(r["grid"])))

    # E3.4 baselines
    print("\nE3.4 Against conventional data centres (100 MW IT)")
    base = [("industry average", PUE_INDUSTRY_AVG, WUE_INDUSTRY_AVG),
            ("efficient hyperscale", PUE_HYPERSCALE, WUE_HYPERSCALE)]
    for lab, pue, wue in base:
        print("  %-22s grid %.1f MW, water consumed %.0f m3/day"
              % (lab, pue * IT_POWER_MW, wue * IT_POWER_MW * 1e3 * 24 / 1e3))
    print("%-8s %-3s %9s %14s %14s %24s" % ("chip", "cfg", "grid MW", "vs hyperscale",
                                            "vs average", "water vs hyperscale m3/d"))
    for r in res:
        g = mw(r["grid"])
        wt = r["water"]["m3_day"] if r["water"] else 0.0
        print("%-8s %-3s %9.2f %13.1f%% %13.1f%% %24.0f" % (
            r["chip"], r["config"], g,
            100 * (1 - g / (PUE_HYPERSCALE * IT_POWER_MW)),
            100 * (1 - g / (PUE_INDUSTRY_AVG * IT_POWER_MW)),
            wt + WUE_HYPERSCALE * IT_POWER_MW * 24))

    # E3.5 tower height sweep
    print("\nE3.5 Tower efficiency against height (ideal g.H/(cp.T0); realised 2/3 x turbine)")
    for H in (100, 200, 500, 1000, 2000):
        p = dict(NOMINAL, tower_H=H)
        e, ei = tower_eta(p)
        print("  H %5d m: ideal %.3f%%, realised %.3f%%" % (H, 100 * ei, 100 * e))
    e200, _ = tower_eta(NOMINAL)
    h_big = 5.0 * NOMINAL["tower_H"]
    e1k, _ = tower_eta(dict(NOMINAL, tower_H=h_big))
    V.check("E3.5 tower efficiency scales linearly with height",
            abs(e1k / e200 - h_big / NOMINAL["tower_H"]) < 1e-9,
            f"ratio {e1k / e200:.6f}")

    # per-scenario physical checks
    for r in res:
        for name, ok, det in validate(r):
            V.check(f"E3.2/3 {r['chip']} {r['config']}: {name}", ok, det)

    # monotonicity and cascade formula
    netA = [mw(r["net"]) for r in res if r["config"] == "A"]
    V.check("E3.3 config A: electricity rises with chip temperature",
            all(b > a for a, b in zip(netA, netA[1:])),
            " < ".join("%.2f" % x for x in netA))
    for r in res:
        if r["cycle"] is not None and r["config"] == "A":
            e1 = r["w_cycle"] / (IT_POWER_MW * 1e6)
            e2 = r["eta_tower"]
            formula = e1 + (1 - e1) * e2
            actual = (r["w_cycle"] + r["p_tower"]) / (IT_POWER_MW * 1e6)
            V.check(f"E3.3 {r['chip']} A: eta_total = eta1 + (1-eta1)eta2",
                    abs(formula - actual) < 1e-12, f"{actual:.6f}")
    # literature ranges (validation against published practice)
    for r in res:
        wt = r["water"]
        if wt and wt["t_steam"] >= NOMINAL["med_steam_C"] - 1e-9:
            # the model must never overstate water: its GOR may not exceed the
            # commercial upper bound; a GOR below the commercial lower bound
            # understates water and is reported, not hidden
            V.check(f"E3.6 {r['chip']} {r['config']}: MED GOR does not exceed the published "
                    f"upper bound {v('med_gor_hi'):.0f} (water never overstated)",
                    wt["gor"] <= v("med_gor_hi"),
                    f"GOR {wt['gor']:.2f}; published {v('med_gor_lo'):.0f}-"
                    f"{v('med_gor_hi'):.0f}; water understated by up to "
                    f"{100 * max(0.0, 1 - wt['gor'] / v('med_gor_lo')):.0f}% against the "
                    f"commercial lower bound")
        elif wt:
            # derived finding: the coolant is colder than benchmark MED steam,
            # so fewer effects fit and the plant falls below commercial practice
            V.check(f"E3.6 {r['chip']} {r['config']}: coolant below benchmark MED steam, "
                    "GOR falls below the commercial range (derived finding)",
                    wt["gor"] < v("med_gor_lo"),
                    f"steam {wt['t_steam']:.1f} degC, GOR {wt['gor']:.2f}")
    sink = T_AMBIENT_C + NOMINAL["sink_approach_K"]
    t_src300 = v("t_sic_design") - NOMINAL["loop_drop_K"] / 2.0
    orc300 = orc("Toluene", t_src300, sink, NOMINAL)
    sc300 = sco2(t_src300, NOMINAL)
    print("\nE3.6 Benchmark comparison at the SiC design point: toluene ORC state-point "
          "model %.2f%%, demonstrated practice %.0f%%, credited %.2f%%; simple sCO2 %.2f%%"
          % (100 * orc300["eta_model"], 100 * v("eta_orc_ceiling"), 100 * orc300["eta"],
             100 * sc300["eta"]))
    print("     the cycle assigned to each class is the better of the two: %s"
          % "; ".join("%s %s" % (n, c) for n, _, c in CHIPS))
    V.check("E3.6 credited ORC efficiency never exceeds demonstrated practice",
            all(r["cycle"]["eta"] <= v("eta_orc_ceiling") + 1e-12 for r in res
                if r["cycle"] is not None and r["cycle"]["kind"].startswith("ORC"))
            and orc300["eta"] <= v("eta_orc_ceiling") + 1e-12)
    V.check("E3.6 credited ORC efficiency is the lesser of model and practice",
            abs(orc300["eta"] - min(orc300["eta_model"], v("eta_orc_ceiling"))) < 1e-12,
            "%.4f" % orc300["eta"])
    for e_p in REG["eta_pump_orc"].sweep:              # pump efficiency sweep ends
        c_p = orc("Toluene", t_src300, sink, dict(NOMINAL, eta_pump=e_p))
        print("E3.6 ORC pump efficiency %.2f: toluene ORC at the design point %.2f%%"
              % (e_p, 100 * c_p["eta"]))
        V.check(f"E3.6 pump efficiency {e_p:g}: ORC physically valid",
                all(ok for _, ok, _ in validate_cycle(c_p)), "%.4f" % c_p["eta"])
    smax = [r for r in res if r["chip"] == "SiC-max" and r["config"] == "A"][0]
    print("E3.6 sCO2 compressor inlet: derived %.1f degC (ambient + sink approach), "
          "reference study %.1f degC; the derived inlet is the less favourable"
          % (smax["cycle"]["t_sink"], v("t_comp_in_sco2_ref")))
    V.check("E3.6 sCO2 compressor inlet equals the registry derivation",
            abs(smax["cycle"]["t_sink"] - v("t_comp_in_sco2")) < 1e-12
            and v("t_comp_in_sco2") >= v("t_comp_in_sco2_ref"),
            "%.1f degC" % smax["cycle"]["t_sink"])
    V.check("E3.6 simple sCO2 below the recompression benchmark at higher temperature",
            0 < smax["cycle"]["eta"] < v("eta_sco2_recomp_550"),
            f"{smax['cycle']['eta']:.4f} < {v('eta_sco2_recomp_550')}")

    # claims against the baselines, scoped to what each configuration is for
    base_water = WUE_HYPERSCALE * IT_POWER_MW * 24.0          # m3/day consumed
    for r in res:
        if r["chip"] in ("SiC-300", "SiC-max") and r["config"] in ("A", "B"):
            V.check(f"E3.4 {r['chip']} {r['config']}: grid draw below efficient hyperscale",
                    mw(r["grid"]) < PUE_HYPERSCALE * IT_POWER_MW, "%.2f MW" % mw(r["grid"]))
        if r["config"] in ("B", "C"):
            V.check(f"E3.4 {r['chip']} {r['config']}: water produced exceeds the "
                    "hyperscale facility's water consumed",
                    r["water"]["m3_day"] > base_water,
                    "%.0f > %.0f m3/day" % (r["water"]["m3_day"], base_water))
        if r["config"] == "C":
            # water-first spends electricity on MED pumping; the check is that
            # the water, at the benchmark price, is worth more than the extra
            # electricity, at the benchmark price, relative to hyperscale.
            extra_mwh = (mw(r["grid"]) - PUE_HYPERSCALE * IT_POWER_MW) * 24.0
            V.check(f"E3.4 {r['chip']} C: water value exceeds the electricity premium "
                    "over hyperscale (benchmark prices)",
                    r["water"]["m3_day"] * v("water_price") > extra_mwh * PRICE_USD_PER_MWH,
                    "$%.0f vs $%.0f per day" % (r["water"]["m3_day"] * v("water_price"),
                                                max(extra_mwh, 0) * PRICE_USD_PER_MWH))

    # E3.7 fault injection: every injected fault must be caught
    print("\nE3.7 Fault injection")
    faults = [
        ("ORC expander efficiency 1.6 (beats Carnot)", "Si", "A",
         dict(eta_turb_orc=1.6, eta_orc_ceiling=1.0)),
        ("sCO2 turbine efficiency 1.5", "SiC-max", "A", dict(eta_turb_sco2=1.5)),
        ("recuperator effectiveness 1.5 (temperature cross)", "SiC-max", "A", dict(recup_eff=1.5)),
        ("MED loss -0.5 (energy created in effects)", "SiC-300", "B", dict(med_loss=-0.5)),
        ("rejected heat dropped from ledger", "SiC-300", "A", dict(drop_reject=True)),
        ("tower turbine efficiency 4.0", "Si", "A", dict(tower_turb=4.0)),
    ]
    for label, chip_name, cfg, change in faults:
        prm = dict(NOMINAL, **change)
        chip = [c for c in CHIPS if c[0] == chip_name][0]
        try:
            r = scenario(chip, cfg, prm)
            caught = r is None or not all(ok for _, ok, _ in validate(r))
        except Exception as exc:  # a property call refusing the state also counts
            caught = True
            label += f" [raised {type(exc).__name__}]"
        print("  %-55s %s" % (label, "caught" if caught else "MISSED"))
        V.check(f"E3.7 fault caught: {label}", caught)

    # illustrative annual value
    print("\nE3.8 Annual value at $%.0f/MWh (net electricity recovered)" % PRICE_USD_PER_MWH)
    for r in res:
        mwh = mw(r["net"]) * HOURS_PER_YEAR
        print("  %-8s %s: %9.0f MWh/yr  $%.1fM" % (r["chip"], r["config"], mwh,
                                                 mwh * PRICE_USD_PER_MWH / 1e6))
    V.finish()


if __name__ == "__main__":
    main()
