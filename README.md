# Reimagining the Data Center — Validation Archive

### Computational validation for *Reimagining the Data Center: AI Computation as the First Stage of an Integrated Energy System*

**Author:** Dr. David Swanagon
**Affiliation:** ORCID: 0009-0005-9506-4609, Dallas, Texas, United States

---

## 📄 Read the paper

The manuscript is **not** hosted in this repository. It is published open access:

| | |
| --- | --- |
| **Zenodo** | |
| **ResearchGate** | |

This repository contains only the experiments behind the paper's protocols and their recorded output, so that any claim in the paper can be re-run and checked independently.

---

## 1. What the paper claims

The paper introduces an inverse design for AI computation. Today's data centers run their chips as cool as possible and discard the heat. The design runs the chips as hot as the material allows, generates that heat with geometric operations whose results form a public ground truth for data, and uses the heat as a secondary energy source at an energy site such as a refinery. One input, electricity, yields two products: insight the whole industry builds on, and energy the site would otherwise buy.

**Every joule becomes heat, so two properties decide the worth of a facility.** The First Law returns all electricity drawn by a computer as heat. What a facility is worth to the energy system around it is therefore set by the temperature at which that heat leaves and by the value of the computation that produced it. The design maximises both.

**The geometric workload is computed once, for everyone.** The workload is the spectrum of the covariant Laplace–Beltrami operator on public geometry corpora (1,261,300 geometries). It holds the chips at rated power, and its results are published as a master geometric dataset on which each developer fits its own proprietary weights.

Four consequences are measured here rather than asserted:

**Redundant computation is eliminated.** The deepest tier of the dataset costs US$360 million in electricity computed once at the energy site, against US$461 million for each developer computing it separately in a hyperscale facility. Ten developers sharing one computation save 92%; fifty save 98%.

**The dataset is a ground truth.** Its certifiable precision improves at second order, from 10.3% to 0.17%. Weights fitted on the shared basis give 2.4–11 times lower error than the same number of weights on raw coordinates, in 24 of 24 comparisons, and descent in the geometry's own metric does not slow as resolution rises: 228 times fewer iterations than gradient descent and 18 times fewer than conjugate gradients at the finest mesh.

**Gross consumption becomes net output and secondary energy.** Silicon-carbide chips carry full power to a coolant at 300–465 °C. Of the heat, 24.0–35.0% returns as electricity (21.3% with every ranged input at its least favourable end together), the remainder serves every steam band and solvent regeneration, and desalination yields up to 23,841 m³ of water a day per 100 MW. Silicon cannot follow: its junction limit holds recovery to 3.0%.

**The refinery runs more efficiently.** Of US refinery process heat, 1,380 TBtu a year (62%) lies within the design's reach. Supplying it from computation frees at least 41% of refinery fuel and avoids at least 73 Mt of CO₂; it is the heat of 46 GW of computation. For the same computation and process heat, the integrated system purchases 52–54% less energy than today's separate systems and avoids 1.6–1.9 Mt of CO₂ per gigawatt-year.

## 2. The originating proposal

The design was first stated by the author as a proposal for a hot "furnace tier" of AI computation. Its figures are held in the registry as CLAIM entries: they are tested, and never used as inputs. Protocol E3 reproduces each of them.

| Proposal | Reproduced (E3) |
| --- | --- |
| Carnot ceiling ~15% at 80 °C, ~48% at 300 °C | 15.6%, 48.0% |
| ~5% recovered at ~80 °C | 5.4% |
| ORC ~20% at ~300 °C | 23.0% |
| ~4× the recovered energy | 4.3× |
| Tower ~1% of rejected heat | 1% at a 596 m tower |
| Multi-effect distillation at 60–70 °C | Top brine temperature 66–72 °C |

The integrated chain is also the basis of a companion inquiry on Mars, where heat for regolith outgassing and gas separation is a primary requirement.

## 3. Contents

```
registry.py           every input to every experiment, defined once with its kind,
                      basis and citation key
conventions.py        shared helpers and the verdict harness
Scripts/              the nine experiment programs, E1–E9
dependency_graph.py   protocol D: verifies the dependency chain itself
make_paper_numbers.py reads every figure the paper quotes from the logs
run_all.sh            runs every protocol in order
sn-bibliography.bib   every citation key the registry uses
dataset_slice/        the prototype master-dataset slice, with its SHA-256 manifest
Experiment Logs/      recorded output of each protocol, as published
requirements.txt
LICENSE
```

Every number that enters a result is defined once in `registry.py` and is one of five kinds: **LAW** (a physical law, exact constant or definition, cited), **BENCH** (a published value, cited with the location of the value in its source), **DERIVED** (calculated from named registry entries and nothing else), **DESIGN** (a value chosen by this study; where it carries a range, the range is exercised) and **CLAIM** (a figure of the originating proposal, tested and never used as an input). The registry holds 155 entries joined by 43 derivation edges. No experiment holds an input of its own.

Four rules govern how a value enters a result. Where a source gives a range, the nominal value is the end least favourable to the design, and the full range is exercised. The work credited to an organic Rankine cycle is the lesser of its state-point model and the 24% demonstrated in practice, and any excess is booked as loss so that energy still closes. Each chip class is assigned the most efficient cycle that passes every physical-law check. The hottest coolant each material can use is derived from its junction limit: 65 °C for silicon, 465 °C for silicon carbide.

`dataset_slice/` holds twelve curved surfaces at 2,562 vertices, with full spectra, 200 stored modes and heat-kernel signatures. Every entry carries a SHA-256 checksum under `manifest.json`, verified before any check runs; an altered byte, or data stored under the wrong surface, is rejected on the checksum alone.

