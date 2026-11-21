"""The dependency registry.

Every number that enters any experiment is defined here exactly once, with
its kind and its basis. Nothing else in the archive may introduce an input.

Kinds
  LAW      a physical law, an exact constant or a definition
  BENCH    a published benchmark, carried with its citation key
           (keys resolve in sn-bibliography.bib)
  DERIVED  computed here from other registry entries, which it names
  CLAIM    a statement of the originating post; tested by an experiment, never
           used as an input to another result
  DESIGN   a design choice of this study (operating point, approach
           temperature, scale); every design parameter that can move a result
           carries a sweep range that E7 exercises

Rule for benchmark ranges: where a source gives a range, the nominal value is
the end least favourable to the paper's claims (declared as `worse`), and the
range is swept. A benchmark quoted as a single value or a one-sided bound is
used at that value and not swept: no range is invented for it.

dependency_graph.py verifies that this registry is closed and acyclic, that
every BENCH resolves to a bibliography entry, that every DERIVED entry names
its dependencies, and that no experiment defines an input of its own.
"""
from CoolProp.CoolProp import PropsSI

REG = {}


class P:
    __slots__ = ("id", "value", "unit", "kind", "src", "basis", "deps", "sweep", "worse")

    def __init__(self, id, value, unit, kind, basis, src=None, deps=(), sweep=None,
                 worse=None):
        """worse: for a swept BENCH entry, which end of the range is least
        favourable to the paper's claims ("lo" or "hi"), or "both" when every
        experiment that uses it is run at both ends."""
        self.id, self.value, self.unit, self.kind = id, value, unit, kind
        self.basis, self.src, self.deps, self.sweep = basis, src, tuple(deps), sweep
        self.worse = worse
        if id in REG:
            raise ValueError(f"duplicate registry id {id}")
        REG[id] = self


def v(i):
    return REG[i].value


# ===================================================================== LAW
P("g_n", 9.80665, "m s^-2", "LAW", "standard acceleration of gravity, exact", "BIPM2019")
P("zero_C_in_K", 273.15, "K", "LAW", "0 degC in kelvin, exact", "BIPM2019")
P("k_B_eV", 8.617333262e-5, "eV K^-1", "LAW", "Boltzmann constant, CODATA 2018", "Tiesinga2021")
P("J_per_Btu", 1055.05585262, "J", "LAW", "International Table British thermal unit", "ThompsonTaylor2008")
P("kg_per_lb", 0.45359237, "kg", "LAW", "international avoirdupois pound, exact", "ThompsonTaylor2008")
P("hours_per_year", 8760.0, "h", "LAW", "365 x 24, definition of the annual basis")
P("p_atm", 101325.0, "Pa", "LAW", "standard atmosphere, exact", "BIPM2019")
P("eq_first_law", None, "-", "LAW", "energy conservation: electrical power into "
  "computation leaves as heat (computation stores negligible energy)", "Landauer1961")
P("eq_carnot", None, "-", "LAW", "eta <= 1 - Tc/Th for any heat engine", "Callen1985")
P("eq_cascade", None, "-", "LAW", "eta_total = eta1 + (1-eta1) eta2, from the first law",
  "Callen1985")
P("eq_chimney", None, "-", "LAW", "ideal chimney efficiency g H / (cp T0), from "
  "hydrostatics and the ideal-gas law (Eq. 14)", "ZhouXu2016")
P("eq_intrinsic", None, "-", "LAW", "n_i proportional to T^1.5 exp(-Eg / 2kT)", "SzeNg2007")
P("eq_virtual_T", None, "-", "LAW", "virtual temperature Tv = T (1 + w/0.622)/(1 + w)",
  "WallaceHobbs2006")
P("eq_cotan", None, "-", "LAW", "cotangent Laplace-Beltrami with lumped mass",
  "PinkallPolthier1993")
P("eq_roofline", None, "-", "LAW", "attainable FLOP/s = min(peak, intensity x bandwidth)",
  "Williams2009")
P("eq_eig_flops", 9.0, "n^3", "LAW", "symmetric QR, all eigenpairs ~ 9 n^3 flops",
  "GolubVanLoan2013")
