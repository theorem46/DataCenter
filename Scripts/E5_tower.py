"""E5 - The tower: height, moisture and the atmosphere as a cold reservoir.

  E5.1  The dry updraft tower. Ideal efficiency g.H/(cp.T0), realised 2/3 of
        it times the turbine efficiency; the height needed for a target.
  E5.2  The atmosphere as the cold reservoir. Air rising a height H cools
        adiabatically by g.H/cp, so heat is rejected aloft to a colder
        reservoir. The tower's ideal efficiency must therefore sit below the
        Carnot efficiency between the plume and the air at the top of the
        column, at every height; this is checked.
  E5.3  Moisture. Exhaust air from the desalination stage leaves warm and
        humid. Per kilogram of air it carries far more enthalpy than dry air at
        the same temperature, and water vapour is lighter than air, which adds
        buoyancy. Both are computed from real humid-air properties (CoolProp).
  E5.4  Virtual chimneys. A vortex or moist plume that rises well above any
        structure behaves as a taller column. Its ideal efficiency is bounded
        here for effective heights of 1 to 10 km; these are bounds, not claims
        of achieved performance.

Run:  python3 -I Scripts/E5_tower.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from conventions import Verdicts, G, CP_AIR, c2k, carnot, T_AMBIENT_C  # noqa: E402
from registry import v, REG  # noqa: E402
import E3_cascade as E3  # noqa: E402
from CoolProp.HumidAirProp import HAPropsSI  # noqa: E402

T0 = c2k(T_AMBIENT_C)
P0 = v("p_atm")
RH = v("rh_ambient")
EPS = v("eps_mw")                      # molar-mass ratio water / dry air
TURB = E3.NOMINAL["tower_turb"]
SHARE = E3.NOMINAL["tower_share"]
T_PLUME_C = v("med_last")              # exhaust leaves the MED final condenser
H_SCAN = (50, 100, 200, 500, 1000, 2000)        # output grid, m
H_COLUMN = (200, 1000, 5000, 10000)             # output grid, m
T_EXHAUST = (35.0, 40.0, 45.0)                  # output grid, degC


def ideal(H):
    return G * H / (CP_AIR * T0)


def realised(H):
    return SHARE * TURB * ideal(H)


def main():
    V = Verdicts("APPENDIX E5")
    print("E5  THE TOWER")

    # ------------------------------------------------------------ E5.1
    print("\nE5.1  Dry updraft tower (ambient %.0f degC, turbine %.2f, pressure share %.3f)"
          % (T_AMBIENT_C, TURB, SHARE))
    print("  %8s %12s %12s %22s" % ("H (m)", "ideal", "realised", "MW per 100 MW rejected"))
    Hs = list(H_SCAN)
    for H in Hs:
        print("  %8d %11.3f%% %11.3f%% %22.3f" % (H, 100 * ideal(H), 100 * realised(H),
                                                 100 * realised(H)))
    for target in (0.005, 0.01, 0.02):
        H = target / realised(1.0)
        print("  height for %.1f%% realised: %.0f m" % (100 * target, H))
    V.check("E5.1 efficiency proportional to height", all(
        abs(realised(H) / realised(100) - H / 100) < 1e-12 for H in Hs))
    V.check("E5.1 realised below ideal at every height", all(realised(H) < ideal(H) for H in Hs))

    # ------------------------------------------------------------ E5.2
    print("\nE5.2  The atmosphere as cold reservoir: Carnot bound with air at the column top")
    print("  %8s %12s %14s %14s" % ("H (m)", "T top (K)", "ideal tower", "Carnot bound"))
    t_plume = c2k(T_PLUME_C)
    for H in H_COLUMN:
        t_top = T0 - G * H / CP_AIR
        cb = carnot(t_plume, t_top)
        print("  %8d %12.1f %13.2f%% %13.2f%%" % (H, t_top, 100 * ideal(H), 100 * cb))
        V.check(f"E5.2 H = {H} m: tower ideal below Carnot to the column-top air",
                ideal(H) < cb, "%.4f < %.4f" % (ideal(H), cb))
    V.check("E5.2 the tallest column exceeds the Carnot limit of plume heat to ground air",
            ideal(H_COLUMN[-1]) > carnot(t_plume, T0),
            "%.3f > %.3f: the cold reservoir aloft is what makes this possible"
            % (ideal(H_COLUMN[-1]), carnot(t_plume, T0)))

    # ------------------------------------------------------------ E5.3
    print("\nE5.3  Moisture from the desalination stage (ambient %.0f degC, %.0f%% RH)"
          % (T_AMBIENT_C, 100 * RH))
    h_amb = HAPropsSI("H", "T", T0, "P", P0, "R", RH)
    w_amb = HAPropsSI("W", "T", T0, "P", P0, "R", RH)
    rows = []
    for tc in T_EXHAUST:
        T = c2k(tc)
        h_dry = HAPropsSI("H", "T", T, "P", P0, "W", w_amb)       # heated, same moisture
        h_wet = HAPropsSI("H", "T", T, "P", P0, "R", 1.0)         # saturated exhaust
        w_wet = HAPropsSI("W", "T", T, "P", P0, "R", 1.0)
        tv = lambda t, w: t * (1 + w / EPS) / (1 + w)            # virtual temperature
        b_dry = tv(T, w_amb) / tv(T0, w_amb) - 1.0
        b_wet = tv(T, w_wet) / tv(T0, w_amb) - 1.0
        rows.append((tc, h_dry - h_amb, h_wet - h_amb, b_dry, b_wet))
        print("  exhaust %2.0f degC: heat carried %6.1f kJ/kg dry vs %6.1f kJ/kg humid (x%.1f);"
              " buoyancy %.3f vs %.3f (x%.2f)" % (
                  tc, (h_dry - h_amb) / 1e3, (h_wet - h_amb) / 1e3,
                  (h_wet - h_amb) / (h_dry - h_amb), b_dry, b_wet, b_wet / b_dry))
    for tc, hd, hw, bd, bw in rows:
        V.check(f"E5.3 {tc:.0f} degC humid exhaust carries more heat per kg of air", hw > hd,
                "x%.1f" % (hw / hd))
        V.check(f"E5.3 {tc:.0f} degC humid exhaust is more buoyant than dry air", bw > bd,
                "x%.2f" % (bw / bd))
    for rh in REG["rh_ambient"].sweep:          # sweep ends of ambient humidity
        ha = HAPropsSI("H", "T", T0, "P", P0, "R", rh)
        wa = HAPropsSI("W", "T", T0, "P", P0, "R", rh)
        T = c2k(T_PLUME_C)
        hd = HAPropsSI("H", "T", T, "P", P0, "W", wa) - ha
        hw = HAPropsSI("H", "T", T, "P", P0, "R", 1.0) - ha
        print("  RH %.0f%%: exhaust %.0f degC carries x%.1f the heat when saturated"
              % (100 * rh, T_PLUME_C, hw / hd))
        V.check(f"E5.3 RH {rh:g}: humid exhaust carries more heat per kg of air", hw > hd,
                "x%.1f" % (hw / hd))
    print("  humid exhaust lets the same tower absorb several times the heat per kg of air,")
    print("  and the latent heat is released aloft as the plume condenses")

    # ------------------------------------------------------------ E5.4
    print("\nE5.4  Virtual chimney bounds (effective column height, ideal and realised)")
    for H in H_COLUMN[1:]:
        print("  H_eff %5d m: ideal %.2f%%, realised %.2f%%, per 100 MW rejected %.2f MW"
              % (H, 100 * ideal(H), 100 * realised(H), 100 * realised(H)))
        V.check(f"E5.4 H_eff {H} m: bound stays below Carnot to the column-top air",
                ideal(H) < carnot(t_plume, T0 - G * H / CP_AIR))

    # ------------------------------------------------------------ E5.5 faults
    print("\nE5.5  Fault injection")
    faults = [
        ("tower efficiency computed with T0 in Celsius",
         G * H_COLUMN[0] / (CP_AIR * T_AMBIENT_C)
         > carnot(t_plume, T0 - G * H_COLUMN[0] / CP_AIR)),
        ("humid enthalpy replaced by half the dry value",
         not (0.5 * rows[1][1] > rows[1][1])),
        ("turbine extracting more than the full pressure drop (factor 1.5)",
         1.5 * TURB * ideal(H_COLUMN[0]) > ideal(H_COLUMN[0])),
    ]
    for label, caught in faults:
        print("  %-60s %s" % (label, "caught" if caught else "MISSED"))
        V.check(f"E5.5 fault caught: {label}", caught)
    V.finish()


if __name__ == "__main__":
    main()
