"""Generate the figures quoted in the paper from the experiment logs, so that
prose and measurement cannot drift.

Every figure the paper quotes is a LaTeX macro in one block of its source,
between the two marker lines

    %% ---- generated figures, so prose and measurement cannot drift ----
    %% ---- end of generated figures ----

The block as published is committed as Experiment Logs/paper_figures.tex. This
program reads every one of those figures from Experiment Logs/ and compares;
it exits 1 on any difference. With --paper PATH it checks the block inside a
copy of the paper's LaTeX source instead. With --write it regenerates the
block in whichever file it checks.

Run:  python3 -I make_paper_numbers.py                        (check)
      python3 -I make_paper_numbers.py --paper main.tex       (check a paper)
      python3 -I make_paper_numbers.py --write                (regenerate)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(ROOT, "Experiment Logs")
FIGURES = os.path.join(LOGS, "paper_figures.tex")
BEGIN = "%% ---- generated figures, so prose and measurement cannot drift ----"
END = "%% ---- end of generated figures ----"

PROTOCOLS = [
    ("Eone", "E1_geometric_heat"), ("Etwo", "E2_insight_baseline"),
    ("Ethree", "E3_cascade"), ("Efour", "E4_leakage_crossover"),
    ("Efive", "E5_tower"), ("Esix", "E6_best_uses"),
    ("Eseven", "E7_uncertainty"), ("Eeight", "E8_incremental_production"),
    ("Enine", "E9_dataset_value"), ("D", "dependency_graph"),
]
WORDS = {10: "ten", 11: "eleven", 12: "twelve"}


def log(name):
    with open(os.path.join(LOGS, name + ".log"), encoding="utf-8") as f:
        return f.read()


def grab(text, pattern, group=1):
    m = re.search(pattern, text, re.M)
    if not m:
        sys.exit("make_paper_numbers: pattern not found: %s" % pattern)
    return m.group(group)


def thou(x):
    """Integer with LaTeX thousands separators."""
    return "{:,}".format(int(round(float(x)))).replace(",", "{,}")


def fix(x, nd):
    return ("%." + str(nd) + "f") % float(x)


def figures():
    F = []

    def add(name, value, note=None):
        if note:
            F.append("%% " + note)
        F.append("\\newcommand{\\%s}{%s}" % (name, value))

    # verdicts --------------------------------------------------------------
    total, faults = 0, 0
    for macro, name in PROTOCOLS:
        t = log(name)
        n = int(grab(t, r"(\d+)/\d+ checks pass\s*$"))
        total += n
        faults += len(re.findall(r"^\[PASS\] E\d(?:\.\d+)?[a-z]? fault caught", t, re.M))
        add(macro + "Checks", n, "verdicts of each protocol" if macro == "Eone" else None)
    add("checksTotal", total)
    add("protocolCount", WORDS[len(PROTOCOLS)])
    add("ProtocolCount", WORDS[len(PROTOCOLS)].capitalize())
    add("faultCount", faults)

    # the registry (D7 census) ---------------------------------------------
    d = log("dependency_graph")
    for kind in ("LAW", "BENCH", "DERIVED", "DESIGN", "CLAIM"):
        add("Reg" + kind.capitalize(), grab(d, r"^\s+%s\s+(\d+)" % kind),
            "the registry" if kind == "LAW" else None)
    add("RegTotal", grab(d, r"total\s+(\d+) nodes"))
    add("RegEdges", grab(d, r"(\d+) derivation edges"))
    add("RegSwept", grab(d, r"swept\s+(\d+)"))
    add("CiteKeys", grab(d, r"resolves in sn-bibliography\.bib\s+\((\d+) keys\)"))

    # E9: the dataset computed once, and its ground truth -------------------
    e9 = log("E9_dataset_value")
    add("SavedTen", grab(e9, r"N = 10: .*\((\d+)%\)"), "the geometric dataset (E9)")
    add("SavedFifty", grab(e9, r"N = 50: .*\((\d+)%\)"))
    m = re.search(r"T5 corpus: ([\d.e+]+) MWh of computation, ([\d.e+]+) USD in the furnace;"
                  r" each developer spared it saves ([\d.e+]+) USD", e9)
    add("CorpusTWh", fix(float(m.group(1)) / 1e6, 2))
    add("CorpusOnceM", thou(float(m.group(2)) / 1e6))
    add("CorpusEachM", thou(float(m.group(3)) / 1e6))
    rows = re.findall(r"^\s+\d\s+(\d+)\s+([\d.e+-]+)\s+[\d.e+-]+\s+\S+$",
                      e9.split("E9.4")[1].split("E9.5")[0], re.M)
    add("PrecCoarse", fix(float(rows[0][1]) * 100, 1))
    add("PrecFine", fix(float(rows[-1][1]) * 100, 2))
    m = re.search(r"error ratio raw / dataset: ([\d.]+) to ([\d.]+) \(median ([\d.]+)\)", e9)
    add("FitLo", m.group(1))
    add("FitHi", "%d" % round(float(m.group(2))))
    add("FitMedian", m.group(3))
    add("FitWins", grab(e9, r"every sample size, target and surface\s+\((\d+ of \d+)\)"))

    # E3: the cascade --------------------------------------------------------
    e3 = log("E3_cascade")
    tab = e3.split("E3.3")[1].split("E3.4")[0]

    def net(chip, cfg):
        return grab(tab, r"^%s\s+%s\s+\S+\s+\S+\s+\S+\s+(-?[\d.]+)" % (re.escape(chip), cfg))
    add("RecSi", fix(net("Si", "A"), 1), "the heat as secondary energy (E3, E7)")
    add("RecDesign", fix(net("SiC-300", "A"), 1))
    add("RecMax", fix(net("SiC-max", "A"), 1))
    add("WaterMax", thou(grab(tab, r"^SiC-300\s+C\s+(?:\S+\s+){4}(\d+)")))
    add("CarnotLow", fix(grab(e3, r"80 degC ([\d.]+)%"), 1))
    add("CarnotHigh", fix(grab(e3, r"300 degC ([\d.]+)% \(post"), 1))
    e7 = log("E7_uncertainty")
    add("RecLB", fix(grab(e7, r"together: recovery ([\d.]+)%"), 1))
    add("PUEbreak", grab(e7, r"PUE-equivalent ([\d.]+)\)"))

    # E8: the integrated energy facility ------------------------------------
    e8 = log("E8_incremental_production")
    m = re.search(r"US process heat below 300 degC: (\d+) TBtu of (\d+) \((\d+)%\), a continuous (\d+) GW", e8)
    add("ProcShare", m.group(3), "the integrated energy facility (E8)")
    add("ProcGW", m.group(4))
    m = re.search(r"(\d+) TBtu of refinery process heat \((\d+)%\)", e8)
    add("RefTBtu", thou(m.group(1)))
    add("RefShare", m.group(2))
    add("RefFuel", grab(e8, r"a year, (\d+)% of refinery fuel use"))
    add("RefCO", grab(e8, r"avoids at least (\d+) Mt of CO2"))
    add("RefGW", grab(e8, r"the heat of (\d+) GW of computation"))
    saves = re.findall(r"saved: [\d.]+ TWh of energy bought \((\d+)%\), ([\d.]+) Mt CO2 from gas; (\d+) M USD", e8)
    add("SysDirect", saves[0][0])
    add("SysCascade", saves[1][0])
    add("SysCOlo", fix(min(float(s[1]) for s in saves), 1))
    add("SysCOhi", fix(max(float(s[1]) for s in saves), 1))
    add("SysUSDlo", saves[0][2])
    add("SysUSDhi", saves[1][2])
    return F


def block():
    return "\n".join([BEGIN] + figures() + [END])


def main():
    target = FIGURES
    if "--paper" in sys.argv:
        target = os.path.abspath(sys.argv[sys.argv.index("--paper") + 1])
    name = os.path.relpath(target, ROOT)
    new = block()
    if target == FIGURES and not os.path.exists(FIGURES):
        tex = new
    else:
        with open(target, encoding="utf-8") as f:
            tex = f.read()
    pat = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    if not pat.search(tex):
        sys.exit("make_paper_numbers: marker lines not found in %s" % name)
    if "--write" in sys.argv:
        with open(target, "w", encoding="utf-8") as f:
            f.write(pat.sub(lambda _: new, tex).rstrip("\n") + "\n")
        print("wrote %d generated figures into %s" % (new.count("\\newcommand"), name))
        return
    if pat.search(tex).group(0) != new:
        print("PAPER FIGURES: the block in %s differs from the logs" % name)
        sys.exit(1)
    print("PAPER FIGURES: %d generated figures agree with the logs" % new.count("\\newcommand"))


if __name__ == "__main__":
    main()