P("eq_lanczos_flops", 2.0, "n m^2", "LAW", "Lanczos with full reorthogonalisation: "
  "~2 n m^2 flops for m steps (plus m sparse products)", "GolubVanLoan2013")
P("coolprop", None, "-", "LAW", "reference equations of state via CoolProp", "Bell2014")
P("eq_seawater_cp", None, "-", "LAW", "seawater cp correlation (Jamieson et al.), "
  "0-180 degC, 0-180 g/kg, +-0.28%", "Sharqawy2010")

# =================================================================== BENCH
# accelerator
P("h100_fp64_tc", 67e12, "FLOP s^-1", "BENCH", "H100 SXM FP64 Tensor Core peak", "NVIDIA2024H100")
P("h100_bw", 3.35e12, "B s^-1", "BENCH", "H100 SXM HBM3 bandwidth", "NVIDIA2024H100")
P("h100_tdp", 700.0, "W", "BENCH", "H100 SXM maximum thermal design power", "NVIDIA2024H100")
P("h100_die_mm2", 814.0, "mm^2", "BENCH", "GH100 die size", "NVIDIA2022Hopper")
P("eagle_rmax", 561.20e15, "FLOP s^-1", "BENCH", "Eagle (H100) HPL Rmax, June 2024", "TOP5002024")
P("eagle_rpeak", 846.84e15, "FLOP s^-1", "BENCH", "Eagle (H100) Rpeak, June 2024", "TOP5002024")
# data-centre baselines
P("pue_hyperscale", 1.09, "-", "BENCH", "Google fleet annual PUE 2025 (best practice)", "Google2026PUE")
P("pue_avg", 1.4, "-", "BENCH", "US average PUE 2023 (LBNL); the global 2024 survey "
  "average 1.56 is less favourable to the baseline", "Shehabi2024")
P("pue_avg_global", 1.56, "-", "BENCH", "industry average PUE, 2024 survey (p. 7)", "Donnellan2024")
P("wue_avg", 0.36, "L kWh^-1", "BENCH", "US average site WUE through 2023", "Shehabi2024")
P("wue_hyperscale", 0.1, "L kWh^-1", "BENCH", "hyperscale WUE 0.1-0.3; nominal is the "
  "end least favourable to the furnace", "Shehabi2024", sweep=(0.1, 0.3), worse="lo")
# semiconductors
P("eg_si", 1.12, "eV", "BENCH", "silicon bandgap, 300 K", "SzeNg2007")
P("eg_sic", 3.26, "eV", "BENCH", "4H-SiC bandgap, room temperature", "KimotoCooper2014")
P("tj_max_si", 100.0, "degC", "BENCH", "silicon logic Tj,max 100-110 degC; both ends "
  "exercised wherever it enters (E4.2)", "IntelTjmax", sweep=(100.0, 110.0), worse="both")
P("tj_max_sic", 500.0, "degC", "BENCH", "4H-SiC JFET ICs operated over one year at 500 degC "
  "in air (about 10,000 h, tests still running)", "Neudeck2018")
P("rth_area_demo", 0.090, "K cm^2 W^-1", "BENCH", "microchannel heat sink, 790 W/cm^2 at "
  "71 K rise", "TuckermanPease1981")
# power cycles
P("eta_exp_orc", 0.60, "-", "BENCH", "ORC expander overall isentropic efficiency: "
  "maximum around 70% with generator losses (Sec. 10); screw expanders not much above "
  "60% (Sec. 6.2.2); nominal is the lower end", "Quoilin2013", sweep=(0.60, 0.70),
  worse="lo")
P("eta_pump_orc", 0.25, "-", "BENCH", "ORC feed pump overall efficiency: highest measured "
  "value 25% (Sec. 8.2); centrifugal pumps claimed above 60% but unconfirmed; nominal "
  "is the measured end", "Quoilin2013", sweep=(0.25, 0.60), worse="lo")
P("eta_orc_ceiling", 0.24, "-", "BENCH", "the efficiency of current high-temperature "
  "ORCs does not exceed 24% (Sec. 4)", "Quoilin2013")