`Experiment Logs/paper_figures.tex` is the block of generated figures exactly as typeset in the paper. `make_paper_numbers.py` reads each of those figures from the logs and fails if any differs, so the prose and the measurements cannot drift.

## 4. Running the experiments

Python 3.13 with NumPy, SciPy and CoolProp (tested with NumPy 2.5, SciPy 1.18 and CoolProp 8.0).

```bash
pip install -r requirements.txt
./run_all.sh
```

or one protocol at a time:

```bash
python3 -I Scripts/E1_geometric_heat.py
python3 -I Scripts/E2_insight_baseline.py
python3 -I Scripts/E3_cascade.py
python3 -I Scripts/E4_leakage_crossover.py
python3 -I Scripts/E5_tower.py
python3 -I Scripts/E6_best_uses.py
python3 -I Scripts/E7_uncertainty.py
python3 -I Scripts/E8_incremental_production.py
python3 -I Scripts/E9_dataset_value.py
python3 -I dependency_graph.py
python3 -I make_paper_numbers.py
```

Each program reads every input from `registry.py`, resolves its own paths, prints its structural output followed by its verdicts, and exits non-zero if any check fails. Every verdict is deterministic: the sampled protocols draw from a seeded generator whose seed is a registry entry, and no check uses a timing. Output should match `Experiment Logs/` apart from the elapsed-time lines, which are figures of the machine and carry no verdict. E7, a 300-sample Monte Carlo with the power cycle re-selected in each sample, takes about fifteen minutes; the rest take seconds to a few minutes.

## 5. What each experiment establishes

| Program | Protocol | Establishes |
| --- | --- | --- |
| `E1_geometric_heat.py` | E1 | **Geometric heat.** The cotangent Laplace–Beltrami spectrum converges to *l*(*l*+1) on the unit sphere; the dense kernels are compute-bound against the reference accelerator's roofline; the junction fixed point with leakage scaled by the intrinsic carrier density, and the heat each chip carries before its limit; corpus energy at five registered depths. |
| `E2_insight_baseline.py` | E2 | **The master dataset slice.** The prototype slice under its SHA-256 manifest; three downstream models built from one dataset; a verifier that accepts every correct answer and rejects every departure of 0.5% or more from a stored value. |
| `E3_cascade.py` | E3 | **The thermodynamic cascade.** State-point ORC and supercritical CO₂ cycles on reference equations of state, under the practice cap; multi-effect distillation effect by effect; the tower; energy closure, the Carnot bound, entropy generation and recuperator pinch in every scenario; the figures of the originating proposal reproduced. |
| `E4_leakage_crossover.py` | E4 | **The leakage crossover.** Computation per unit of grid electricity across coolant temperature for silicon and silicon carbide; the 16 corners of the ranged leakage share, thermal resistance, baseline junction and junction limit; the SiC logic efficiency at which the design equals the best hyperscale facility. |
| `E5_tower.py` | E5 | **The tower.** Ideal and realised tower efficiency; the Carnot bound to the air at the column top at every height; humid-air enthalpy and virtual temperature at the ends of the humidity range. |
| `E6_best_uses.py` | E6 | **The best uses of the heat.** The reach of each process band from the coolant return; the value per MWh of electricity, process heat, cascades and water; break-even electricity prices at US and European gas prices; hydrogen break-even. |
| `E7_uncertainty.py` | E7 | **Uncertainty and lower bounds.** The deterministic lower bound with every ranged input at its least favourable end, after monotonicity is confirmed; 300 samples over the same ranges, none below the bound; exact linear sensitivities; the overhead break-even at a PUE equivalent of 1.30. |
| `E8_incremental_production.py` | E8 | **The integrated energy facility.** Value added around each MWh of heat in the oil-to-products chain; the reach of US process heat; the refinery fuel and heat ledger; side-by-side system ledgers at equal computation and heat. |
| `E9_dataset_value.py` | E9 | **The value of the geometric dataset.** The corpus ledger computed once and separately; equal-weight fitting on three surfaces and two geometric fields; flat and covariant solves at four resolutions and three stored shares; certified precision on the sphere; break-even downstream uses. |
| `dependency_graph.py` | D | **The dependency chain.** The registry closed and acyclic; every citation resolved; every ranged benchmark at its least favourable end; every entry consumed; no experiment re-typing a registry value; values computed by two experiments in agreement; every range exercised at both ends. |

## 6. Current verdicts

```
APPENDIX E1             52 checks pass
APPENDIX E2             75 checks pass
APPENDIX E3            104 checks pass
APPENDIX E4             43 checks pass
APPENDIX E5             21 checks pass
APPENDIX E6             38 checks pass
APPENDIX E7             27 checks pass
APPENDIX E8             34 checks pass
APPENDIX E9             31 checks pass
DEPENDENCY CHAIN        29 checks pass
                       454 total
```

Each of the nine experiments also breaks its own physics and its own accounting, one fault at a time, and passes only if every break is caught: 41 faults are injected, among them an expander more efficient than Carnot, rejected heat dropped from the ledger, leakage switched off, one byte altered in a dataset entry, and heat credited twice. Every fault is caught. Full output for each protocol is in `Experiment Logs/`.

## 7. Falsifiability

The paper states its failure modes explicitly, each targeting a named link of the chain and each tested by a named protocol here. Failure of any protocol is a direct refutation of that link, and this archive exists so that the attempt costs one command.

One standing criterion of the design belongs here, because this is where it would fail first. Every joule the chips draw leaves as heat, so the chain cannot deliver less heat than the computation consumes, and it cannot deliver more energy than it draws. Should any stage be shown to break either bound, the energy ledger is wrong and every link after it with it; each protocol therefore closes that ledger before it reports anything else.

## 8. Citation

If you use this work, please cite the paper rather than the repository.

## 9. License

See `LICENSE`.
