"""Shared conventions for the AI compute-heat validation archive.

Every physical constant, benchmark and design value is read from registry.py,
where each carries its kind and source. This module only re-exports the
values most experiments use, under stable names, and provides the verdict
harness. It defines no input of its own.
"""
import sys

from registry import v

G = v("g_n")
CP_AIR = v("cp_air")
CP_SEAWATER = v("cp_seawater")
K0 = v("zero_C_in_K")
T_AMBIENT_C = v("t_ambient")
T_SEAWATER_C = v("t_seawater")
IT_POWER_MW = v("it_power_mw")
HOURS_PER_YEAR = v("hours_per_year")
PRICE_USD_PER_MWH = v("elec_price")
PUE_INDUSTRY_AVG = v("pue_avg")
PUE_HYPERSCALE = v("pue_hyperscale")
WUE_INDUSTRY_AVG = v("wue_avg")
WUE_HYPERSCALE = v("wue_hyperscale")


def c2k(t_c):
    return t_c + K0


def carnot(t_hot_k, t_cold_k):
    return 1.0 - t_cold_k / t_hot_k


class Verdicts:
    """Collects named checks; prints them; exits non-zero if any fails."""

    def __init__(self, label):
        self.label = label
        self.rows = []

    def check(self, name, condition, detail=""):
        self.rows.append((name, bool(condition), detail))
        return bool(condition)

    def report(self):
        print()
        print("=" * 78)
        print(f"VERDICTS  {self.label}")
        print("=" * 78)
        for name, ok, detail in self.rows:
            tag = "PASS" if ok else "FAIL"
            line = f"[{tag}] {name}"
            if detail:
                line += f"  ({detail})"
            print(line)
        n_ok = sum(ok for _, ok, _ in self.rows)
        print("-" * 78)
        print(f"{self.label}: {n_ok}/{len(self.rows)} checks pass")
        return n_ok == len(self.rows)

    def finish(self):
        sys.exit(0 if self.report() else 1)