P("eta_turb_sco2", 0.90, "-", "BENCH", "sCO2 turbine efficiency 90% (Sec. 2.2, p. 9)",
  "Dostal2004")
P("eta_comp_sco2", 0.89, "-", "BENCH", "sCO2 compressor efficiency 89% (Sec. 2.2, p. 11)",
  "Dostal2004")
P("t_comp_in_sco2_ref", 32.0, "degC", "BENCH", "sCO2 compressor inlet 32 degC (Sec. 2.2, "
  "p. 11); comparison only, this study derives its own from the heat sink", "Dostal2004")
P("p_high_sco2", 20.0e6, "Pa", "BENCH", "sCO2 cycle high pressure", "Dostal2004")
P("eta_sco2_recomp_550", 0.453, "-", "BENCH", "recompression sCO2 at 550 degC, 20 MPa "
  "(upper bound for a simple cycle at lower temperature)", "Dostal2004")
P("eta_tower_turb", 0.77, "-", "BENCH", "updraft-tower turbine efficiency 77-80% "
  "(Table 4); nominal is the lower end", "ZhouXu2016", sweep=(0.77, 0.80), worse="lo")
P("tower_pressure_share", 2.0 / 3.0, "-", "BENCH", "optimal turbine share of the "
  "available pressure difference (Table 7)", "ZhouXu2016")
# desalination
P("med_tbt", 66.0, "degC", "BENCH", "MED top brine temperature 66-72 degC; nominal is "
  "the lower end (fewer effects)", "AlKaraghouli2011", sweep=(66.0, 72.0), worse="lo")
P("med_kwh_m3", 2.5, "kWh m^-3", "BENCH", "MED electrical energy 1.5-2.5 kWh/m3; nominal "
  "is the upper end", "AlKaraghouli2011", sweep=(1.5, 2.5), worse="hi")
P("med_gor_lo", 8.0, "-", "BENCH", "MED gain output ratio 8-12: lower end",
  "AlKaraghouli2011")
P("med_gor_hi", 12.0, "-", "BENCH", "MED gain output ratio 8-12: upper end",
  "AlKaraghouli2011")
P("s_seawater", 35.0, "g kg^-1", "BENCH", "reference seawater salinity", "Sharqawy2010")
P("water_price", 0.5, "USD m^-3", "BENCH", "large-plant desalinated water cost "
  "0.5-1.0 USD/m3; nominal is the lower end", "Ghaffour2013", sweep=(0.5, 1.0),
  worse="lo")
# energy prices and factors
P("elec_price", 85.1, "USD MWh^-1", "BENCH", "US average industrial electricity price, "
  "2025", "EIA2026EPM")
P("henry_hub", 3.48, "USD MMBtu^-1", "BENCH", "Henry Hub 2026 average", "EIA2026STEO")
P("ttf_2025", 11.96, "USD MMBtu^-1", "BENCH", "natural gas, Europe (Netherlands TTF), "
  "2025 average; range is the lowest and highest monthly values printed for October "
  "2025 to April 2026; both ends exercised (E6.3)", "WorldBank2026",
  sweep=(9.48, 17.91), worse="both")
P("co2_gas_kg_mmbtu", 53.06, "kg MMBtu^-1", "BENCH", "natural gas CO2 factor", "EPA2025")
P("eta_boiler", 0.857, "-", "BENCH", "natural-gas boiler combustion efficiency with "
  "economiser", "DOE2012Steam")
P("kwh_per_kg_h2", 50.0, "kWh kg^-1", "BENCH", "electrolyser system 50-83 kWh/kg; nominal "
  "is the end most favourable to hydrogen, the competing use", "IRENA2020",
  sweep=(50.0, 83.0), worse="lo")
# process temperatures
P("t_pyrolysis", 500.0, "degC", "BENCH", "pyrolysis producing liquid oils and waxes at "
  "500-650 degC; nominal is the lower end (most reachable)", "AlSalem2017",
  sweep=(500.0, 650.0), worse="lo")
