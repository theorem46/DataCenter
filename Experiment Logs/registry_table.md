| id | value | unit | kind | basis | source | depends on | range | read by |
|---|---|---|---|---|---|---|---|---|
| g_n | 9.80665 | m s^-2 | LAW | standard acceleration of gravity, exact | BIPM2019 |  |  | conventions.py |
| zero_C_in_K | 273.15 | K | LAW | 0 degC in kelvin, exact | BIPM2019 |  |  | conventions.py, registry |
| k_B_eV | 8.61733e-05 | eV K^-1 | LAW | Boltzmann constant, CODATA 2018 | Tiesinga2021 |  |  | E1_geometric_heat.py |
| J_per_Btu | 1055.06 | J | LAW | International Table British thermal unit | ThompsonTaylor2008 |  |  | E8_incremental_production.py, registry, registry:mwh_per_mmbtu |
| kg_per_lb | 0.453592 | kg | LAW | international avoirdupois pound, exact | ThompsonTaylor2008 |  |  | E8_incremental_production.py |
| hours_per_year | 8760 | h | LAW | 365 x 24, definition of the annual basis |  |  |  | conventions.py |
| p_atm | 101325 | Pa | LAW | standard atmosphere, exact | BIPM2019 |  |  | E5_tower.py, registry, registry:cp_air |
| eq_first_law | (relation) | - | LAW | energy conservation: electrical power into computation leaves as heat (computation stores negligible energy) | Landauer1961 |  |  |  |
| eq_carnot | (relation) | - | LAW | eta <= 1 - Tc/Th for any heat engine | Callen1985 |  |  |  |
| eq_cascade | (relation) | - | LAW | eta_total = eta1 + (1-eta1) eta2, from the first law | Callen1985 |  |  |  |
| eq_chimney | (relation) | - | LAW | ideal chimney efficiency g H / (cp T0), from hydrostatics and the ideal-gas law (Eq. 14) | ZhouXu2016 |  |  |  |
| eq_intrinsic | (relation) | - | LAW | n_i proportional to T^1.5 exp(-Eg / 2kT) | SzeNg2007 |  |  |  |
| eq_virtual_T | (relation) | - | LAW | virtual temperature Tv = T (1 + w/0.622)/(1 + w) | WallaceHobbs2006 |  |  |  |
| eq_cotan | (relation) | - | LAW | cotangent Laplace-Beltrami with lumped mass | PinkallPolthier1993 |  |  |  |
| eq_roofline | (relation) | - | LAW | attainable FLOP/s = min(peak, intensity x bandwidth) | Williams2009 |  |  | registry:ridge |
| eq_eig_flops | 9 | n^3 | LAW | symmetric QR, all eigenpairs ~ 9 n^3 flops | GolubVanLoan2013 |  |  | E1_geometric_heat.py, E9_dataset_value.py |
| eq_lanczos_flops | 2 | n m^2 | LAW | Lanczos with full reorthogonalisation: ~2 n m^2 flops for m steps (plus m sparse products) | GolubVanLoan2013 |  |  | E1_geometric_heat.py |
| coolprop | (relation) | - | LAW | reference equations of state via CoolProp | Bell2014 |  |  | registry:cp_air, registry:eps_mw, registry:steam_sat_bar |
| eq_seawater_cp | (relation) | - | LAW | seawater cp correlation (Jamieson et al.), 0-180 degC, 0-180 g/kg, +-0.28% | Sharqawy2010 |  |  | registry:cp_seawater |
| h100_fp64_tc | 6.7e+13 | FLOP s^-1 | BENCH | H100 SXM FP64 Tensor Core peak | NVIDIA2024H100 |  |  | E1_geometric_heat.py, registry, registry:flop_per_joule, registry:ridge |
| h100_bw | 3.35e+12 | B s^-1 | BENCH | H100 SXM HBM3 bandwidth | NVIDIA2024H100 |  |  | E1_geometric_heat.py, registry, registry:ridge |
| h100_tdp | 700 | W | BENCH | H100 SXM maximum thermal design power | NVIDIA2024H100 |  |  | E1_geometric_heat.py, E4_leakage_crossover.py, E6_best_uses.py, registry, registry:flop_per_joule, registry:t_coolant_si, registry:t_coolant_sic_max |
| h100_die_mm2 | 814 | mm^2 | BENCH | GH100 die size | NVIDIA2022Hopper |  |  | registry, registry:h100_die_cm2 |
| eagle_rmax | 5.612e+17 | FLOP s^-1 | BENCH | Eagle (H100) HPL Rmax, June 2024 | TOP5002024 |  |  | registry, registry:sustained |
| eagle_rpeak | 8.4684e+17 | FLOP s^-1 | BENCH | Eagle (H100) Rpeak, June 2024 | TOP5002024 |  |  | registry, registry:sustained |
| pue_hyperscale | 1.09 | - | BENCH | Google fleet annual PUE 2025 (best practice) | Google2026PUE |  |  | conventions.py, registry, registry:furnace_overhead |
| pue_avg | 1.4 | - | BENCH | US average PUE 2023 (LBNL); the global 2024 survey average 1.56 is less favourable to the baseline | Shehabi2024 |  |  | conventions.py |
| pue_avg_global | 1.56 | - | BENCH | industry average PUE, 2024 survey (p. 7) | Donnellan2024 |  |  | E7_uncertainty.py |
| wue_avg | 0.36 | L kWh^-1 | BENCH | US average site WUE through 2023 | Shehabi2024 |  |  | conventions.py |
| wue_hyperscale | 0.1 | L kWh^-1 | BENCH | hyperscale WUE 0.1-0.3; nominal is the end least favourable to the furnace | Shehabi2024 |  | 0.1-0.3 | E7_uncertainty.py, conventions.py |
| eg_si | 1.12 | eV | BENCH | silicon bandgap, 300 K | SzeNg2007 |  |  | E1_geometric_heat.py, E4_leakage_crossover.py |
| eg_sic | 3.26 | eV | BENCH | 4H-SiC bandgap, room temperature | KimotoCooper2014 |  |  | E1_geometric_heat.py, E4_leakage_crossover.py |
| tj_max_si | 100 | degC | BENCH | silicon logic Tj,max 100-110 degC; both ends exercised wherever it enters (E4.2) | IntelTjmax |  | 100-110 | E1_geometric_heat.py, E4_leakage_crossover.py, registry, registry:t_coolant_si |
| tj_max_sic | 500 | degC | BENCH | 4H-SiC JFET ICs operated over one year at 500 degC in air (about 10,000 h, tests still running) | Neudeck2018 |  |  | E1_geometric_heat.py, E4_leakage_crossover.py, E6_best_uses.py, registry, registry:t_coolant_sic_max |
| rth_area_demo | 0.09 | K cm^2 W^-1 | BENCH | microchannel heat sink, 790 W/cm^2 at 71 K rise | TuckermanPease1981 |  |  | registry, registry:rth_best_demo |
| eta_exp_orc | 0.6 | - | BENCH | ORC expander overall isentropic efficiency: maximum around 70% with generator losses (Sec. 10); screw expanders not much above 60% (Sec. 6.2.2); nominal is the lower end | Quoilin2013 |  | 0.6-0.7 | E3_cascade.py, E7_uncertainty.py |
| eta_pump_orc | 0.25 | - | BENCH | ORC feed pump overall efficiency: highest measured value 25% (Sec. 8.2); centrifugal pumps claimed above 60% but unconfirmed; nominal is the measured end | Quoilin2013 |  | 0.25-0.6 | E3_cascade.py |
| eta_orc_ceiling | 0.24 | - | BENCH | the efficiency of current high-temperature ORCs does not exceed 24% (Sec. 4) | Quoilin2013 |  |  | E3_cascade.py |
| eta_turb_sco2 | 0.9 | - | BENCH | sCO2 turbine efficiency 90% (Sec. 2.2, p. 9) | Dostal2004 |  |  | E3_cascade.py |
| eta_comp_sco2 | 0.89 | - | BENCH | sCO2 compressor efficiency 89% (Sec. 2.2, p. 11) | Dostal2004 |  |  | E3_cascade.py |
| t_comp_in_sco2_ref | 32 | degC | BENCH | sCO2 compressor inlet 32 degC (Sec. 2.2, p. 11); comparison only, this study derives its own from the heat sink | Dostal2004 |  |  | E3_cascade.py |
| p_high_sco2 | 2e+07 | Pa | BENCH | sCO2 cycle high pressure | Dostal2004 |  |  | E3_cascade.py |
| eta_sco2_recomp_550 | 0.453 | - | BENCH | recompression sCO2 at 550 degC, 20 MPa (upper bound for a simple cycle at lower temperature) | Dostal2004 |  |  | E3_cascade.py |
| eta_tower_turb | 0.77 | - | BENCH | updraft-tower turbine efficiency 77-80% (Table 4); nominal is the lower end | ZhouXu2016 |  | 0.77-0.8 | E3_cascade.py, E7_uncertainty.py |
| tower_pressure_share | 0.666667 | - | BENCH | optimal turbine share of the available pressure difference (Table 7) | ZhouXu2016 |  |  | E3_cascade.py |
| med_tbt | 66 | degC | BENCH | MED top brine temperature 66-72 degC; nominal is the lower end (fewer effects) | AlKaraghouli2011 |  | 66-72 | E7_uncertainty.py, registry, registry:cp_seawater, registry:med_steam |
| med_kwh_m3 | 2.5 | kWh m^-3 | BENCH | MED electrical energy 1.5-2.5 kWh/m3; nominal is the upper end | AlKaraghouli2011 |  | 1.5-2.5 | E3_cascade.py, E7_uncertainty.py |
| med_gor_lo | 8 | - | BENCH | MED gain output ratio 8-12: lower end | AlKaraghouli2011 |  |  | E3_cascade.py |
| med_gor_hi | 12 | - | BENCH | MED gain output ratio 8-12: upper end | AlKaraghouli2011 |  |  | E3_cascade.py |
| s_seawater | 35 | g kg^-1 | BENCH | reference seawater salinity | Sharqawy2010 |  |  | E3_cascade.py, registry, registry:cp_seawater |
| water_price | 0.5 | USD m^-3 | BENCH | large-plant desalinated water cost 0.5-1.0 USD/m3; nominal is the lower end | Ghaffour2013 |  | 0.5-1 | E3_cascade.py, E6_best_uses.py |
| elec_price | 85.1 | USD MWh^-1 | BENCH | US average industrial electricity price, 2025 | EIA2026EPM |  |  | E6_best_uses.py, conventions.py |
| henry_hub | 3.48 | USD MMBtu^-1 | BENCH | Henry Hub 2026 average | EIA2026STEO |  |  | registry, registry:gas_us |
| ttf_2025 | 11.96 | USD MMBtu^-1 | BENCH | natural gas, Europe (Netherlands TTF), 2025 average; range is the lowest and highest monthly values printed for October 2025 to April 2026; both ends exercised (E6.3) | WorldBank2026 |  | 9.48-17.91 | E6_best_uses.py, registry, registry:gas_eu |
| co2_gas_kg_mmbtu | 53.06 | kg MMBtu^-1 | BENCH | natural gas CO2 factor | EPA2025 |  |  | E8_incremental_production.py, registry, registry:co2_t_per_mwh_gas |
| eta_boiler | 0.857 | - | BENCH | natural-gas boiler combustion efficiency with economiser | DOE2012Steam |  |  | E6_best_uses.py, E8_incremental_production.py |
| kwh_per_kg_h2 | 50 | kWh kg^-1 | BENCH | electrolyser system 50-83 kWh/kg; nominal is the end most favourable to hydrogen, the competing use | IRENA2020 |  | 50-83 | E6_best_uses.py |
| t_pyrolysis | 500 | degC | BENCH | pyrolysis producing liquid oils and waxes at 500-650 degC; nominal is the lower end (most reachable) | AlSalem2017 |  | 500-650 | E6_best_uses.py |
| t_amine_regen | 120 | degC | BENCH | amine stripping at 100-120 degC; upper end | Rochelle2009 |  |  | E6_best_uses.py, E8_incremental_production.py |
| mecs_va_324110 | 28.6 | kBtu USD^-1 | BENCH | petroleum refineries (NAICS 324110), Table 6.1 | EIA2021MECS |  |  | E8_incremental_production.py |
| mecs_va_325110 | 23.1 | kBtu USD^-1 | BENCH | petrochemicals (NAICS 325110), Table 6.1 | EIA2021MECS |  |  | E8_incremental_production.py |
| mecs_va_325199 | 19.8 | kBtu USD^-1 | BENCH | other basic organic chemicals (NAICS 325199), Table 6.1 | EIA2021MECS |  |  | E8_incremental_production.py |
| mecs_va_325211 | 20.5 | kBtu USD^-1 | BENCH | plastics materials and resins (NAICS 325211), Table 6.1 | EIA2021MECS |  |  | E8_incremental_production.py |
| mecs_va_mfg | 5.6 | kBtu USD^-1 | BENCH | all US manufacturing, Table 6.1 | EIA2021MECS |  |  | E8_incremental_production.py |
| mecs_fuel_324110 | 3375 | TBtu | BENCH | petroleum refineries, total fuel, Table 3.2 | EIA2021MECS |  |  | E8_incremental_production.py |
| mecs_other_324110 | 2192 | TBtu | BENCH | petroleum refineries, 'Other' fuels (mainly byproduct still gas), Table 3.2 | EIA2021MECS |  |  | E8_incremental_production.py |
| mecs_fuel_325110 | 569 | TBtu | BENCH | petrochemicals, total fuel, Table 3.2 | EIA2021MECS |  |  | E8_incremental_production.py |
| mecs_fuel_325199 | 742 | TBtu | BENCH | other basic organic chemicals, total fuel, Table 3.2 | EIA2021MECS |  |  | E8_incremental_production.py |
| mecs_fuel_325211 | 668 | TBtu | BENCH | plastics materials and resins, total fuel, Table 3.2 | EIA2021MECS |  |  | E8_incremental_production.py |
| iph_us | 11000 | TBtu | BENCH | US industrial process heat demand (Sec. 1.7, Table 2) | McMillan2021 |  |  | E8_incremental_production.py |
| iph_us_below300 | 8010 | TBtu | BENCH | US process heat below 300 degC, about 73% (Sec. 2.1) | McMillan2021 |  |  | E8_incremental_production.py |
| iph_refining | 2210 | TBtu | BENCH | petroleum refineries (324110) process heat (Table 3) | McMillan2021 |  |  | E8_incremental_production.py |
| iph_refining_100_300 | 1380 | TBtu | BENCH | petroleum refineries process heat at 100-300 degC, about 63% (Table 3) | McMillan2021 |  |  | E8_incremental_production.py |
| iph_share_stated | 0.73 | - | BENCH | share below 300 degC as stated (Sec. 2.1) | McMillan2021 |  |  | E8_incremental_production.py |
| iph_refining_share_stated | 0.63 | - | BENCH | refinery share at 100-300 degC as stated (text, p. 14) | McMillan2021 |  |  | E8_incremental_production.py |
| t_iph_band_lo | 100 | degC | BENCH | lower edge of the reported 100-300 degC band | McMillan2021 |  |  | E8_incremental_production.py |
| t_iph_band | 300 | degC | BENCH | upper edge of the reported band | McMillan2021 |  |  | E8_incremental_production.py |
| cracker_pyrolysis_share | 0.65 | - | BENCH | pyrolysis section share of naphtha cracker process energy (abstract) | Ren2006 |  |  | E8_incremental_production.py |
| t_cracker_lo | 750 | degC | BENCH | steam-cracking temperature 750-900 degC; lower end (Sec. 2.1) | Ren2008 |  |  | E8_incremental_production.py |
| bw_ethylene | 7071 | Btu lb^-1 | BENCH | ethylene, current typical onsite energy (Table 4-5) | Brueske2015 |  |  | E8_incremental_production.py |
| bw_hdpe | 1037 | Btu lb^-1 | BENCH | HDPE (Table 4-5) | Brueske2015 |  |  | E8_incremental_production.py |
| bw_lldpe | 871 | Btu lb^-1 | BENCH | LLDPE (Table 4-5) | Brueske2015 |  |  | E8_incremental_production.py |
| bw_ldpe | 1143 | Btu lb^-1 | BENCH | LDPE (Table 4-5) | Brueske2015 |  |  | E8_incremental_production.py |
| bw_pp | 616 | Btu lb^-1 | BENCH | polypropylene (Table 4-5) | Brueske2015 |  |  | E8_incremental_production.py |
| bw_ethylene_mlb | 52864 | million lb | BENCH | US ethylene production 2010 (Table 3-1) | Brueske2015 |  |  | E8_incremental_production.py |
| bw_ethylene_tbtu | 374 | TBtu | BENCH | ethylene onsite current typical energy (Table 4-5) | Brueske2015 |  |  | E8_incremental_production.py |
| n_abc | 1000000 | models | BENCH | ABC CAD dataset | Koch2019 |  |  | E1_geometric_heat.py, registry, registry:n_corpus |
| n_shapenet | 51300 | models | BENCH | ShapeNetCore | Chang2015 |  |  | E1_geometric_heat.py, registry, registry:n_corpus |
| n_thingi | 10000 | models | BENCH | Thingi10K | ZhouJacobson2016 |  |  | E1_geometric_heat.py, registry, registry:n_corpus |
| n_pdb | 200000 | structures | BENCH | PDB, approximately 200,000 experimental structures | Burley2023 |  |  | E1_geometric_heat.py, registry, registry:n_corpus |
| t_ambient | 25 | degC | DESIGN | standard ambient temperature 298.15 K | IUPACGoldBook |  |  | E1_geometric_heat.py, conventions.py, registry, registry:cp_air, registry:t_comp_in_sco2 |
| t_seawater | 25 | degC | DESIGN | seawater intake temperature |  |  |  | conventions.py |
| it_power_mw | 100 | MW | DESIGN | normalisation scale; all results are linear in it |  |  |  | conventions.py |
| loop_drop | 10 | K | DESIGN | coolant loop temperature drop |  |  | 5-15 | E3_cascade.py, E6_best_uses.py, E7_uncertainty.py, E8_incremental_production.py |
| pinch | 10 | K | DESIGN | minimum approach, source to working fluid | LinnhoffHindmarsh1983 |  | 5-15 | E3_cascade.py, E7_uncertainty.py |
| sink_approach | 10 | K | DESIGN | condensing temperature above ambient | LinnhoffHindmarsh1983 |  | 8-20 | E3_cascade.py, E7_uncertainty.py, registry, registry:t_comp_in_sco2 |
| recup_min_pinch | 5 | K | DESIGN | recuperator minimum temperature difference |  |  | 5-15 | E3_cascade.py, E7_uncertainty.py |
| recup_eff | 1 | - | DESIGN | recuperator duty limited by its pinch alone |  |  |  | E3_cascade.py |
| subcrit_margin | 2 | K | DESIGN | subcritical ORC evaporates at least this far below the working fluid's critical temperature |  |  | 2-10 | E3_cascade.py, E7_uncertainty.py |
| p_low_sco2 | 7.7e+06 | Pa | DESIGN | sCO2 low pressure, just above critical 7.38 MPa |  |  |  | E3_cascade.py |
| med_steam_margin | 5 | K | DESIGN | heating steam above top brine temperature |  |  |  | E3_cascade.py, E7_uncertainty.py, registry, registry:med_steam |
| med_steam_approach | 3 | K | DESIGN | heat source above heating steam |  |  |  | E3_cascade.py |
| med_last | 40 | degC | DESIGN | last effect temperature |  |  |  | E3_cascade.py, E5_tower.py |
| med_step | 3 | K | DESIGN | temperature drop per effect |  |  |  | E3_cascade.py |
| med_feed | 35 | degC | DESIGN | feed temperature after final-condenser preheat |  |  |  | E3_cascade.py, registry, registry:cp_seawater |
| med_brine_salinity | 60 | g kg^-1 | DESIGN | brine reject salinity |  |  | 55-70 | E3_cascade.py, E7_uncertainty.py |
| med_loss | 0.01 | - | DESIGN | heat lost to ambient per effect |  |  | 0-0.03 | E3_cascade.py, E7_uncertainty.py |
| tower_H | 200 | m | DESIGN | tower height |  |  | 100-300 | E3_cascade.py, E7_uncertainty.py |
| rth | 0.05 | K W^-1 | DESIGN | junction-to-coolant resistance; above the best demonstrated value, hence conservative |  |  | 0.0111-0.05 | E1_geometric_heat.py, E4_leakage_crossover.py, E6_best_uses.py, registry, registry:t_coolant_si, registry:t_coolant_sic_max |
| leak_frac | 0.15 | - | DESIGN | silicon leakage share of power at the baseline junction; leakage approaching dynamic power is reported (kim2003) | Kim2003 |  | 0.05-0.5 | E1_geometric_heat.py, E4_leakage_crossover.py, E7_uncertainty.py |
| t_base_junction | 85 | degC | DESIGN | baseline silicon junction temperature |  |  | 65-85 | E1_geometric_heat.py, E4_leakage_crossover.py |
| t_sic_design | 300 | degC | DESIGN | SiC design-point coolant temperature: the hot-chip temperature of the originating proposal |  |  |  | E1_geometric_heat.py, E3_cascade.py, E4_leakage_crossover.py, E6_best_uses.py, E8_incremental_production.py |
| approach_process | 10 | K | DESIGN | supply above process requirement | LinnhoffHindmarsh1983 |  |  | E6_best_uses.py, E8_incremental_production.py |
| steam_bands | (150.0, 200.0, 250.0) | degC | DESIGN | steam delivery temperatures; saturation pressures derived |  |  |  | E6_best_uses.py, E8_incremental_production.py, registry, registry:steam_sat_bar |
| slice_level | 4 | - | DESIGN | icosphere subdivision level of the dataset slice (2,562 vertices) |  |  |  | E2_insight_baseline.py |
| slice_k | 200 | modes | DESIGN | eigenpairs stored per surface in the slice |  |  |  | E2_insight_baseline.py |
| spectral_fraction | 0.05 | - | DESIGN | share of the spectrum a dataset entry stores for downstream preconditioning (E9.3) |  |  | 0.02-0.1 | E9_dataset_value.py |
| raw_feature_degree | 6 | - | DESIGN | degree of the raw-coordinate monomial features in E9.2; the dataset basis is given the same number of features |  |  |  | E9_dataset_value.py |
| solve_tol | 1e-06 | - | DESIGN | relative energy-norm tolerance of every iterative solve (E2e, E9.3) |  |  |  | E2_insight_baseline.py, E9_dataset_value.py |
| tier_n_small | 100000 | vertices | DESIGN | mesh resolution of tiers T1 and T3 |  |  |  | E1_geometric_heat.py |
| tier_n_large | 1e+06 | vertices | DESIGN | mesh resolution of tiers T2, T4 and T5 |  |  |  | E1_geometric_heat.py |
| tier_k_small | 1000 | modes | DESIGN | eigenpairs computed at tier T1 |  |  |  | E1_geometric_heat.py |
| tier_k_large | 5000 | modes | DESIGN | eigenpairs computed at tier T2 |  |  |  | E1_geometric_heat.py |
| depth_families | 100 | metrics | DESIGN | families of metrics per geometry (T5) |  |  |  | E1_geometric_heat.py |
| rh_ambient | 0.5 | - | DESIGN | ambient relative humidity |  |  | 0.3-0.8 | E5_tower.py |
| mc_samples | 300 | - | DESIGN | Monte Carlo sample count (E7) |  |  |  | E7_uncertainty.py |
| seed | 46 | - | DESIGN | random seed for every stochastic experiment |  |  |  | E1_geometric_heat.py, E7_uncertainty.py, E9_dataset_value.py |
| post_t_low | 80 | degC | CLAIM | originating post: chip coolant today (~80 degC) |  |  |  | E1_geometric_heat.py, E3_cascade.py |
| post_t_high | 300 | degC | CLAIM | originating post: hot-chip coolant (~300 degC) |  |  |  | E3_cascade.py |
| post_carnot_low | 0.15 | - | CLAIM | originating post: Carnot ceiling ~15% at 80 degC |  |  |  | E3_cascade.py |
| post_carnot_high | 0.48 | - | CLAIM | originating post: Carnot ceiling ~48% at 300 degC |  |  |  | E3_cascade.py |
| post_recovery_low | 0.05 | - | CLAIM | originating post: ~5% recovered at ~80 degC |  |  |  | E3_cascade.py |
| post_orc_high | 0.2 | - | CLAIM | originating post: ORC ~20% at ~300 degC |  |  |  | E3_cascade.py |
| post_tower | 0.01 | - | CLAIM | originating post: tower ~1% of rejected heat |  |  |  | E3_cascade.py |
| post_ratio | 4 | - | CLAIM | originating post: ~4x the recovered energy |  |  |  | E3_cascade.py |
| post_tol | 0.01 | - | CLAIM | the post states percentages to the nearest point ('~'); a claim is reproduced within one point |  |  |  | E3_cascade.py |
| cp_air | 1006.31 | J kg^-1 K^-1 | DERIVED | dry air cp at ambient |  | coolprop, t_ambient, p_atm |  | conventions.py |
| t_comp_in_sco2 | 35 | degC | DERIVED | sCO2 compressor inlet: the same heat sink as the ORC condenser |  | t_ambient, sink_approach |  | E3_cascade.py |
| eps_mw | 0.621957 | - | DERIVED | ratio of molar masses, water to dry air |  | coolprop |  | E5_tower.py |
| mwh_per_mmbtu | 0.293071 | MWh MMBtu^-1 | DERIVED | 1 MMBtu in MWh |  | J_per_Btu |  | E6_best_uses.py, E8_incremental_production.py, registry, registry:co2_t_per_mwh_gas, registry:gas_eu, registry:gas_us |
| sustained | 0.662699 | - | DERIVED | sustained fraction of peak on dense linear algebra (HPL) |  | eagle_rmax, eagle_rpeak |  | E1_geometric_heat.py, registry, registry:flop_per_joule |
| flop_per_joule | 6.34298e+10 | FLOP J^-1 | DERIVED | sustained dense FLOP per joule |  | sustained, h100_fp64_tc, h100_tdp |  | E1_geometric_heat.py, E2_insight_baseline.py, E9_dataset_value.py |
| ridge | 20 | FLOP B^-1 | DERIVED | roofline ridge point |  | h100_fp64_tc, h100_bw, eq_roofline |  | E1_geometric_heat.py |
| h100_die_cm2 | 8.14 | cm^2 | DERIVED | die area |  | h100_die_mm2 |  | E1_geometric_heat.py, registry, registry:rth_best_demo |
| rth_best_demo | 0.0110565 | K W^-1 | DERIVED | best demonstrated resistance over an H100-size die |  | rth_area_demo, h100_die_cm2 |  | E1_geometric_heat.py |
| t_coolant_si | 65 | degC | DERIVED | hottest silicon coolant at full power: Tj,max - Rth P |  | tj_max_si, rth, h100_tdp |  | E1_geometric_heat.py, E3_cascade.py, E4_leakage_crossover.py |
| t_coolant_sic_max | 465 | degC | DERIVED | hottest SiC coolant at full power: Tj,max - Rth P |  | tj_max_sic, rth, h100_tdp |  | E1_geometric_heat.py, E3_cascade.py, E4_leakage_crossover.py, E6_best_uses.py |
| furnace_overhead | 0.09 | - | DERIVED | furnace facility overhead charged at the best hyperscale level (conservative) |  | pue_hyperscale |  | E3_cascade.py, E4_leakage_crossover.py, E7_uncertainty.py, E8_incremental_production.py, E9_dataset_value.py |
| med_steam | 71 | degC | DERIVED | MED heating steam temperature |  | med_tbt, med_steam_margin |  | E3_cascade.py |
| co2_t_per_mwh_gas | 0.181048 | t MWh^-1 | DERIVED | natural gas CO2 per MWh |  | co2_gas_kg_mmbtu, mwh_per_mmbtu |  | E6_best_uses.py, E8_incremental_production.py |
| gas_us | 11.8743 | USD MWh^-1 | DERIVED | Henry Hub per MWh |  | henry_hub, mwh_per_mmbtu |  | E6_best_uses.py, E8_incremental_production.py |
| gas_eu | 40.8092 | USD MWh^-1 | DERIVED | TTF 2025 average per MWh |  | ttf_2025, mwh_per_mmbtu |  | E6_best_uses.py, E8_incremental_production.py |
| n_corpus | 1261300 | geometries | DERIVED | public geometry corpus |  | n_abc, n_shapenet, n_thingi, n_pdb |  | E1_geometric_heat.py, E9_dataset_value.py |
| steam_sat_bar | (4.761645379698103, 15.54927900466838, 39.761749306524734) | bar | DERIVED | saturation pressure of each steam band |  | steam_bands, coolprop |  | E6_best_uses.py |
| cp_seawater | 4010.17 | J kg^-1 K^-1 | DERIVED | seawater cp at the mean MED liquid temperature |  | eq_seawater_cp, s_seawater, med_tbt, med_feed |  | conventions.py |
