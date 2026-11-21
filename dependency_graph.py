"""The dependency chain: closure, provenance and coherence of every input.

Verifies, and exits 1 on any failure:

  D1  closure     every DERIVED entry names its dependencies, every dependency
                  exists, and the graph is acyclic (each entry depends only on
                  entries defined before it)
  D2  provenance  every BENCH entry carries a citation key; every citation key
                  (BENCH, LAW, DESIGN) resolves in sn-bibliography.bib
  D3  ranges      every sweep range contains its nominal value, and every BENCH
                  range takes as nominal the end its basis declares
  D4  usage       every registry entry is consumed by an experiment or by
                  another entry (no orphan inputs)
  D5  no shadows  no experiment script contains a numeric literal equal to a
                  registry value (an input re-typed instead of read); protocol
                  constants that coincide are listed with their reason
  D6  coherence   values imported across experiments equal the registry, and
                  results that two experiments compute independently agree
  D7  census      nodes by kind, edges, and the entries each experiment reads;
                  writes Experiment Logs/registry_table.md for the paper

Run:  python3 -I dependency_graph.py
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "Scripts"))
from registry import REG, v  # noqa: E402
from conventions import Verdicts  # noqa: E402

SCRIPTS = ["conventions.py"] + [os.path.join("Scripts", f) for f in sorted(
    os.listdir(os.path.join(ROOT, "Scripts"))) if re.match(r"E\d_.*\.py$", f)]
BIB = os.path.join(ROOT, "sn-bibliography.bib")

# Module-level numeric constants allowed in experiments, each with its reason.
# None is an input to a physical or economic result: they set output grids,
# the specimen shapes of the dataset slice, or units.
PROTOCOL = {
    ("E1_geometric_heat.py", "COOLANT_SCAN"): "extra rows of the E1.3 table (output grid)",
    ("E2_insight_baseline.py", "HKS_TIMES"): "heat-kernel signature times (specimen)",
    ("E2_insight_baseline.py", "SWEEP"): "deformation amplitudes of the slice (specimen)",
    ("E2_insight_baseline.py", "HELD_OUT_A"): "held-out amplitudes (specimen)",
    ("E2_insight_baseline.py", "MODES"): "deformation polynomials (specimen)",
    ("E2_insight_baseline.py", "GEOMS"): "slice membership (specimen)",
    ("E4_leakage_crossover.py", "SCAN_STEP"): "coolant scan resolution (output grid)",
    ("E5_tower.py", "H_SCAN"): "tower heights tabulated (output grid)",
    ("E5_tower.py", "H_COLUMN"): "column heights tabulated (output grid)",
    ("E5_tower.py", "T_EXHAUST"): "exhaust temperatures tabulated (output grid)",
    ("E6_best_uses.py", "REGIONS"): "0.0: the United States has no federal carbon price",
    ("E7_uncertainty.py", "CHIP"): "list indices",
    ("E7_uncertainty.py", "MW_PER_GW"): "unit",
    ("E8_incremental_production.py", "MW_PER_GW"): "unit",
    ("E9_dataset_value.py", "J_PER_MWH"): "unit",
    ("E9_dataset_value.py", "BETA"): "screening of the test operator (specimen)",
    ("E9_dataset_value.py", "LEVELS"): "mesh resolutions (specimen)",
    ("E9_dataset_value.py", "LEARN_LEVEL"): "resolution of the learning specimens",
    ("E9_dataset_value.py", "SPECIMENS"): "surface shapes (specimen)",
    ("E9_dataset_value.py", "SAMPLE_MULT"): "training-set sizes as multiples of features (grid)",
    ("E9_dataset_value.py", "REPS"): "random draws per sample size (protocol)",
    ("E9_dataset_value.py", "DEVELOPERS"): "developer counts tabulated (output grid)",
    ("E9_dataset_value.py", "HEAT_T"): "diffusion time of the heat target (specimen)",
    ("E8_incremental_production.py", "TBTU_TO_MWH"): "unit (1 TBtu = 1e6 MMBtu, x registry MWh/MMBtu)",
}
# Physical constants that must be read from the registry, never re-typed.
KNOWN_CONSTANTS = {273.15: "0 degC in K", 101325.0: "standard atmosphere",
                   9.80665: "g_n", 9.81: "g (rounded)", 0.622: "Mw/Ma (rounded)",
                   8.617333262e-5: "k_B", 1055.05585262: "Btu", 0.29307107: "MWh/MMBtu",
                   318.6: "toluene Tc", 154.0: "R245fa Tc"}


def sig_digits(x):
    s = ("%.12g" % abs(x)).split("e")[0].replace(".", "").strip("0")
    return len(s)


def deps_ok():
    order = list(REG)
    pos = {k: i for i, k in enumerate(order)}
    bad = []
    for k, p in REG.items():
        if p.kind == "DERIVED" and not p.deps:
            bad.append(f"{k}: DERIVED without dependencies")
        for d in p.deps:
            if d not in REG:
                bad.append(f"{k}: unknown dependency {d}")
            elif pos[d] >= pos[k]:
                bad.append(f"{k}: depends on later entry {d}")
    return bad


def bib_keys():
    if not os.path.exists(BIB):
        return set()
    return set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", open(BIB).read()))


def literals(path):
    """(value, line) for every numeric literal in a script."""
    tree = ast.parse(open(os.path.join(ROOT, path)).read())
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            out.append((float(node.value), node.lineno))
    return out


def reads(path):
    """Registry ids an experiment reads: through v()/REG[], or held as an id
    string in a table the experiment passes to v() (e.g. E8's INDUSTRIES)."""
    src = open(os.path.join(ROOT, path)).read()
    held = {s for s in re.findall(r'"([A-Za-z0-9_]+)"', src) if s in REG} \
        if re.search(r"\bv\(\s*[a-z_]+\s*\)", src) else set()
    return held | set(re.findall(r'(?:\bv|REG)\(\s*"([A-Za-z0-9_]+)"\s*\)', src)) | \
        set(re.findall(r'REG\[\s*"([A-Za-z0-9_]+)"\s*\]', src)) | \
        set(re.findall(r'v\(\s*\'([A-Za-z0-9_]+)\'\s*\)', src))


def main():
    V = Verdicts("DEPENDENCY CHAIN")
    kinds = {}
    for p in REG.values():
        kinds.setdefault(p.kind, []).append(p.id)
    edges = sum(len(p.deps) for p in REG.values())

    # ---------------------------------------------------------------- D1
    bad = deps_ok()
    V.check("D1 closure: DERIVED entries name existing, earlier dependencies (acyclic)",
            not bad, "; ".join(bad) or "%d edges" % edges)

    # ---------------------------------------------------------------- D2
    keys = bib_keys()
    nosrc = [p.id for p in REG.values() if p.kind == "BENCH" and not p.src]
    V.check("D2 provenance: every BENCH entry carries a citation", not nosrc, ", ".join(nosrc))
    missing = sorted({p.src for p in REG.values() if p.src and p.src not in keys})
    V.check("D2 provenance: every citation key resolves in sn-bibliography.bib",
            not missing, ", ".join(missing) or "%d keys" % len({p.src for p in REG.values()
                                                               if p.src}))
    lawless = [p.id for p in REG.values() if p.kind == "LAW" and not p.src
               and not p.basis.lower().startswith(("365", "definition"))
               and "definition" not in p.basis.lower()]
    V.check("D2 provenance: every LAW entry is cited or is a definition", not lawless,
            ", ".join(lawless))

    # ---------------------------------------------------------------- D3
    out = []
    for p in REG.values():
        if p.sweep is not None:
            lo, hi = p.sweep
            if not (lo <= p.value <= hi):
                out.append(p.id)
    V.check("D3 ranges: every sweep contains its nominal value", not out, ", ".join(out))
    ends = []
    for p in REG.values():
        if p.kind == "BENCH" and p.sweep is not None:
            lo, hi = p.sweep
            ok = ((p.worse == "lo" and p.value == lo) or (p.worse == "hi" and p.value == hi)
                  or p.worse == "both")
            if not ok:
                ends.append(p.id)
    V.check("D3 ranges: every swept BENCH entry declares its least favourable end and "
            "takes it as nominal", not ends, ", ".join(ends))

    # ---------------------------------------------------------------- D4
    used = {}
    for s in SCRIPTS:
        for k in reads(s):
            used.setdefault(k, set()).add(os.path.basename(s))
    for p in REG.values():
        for d in p.deps:
            used.setdefault(d, set()).add("registry:" + p.id)
    # the registry's own module-level use (e.g. K0, seawater_cp)
    reg_src = open(os.path.join(ROOT, "registry.py")).read()
    for k in REG:
        if re.search(r'v\("%s"\)' % k, reg_src.split("# ================================="
                                                      "================================ DERIVED")[-1]):
            used.setdefault(k, set()).add("registry")
    unknown = sorted(set(used) - set(REG))
    V.check("D4 usage: every entry an experiment reads exists in the registry",
            not unknown, ", ".join(unknown))
    orphans = sorted(k for k in REG if k not in used and not k.startswith("eq_")
                     and k != "coolprop")
    V.check("D4 usage: no orphan inputs (every entry is consumed)", not orphans,
            ", ".join(orphans))

    # ---------------------------------------------------------------- D5
    # (a) no module-level numeric constant except declared protocol constants
    undeclared = []
    for s in SCRIPTS:
        base = os.path.basename(s)
        tree = ast.parse(open(os.path.join(ROOT, s)).read())
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            nums = [c for c in ast.walk(node.value) if isinstance(c, ast.Constant)
                    and isinstance(c.value, (int, float)) and not isinstance(c.value, bool)]
            tgt = node.targets[0] if isinstance(node, ast.Assign) else node.target
            name = getattr(tgt, "id", "?")
            if nums and (base, name) not in PROTOCOL:
                undeclared.append(f"{base}:{name}")
    print("D5 declared protocol constants (output grids, specimen definitions, units):")
    for (base, name), why in sorted(PROTOCOL.items()):
        print("  %-26s %-12s %s" % (base, name, why))
    V.check("D5 no module-level numeric constant outside the declared protocol",
            not undeclared, ", ".join(undeclared))
    # (b) no distinctive number (three or more significant digits) that equals a
    # registry value or a physical constant appears anywhere in an experiment
    distinctive = {}
    for p in REG.values():
        if isinstance(p.value, (int, float)) and not isinstance(p.value, bool) \
                and sig_digits(p.value) >= 3:
            distinctive.setdefault(float(p.value), []).append(p.id)
    for c, name in KNOWN_CONSTANTS.items():
        distinctive.setdefault(c, []).append(name)
    shadows = []
    for s in SCRIPTS:
        base = os.path.basename(s)
        for val, line in literals(s):
            if val in distinctive:
                shadows.append("%s:%d %g (= %s)" % (base, line, val, "/".join(distinctive[val])))
    V.check("D5 no experiment re-types a registry value or physical constant",
            not shadows, "; ".join(shadows) or "%d distinctive values screened"
            % len(distinctive))

    # ---------------------------------------------------------------- D6
    import conventions as C
    import E1_geometric_heat as E1
    import E3_cascade as E3
    import E4_leakage_crossover as E4
    import E6_best_uses as E6
    pairs = [
        ("conventions.PUE_HYPERSCALE", C.PUE_HYPERSCALE, v("pue_hyperscale")),
        ("conventions.PUE_INDUSTRY_AVG", C.PUE_INDUSTRY_AVG, v("pue_avg")),
        ("conventions.PRICE_USD_PER_MWH", C.PRICE_USD_PER_MWH, v("elec_price")),
        ("conventions.CP_AIR", C.CP_AIR, v("cp_air")),
        ("E1.R_TH", E1.R_TH, v("rth")),
        ("E1.LEAK_FRAC_REF", E1.LEAK_FRAC_REF, v("leak_frac")),
        ("E1.H100_TDP", E1.H100_TDP, v("h100_tdp")),
        ("E3 Si class coolant", dict((n, t) for n, t, _ in E3.CHIPS)["Si"], v("t_coolant_si")),
        ("E3 SiC-max class coolant", dict((n, t) for n, t, _ in E3.CHIPS)["SiC-max"],
         v("t_coolant_sic_max")),
        ("E3 furnace overhead", E3.NOMINAL["furnace_overhead"], v("furnace_overhead")),
        ("E3 MED steam", E3.NOMINAL["med_steam_C"], v("med_steam")),
        ("E3 ORC ceiling", E3.NOMINAL["eta_orc_ceiling"], v("eta_orc_ceiling")),
        ("E4 overhead", E4.OVERHEAD, v("furnace_overhead")),
        ("E6 boiler efficiency", E6.ETA_FIRED, v("eta_boiler")),
        ("E6 CO2 factor", E6.CO2_T_PER_MWH_GAS, v("co2_t_per_mwh_gas")),
    ]
    for name, got, want in pairs:
        V.check(f"D6 coherence: {name} equals the registry", got == want, "%r" % got)
    # independently computed results that must agree
    sic = [c for c in E3.CHIPS if c[0] == "SiC-300"][0]
    rA = E3.scenario(sic, "A", E3.NOMINAL)
    rec_e3 = (rA["w_cycle"] + rA["p_tower"]) / (E3.IT_POWER_MW * 1e6)
    rec_e4 = E4.best_recovery(sic[1])[2]
    V.check("D6 coherence: recovery at the SiC design point, E3 scenario = E4 best_recovery",
            abs(rec_e3 - rec_e4) < 1e-9, "%.6f vs %.6f" % (rec_e3, rec_e4))
    sink = C.T_AMBIENT_C + E3.NOMINAL["sink_approach_K"]
    e6 = E6.cycle_to(sic[1], sink)[1]
    V.check("D6 coherence: cycle efficiency at the SiC design point, E3 = E6",
            abs(e6 - rA["cycle"]["eta"]) < 1e-12, "%.6f" % e6)
    pt = E4.chip_point(E4.EG_SI, v("tj_max_si"), v("t_coolant_si"), E4.chip_params())
    V.check("D6 coherence: the derived silicon coolant carries exactly full power at Tj,max",
            abs(pt["p_total"] - v("h100_tdp")) < 1e-6 * v("h100_tdp")
            and abs(pt["tj"] - v("tj_max_si")) < 1e-3, "Tj %.3f degC" % pt["tj"])

    # ---------------------------------------------------------------- D8
    # every swept entry is exercised at its range ends by some experiment:
    # sampled in E7, cornered in E4.2, or its .sweep read by an experiment
    import E7_uncertainty as E7
    exercised = set(E7.SAMPLED)
    for s in SCRIPTS:
        src = open(os.path.join(ROOT, s)).read()
        exercised |= set(re.findall(r'REG\[\s*"([A-Za-z0-9_]+)"\s*\]\.sweep', src))
        exercised |= set(re.findall(r'"([A-Za-z0-9_]+)"', src.split("keys = (")[1].split(")")[0])
                         ) if "keys = (" in src else set()
        if "OAT = {" in src:
            exercised |= set(re.findall(r'"([A-Za-z0-9_]+)":', src.split("OAT = {")[1]
                                        .split("}")[0]))
    gaps = sorted(p.id for p in REG.values() if p.sweep is not None and p.id not in exercised)
    V.check("D8 every swept entry is exercised at its range ends by an experiment",
            not gaps, ", ".join(gaps))

    # ---------------------------------------------------------------- D7
    print("\nD7 census")
    for k in ("LAW", "BENCH", "DERIVED", "DESIGN", "CLAIM"):
        print("  %-8s %3d" % (k, len(kinds.get(k, []))))
    print("  total    %3d nodes, %d derivation edges" % (len(REG), edges))
    swept = [p.id for p in REG.values() if p.sweep is not None]
    print("  swept    %3d (%s)" % (len(swept), ", ".join(swept)))
    print("\n  entries read by each experiment:")
    for s in SCRIPTS:
        r = sorted(reads(s))
        print("  %-28s %3d" % (os.path.basename(s), len(r)))
    os.makedirs(os.path.join(ROOT, "Experiment Logs"), exist_ok=True)
    with open(os.path.join(ROOT, "Experiment Logs", "registry_table.md"), "w") as f:
        f.write("| id | value | unit | kind | basis | source | depends on | range | read by |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for p in REG.values():
            val = ("%.6g" % p.value if isinstance(p.value, float) else
                   (str(p.value) if p.value is not None else "(relation)"))
            f.write("| %s | %s | %s | %s | %s | %s | %s | %s | %s |\n" % (
                p.id, val, p.unit, p.kind, p.basis.replace("|", "/"), p.src or "",
                ", ".join(p.deps), "" if p.sweep is None else "%g-%g" % p.sweep,
                ", ".join(sorted(used.get(p.id, [])))))
    print("\n  wrote Experiment Logs/registry_table.md")
    V.finish()


if __name__ == "__main__":
    main()