P("t_amine_regen", 120.0, "degC", "BENCH", "amine stripping at 100-120 degC; upper end",
  "Rochelle2009")
# industrial value and heat (E8: incremental production)
# EIA MECS 2018 Table 6.1: energy consumed per dollar of value added (thousand Btu)
P("mecs_va_324110", 28.6, "kBtu USD^-1", "BENCH", "petroleum refineries (NAICS 324110), "
  "Table 6.1", "EIA2021MECS")
P("mecs_va_325110", 23.1, "kBtu USD^-1", "BENCH", "petrochemicals (NAICS 325110), Table 6.1",
  "EIA2021MECS")
P("mecs_va_325199", 19.8, "kBtu USD^-1", "BENCH", "other basic organic chemicals "
  "(NAICS 325199), Table 6.1", "EIA2021MECS")
P("mecs_va_325211", 20.5, "kBtu USD^-1", "BENCH", "plastics materials and resins "
  "(NAICS 325211), Table 6.1", "EIA2021MECS")
P("mecs_va_mfg", 5.6, "kBtu USD^-1", "BENCH", "all US manufacturing, Table 6.1",
  "EIA2021MECS")
# EIA MECS 2018 Table 3.2: fuel consumption (trillion Btu)
P("mecs_fuel_324110", 3375.0, "TBtu", "BENCH", "petroleum refineries, total fuel, Table 3.2",
  "EIA2021MECS")
P("mecs_other_324110", 2192.0, "TBtu", "BENCH", "petroleum refineries, 'Other' fuels "
  "(mainly byproduct still gas), Table 3.2", "EIA2021MECS")
P("mecs_fuel_325110", 569.0, "TBtu", "BENCH", "petrochemicals, total fuel, Table 3.2",
  "EIA2021MECS")
P("mecs_fuel_325199", 742.0, "TBtu", "BENCH", "other basic organic chemicals, total fuel, "
  "Table 3.2", "EIA2021MECS")
P("mecs_fuel_325211", 668.0, "TBtu", "BENCH", "plastics materials and resins, total fuel, "
  "Table 3.2", "EIA2021MECS")
# NREL: US industrial process heat by temperature (2014)
P("iph_us", 11000.0, "TBtu", "BENCH", "US industrial process heat demand (Sec. 1.7, Table 2)",
  "McMillan2021")
P("iph_us_below300", 8010.0, "TBtu", "BENCH", "US process heat below 300 degC, about 73% "
  "(Sec. 2.1)", "McMillan2021")
P("iph_refining", 2210.0, "TBtu", "BENCH", "petroleum refineries (324110) process heat "
  "(Table 3)", "McMillan2021")
P("iph_refining_100_300", 1380.0, "TBtu", "BENCH", "petroleum refineries process heat at "
  "100-300 degC, about 63% (Table 3)", "McMillan2021")
P("iph_share_stated", 0.73, "-", "BENCH", "share below 300 degC as stated (Sec. 2.1)",
  "McMillan2021")
P("iph_refining_share_stated", 0.63, "-", "BENCH", "refinery share at 100-300 degC as "
  "stated (text, p. 14)", "McMillan2021")
P("t_iph_band_lo", 100.0, "degC", "BENCH", "lower edge of the reported 100-300 degC band",
  "McMillan2021")
P("t_iph_band", 300.0, "degC", "BENCH", "upper edge of the reported band", "McMillan2021")
# steam cracking and polymers
P("cracker_pyrolysis_share", 0.65, "-", "BENCH", "pyrolysis section share of naphtha "
  "cracker process energy (abstract)", "Ren2006")
P("t_cracker_lo", 750.0, "degC", "BENCH", "steam-cracking temperature 750-900 degC; lower "
  "end (Sec. 2.1)", "Ren2008")
P("bw_ethylene", 7071.0, "Btu lb^-1", "BENCH", "ethylene, current typical onsite energy "
  "(Table 4-5)", "Brueske2015")
P("bw_hdpe", 1037.0, "Btu lb^-1", "BENCH", "HDPE (Table 4-5)", "Brueske2015")
P("bw_lldpe", 871.0, "Btu lb^-1", "BENCH", "LLDPE (Table 4-5)", "Brueske2015")
P("bw_ldpe", 1143.0, "Btu lb^-1", "BENCH", "LDPE (Table 4-5)", "Brueske2015")
P("bw_pp", 616.0, "Btu lb^-1", "BENCH", "polypropylene (Table 4-5)", "Brueske2015")
P("bw_ethylene_mlb", 52864.0, "million lb", "BENCH", "US ethylene production 2010 "
  "(Table 3-1)", "Brueske2015")
P("bw_ethylene_tbtu", 374.0, "TBtu", "BENCH", "ethylene onsite current typical energy "
  "(Table 4-5)", "Brueske2015")

# geometry corpora
P("n_abc", 1_000_000, "models", "BENCH", "ABC CAD dataset", "Koch2019")
P("n_shapenet", 51_300, "models", "BENCH", "ShapeNetCore", "Chang2015")
P("n_thingi", 10_000, "models", "BENCH", "Thingi10K", "ZhouJacobson2016")
P("n_pdb", 200_000, "structures", "BENCH", "PDB, approximately 200,000 experimental "
  "structures", "Burley2023")

# ================================================================== DESIGN
P("t_ambient", 25.0, "degC", "DESIGN", "standard ambient temperature 298.15 K", "IUPACGoldBook")
P("t_seawater", 25.0, "degC", "DESIGN", "seawater intake temperature")
P("it_power_mw", 100.0, "MW", "DESIGN", "normalisation scale; all results are linear in it")
P("loop_drop", 10.0, "K", "DESIGN", "coolant loop temperature drop", sweep=(5.0, 15.0))
P("pinch", 10.0, "K", "DESIGN", "minimum approach, source to working fluid", "LinnhoffHindmarsh1983",
  sweep=(5.0, 15.0))
P("sink_approach", 10.0, "K", "DESIGN", "condensing temperature above ambient",
  "LinnhoffHindmarsh1983", sweep=(8.0, 20.0))
P("recup_min_pinch", 5.0, "K", "DESIGN", "recuperator minimum temperature difference",
  sweep=(5.0, 15.0))
P("recup_eff", 1.0, "-", "DESIGN", "recuperator duty limited by its pinch alone")
P("subcrit_margin", 2.0, "K", "DESIGN", "subcritical ORC evaporates at least this far "
  "below the working fluid's critical temperature", sweep=(2.0, 10.0))
P("p_low_sco2", 7.7e6, "Pa", "DESIGN", "sCO2 low pressure, just above critical 7.38 MPa")
P("med_steam_margin", 5.0, "K", "DESIGN", "heating steam above top brine temperature")
P("med_steam_approach", 3.0, "K", "DESIGN", "heat source above heating steam")
P("med_last", 40.0, "degC", "DESIGN", "last effect temperature")
P("med_step", 3.0, "K", "DESIGN", "temperature drop per effect")
P("med_feed", 35.0, "degC", "DESIGN", "feed temperature after final-condenser preheat")
P("med_brine_salinity", 60.0, "g kg^-1", "DESIGN", "brine reject salinity", sweep=(55.0, 70.0))
P("med_loss", 0.01, "-", "DESIGN", "heat lost to ambient per effect", sweep=(0.0, 0.03))
P("tower_H", 200.0, "m", "DESIGN", "tower height", sweep=(100.0, 300.0))
P("rth", 0.05, "K W^-1", "DESIGN", "junction-to-coolant resistance; above the best "
  "demonstrated value, hence conservative", sweep=(0.0111, 0.05))
P("leak_frac", 0.15, "-", "DESIGN", "silicon leakage share of power at the baseline "
  "junction; leakage approaching dynamic power is reported (kim2003)", "Kim2003",
  sweep=(0.05, 0.50))
P("t_base_junction", 85.0, "degC", "DESIGN", "baseline silicon junction temperature",
  sweep=(65.0, 85.0))
P("t_sic_design", 300.0, "degC", "DESIGN", "SiC design-point coolant temperature: the "
  "hot-chip temperature of the originating proposal")
P("approach_process", 10.0, "K", "DESIGN", "supply above process requirement",
  "LinnhoffHindmarsh1983")
P("steam_bands", (150.0, 200.0, 250.0), "degC", "DESIGN", "steam delivery temperatures; "
  "saturation pressures derived")
P("slice_level", 4, "-", "DESIGN", "icosphere subdivision level of the dataset slice "
  "(2,562 vertices)")
P("slice_k", 200, "modes", "DESIGN", "eigenpairs stored per surface in the slice")
P("spectral_fraction", 0.05, "-", "DESIGN", "share of the spectrum a dataset entry stores "
  "for downstream preconditioning (E9.3)", sweep=(0.02, 0.10))
P("raw_feature_degree", 6, "-", "DESIGN", "degree of the raw-coordinate monomial features "
  "in E9.2; the dataset basis is given the same number of features")
P("solve_tol", 1e-6, "-", "DESIGN", "relative energy-norm tolerance of every iterative "
  "solve (E2e, E9.3)")
P("tier_n_small", 1e5, "vertices", "DESIGN", "mesh resolution of tiers T1 and T3")
P("tier_n_large", 1e6, "vertices", "DESIGN", "mesh resolution of tiers T2, T4 and T5")
P("tier_k_small", 1e3, "modes", "DESIGN", "eigenpairs computed at tier T1")
P("tier_k_large", 5e3, "modes", "DESIGN", "eigenpairs computed at tier T2")
P("depth_families", 100, "metrics", "DESIGN", "families of metrics per geometry (T5)")
P("rh_ambient", 0.5, "-", "DESIGN", "ambient relative humidity", sweep=(0.3, 0.8))
P("mc_samples", 300, "-", "DESIGN", "Monte Carlo sample count (E7)")
P("seed", 46, "-", "DESIGN", "random seed for every stochastic experiment")

# =================================================================== CLAIM
P("post_t_low", 80.0, "degC", "CLAIM", "originating post: chip coolant today (~80 degC)")
P("post_t_high", 300.0, "degC", "CLAIM", "originating post: hot-chip coolant (~300 degC)")
P("post_carnot_low", 0.15, "-", "CLAIM", "originating post: Carnot ceiling ~15% at 80 degC")
P("post_carnot_high", 0.48, "-", "CLAIM", "originating post: Carnot ceiling ~48% at 300 degC")
P("post_recovery_low", 0.05, "-", "CLAIM", "originating post: ~5% recovered at ~80 degC")
P("post_orc_high", 0.20, "-", "CLAIM", "originating post: ORC ~20% at ~300 degC")
P("post_tower", 0.01, "-", "CLAIM", "originating post: tower ~1% of rejected heat")
P("post_ratio", 4.0, "-", "CLAIM", "originating post: ~4x the recovered energy")
P("post_tol", 0.01, "-", "CLAIM", "the post states percentages to the nearest point "
  "('~'); a claim is reproduced within one point")

# ================================================================= DERIVED
K0 = v("zero_C_in_K")
P("cp_air", PropsSI("C", "T", K0 + v("t_ambient"), "P", v("p_atm"), "Air"), "J kg^-1 K^-1",
  "DERIVED", "dry air cp at ambient", deps=("coolprop", "t_ambient", "p_atm"))
P("t_comp_in_sco2", v("t_ambient") + v("sink_approach"), "degC", "DERIVED",
  "sCO2 compressor inlet: the same heat sink as the ORC condenser",
  deps=("t_ambient", "sink_approach"))
P("eps_mw", PropsSI("M", "Water") / PropsSI("M", "Air"), "-", "DERIVED",
  "ratio of molar masses, water to dry air", deps=("coolprop",))
P("mwh_per_mmbtu", 1e6 * v("J_per_Btu") / 3.6e9, "MWh MMBtu^-1", "DERIVED",
  "1 MMBtu in MWh", deps=("J_per_Btu",))
P("sustained", v("eagle_rmax") / v("eagle_rpeak"), "-", "DERIVED",
  "sustained fraction of peak on dense linear algebra (HPL)",
  deps=("eagle_rmax", "eagle_rpeak"))
P("flop_per_joule", v("sustained") * v("h100_fp64_tc") / v("h100_tdp"), "FLOP J^-1",
  "DERIVED", "sustained dense FLOP per joule", deps=("sustained", "h100_fp64_tc", "h100_tdp"))
P("ridge", v("h100_fp64_tc") / v("h100_bw"), "FLOP B^-1", "DERIVED", "roofline ridge point",
  deps=("h100_fp64_tc", "h100_bw", "eq_roofline"))
P("h100_die_cm2", v("h100_die_mm2") / 100.0, "cm^2", "DERIVED", "die area",
  deps=("h100_die_mm2",))
P("rth_best_demo", v("rth_area_demo") / v("h100_die_cm2"), "K W^-1", "DERIVED",
  "best demonstrated resistance over an H100-size die",
  deps=("rth_area_demo", "h100_die_cm2"))
P("t_coolant_si", v("tj_max_si") - v("rth") * v("h100_tdp"), "degC", "DERIVED",
  "hottest silicon coolant at full power: Tj,max - Rth P",
  deps=("tj_max_si", "rth", "h100_tdp"))
P("t_coolant_sic_max", v("tj_max_sic") - v("rth") * v("h100_tdp"), "degC", "DERIVED",
  "hottest SiC coolant at full power: Tj,max - Rth P",
  deps=("tj_max_sic", "rth", "h100_tdp"))
P("furnace_overhead", v("pue_hyperscale") - 1.0, "-", "DERIVED",
  "furnace facility overhead charged at the best hyperscale level (conservative)",
  deps=("pue_hyperscale",))
P("med_steam", v("med_tbt") + v("med_steam_margin"), "degC", "DERIVED",
  "MED heating steam temperature", deps=("med_tbt", "med_steam_margin"))
P("co2_t_per_mwh_gas", 1e-3 * v("co2_gas_kg_mmbtu") / v("mwh_per_mmbtu"), "t MWh^-1",
  "DERIVED", "natural gas CO2 per MWh", deps=("co2_gas_kg_mmbtu", "mwh_per_mmbtu"))
P("gas_us", v("henry_hub") / v("mwh_per_mmbtu"), "USD MWh^-1", "DERIVED",
  "Henry Hub per MWh", deps=("henry_hub", "mwh_per_mmbtu"))
P("gas_eu", v("ttf_2025") / v("mwh_per_mmbtu"), "USD MWh^-1", "DERIVED",
  "TTF 2025 average per MWh", deps=("ttf_2025", "mwh_per_mmbtu"))
P("n_corpus", v("n_abc") + v("n_shapenet") + v("n_thingi") + v("n_pdb"), "geometries",
  "DERIVED", "public geometry corpus", deps=("n_abc", "n_shapenet", "n_thingi", "n_pdb"))
P("steam_sat_bar", tuple(PropsSI("P", "T", K0 + t, "Q", 0, "Water") / 1e5
                         for t in v("steam_bands")), "bar", "DERIVED",
  "saturation pressure of each steam band", deps=("steam_bands", "coolprop"))


def seawater_cp(t_c, s=None):
    """Sharqawy et al. (2010) Eq. 9 (Jamieson et al.), J/kg K; T in K (IPTS-68)."""
    s = v("s_seawater") if s is None else s
    T = t_c + K0
    A = 5.328 - 9.76e-2 * s + 4.04e-4 * s * s
    B = -6.913e-3 + 7.351e-4 * s - 3.15e-6 * s * s
    C = 9.6e-6 - 1.927e-6 * s + 8.23e-9 * s * s
    D = 2.5e-9 + 1.666e-9 * s - 7.125e-12 * s * s
    return 1e3 * (A + B * T + C * T * T + D * T ** 3)


P("cp_seawater", seawater_cp(0.5 * (v("med_tbt") + v("med_feed"))), "J kg^-1 K^-1",
  "DERIVED", "seawater cp at the mean MED liquid temperature",
  deps=("eq_seawater_cp", "s_seawater", "med_tbt", "med_feed"))
