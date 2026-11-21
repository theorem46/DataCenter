# Dependency chain: closure, provenance and coherence

Every number that enters a result is defined once in `registry.py`, with its kind and its basis. `dependency_graph.py` verifies the chain mechanically (D1–D8) and exits 1 on any failure.

| Protocol | Checks |
|---|---|
| E1 geometric heat | 52/52 |
| E2 master dataset slice | 75/75 |
| E3 thermodynamic cascade | 104/104 |
| E4 leakage crossover | 43/43 |
| E5 tower | 21/21 |
| E6 best uses | 38/38 |
| E7 uncertainty and lower bounds | 27/27 |
| E8 integrated energy facility | 34/34 |
| E9 value of the geometric dataset | 31/31 |
| Dependency chain | 29/29 |
| Total | 454/454 |

| Kind | Count | Meaning |
|---|---|---|
| LAW | 19 | Physical law, exact constant or definition (cited) |
| BENCH | 71 | Published benchmark, with citation key and location of the value |
| DERIVED | 19 | Computed from named registry entries (43 derivation edges) |
| DESIGN | 37 | Design value of this study; 24 entries carry a range that is exercised |
| CLAIM | 9 | Figures stated in the originating proposal, tested and never used as inputs |

## Rules enforced

1. **Single source.** No experiment holds an input of its own. Module-level constants are allowed only as declared output grids, dataset-slice specimens or units.
2. **Least favourable benchmark.** Where a source gives a range, the nominal value is the end least favourable to the design, and the range is exercised at both ends.
3. **Practice caps the model.** Credited ORC work is the lesser of the state-point model and demonstrated practice (24%). Any excess is booked as loss, so energy still closes.
4. **Physics selects the cycle.** Each chip class gets the best cycle that passes energy closure, Carnot, entropy generation and recuperator pinch.
5. **Derived limits.** The hottest coolant for each material is its junction limit minus Rth·P: Si 65 °C, SiC 465 °C. The 300 °C design point is the originating proposal's.
6. **Machine independence.** No check uses a timing.

## Headline results by link of the chain

**Geometric workload and ground truth**
- Deepest tier: 1,261,300 geometries, one million vertices, 100 metric families; 4.97 TWh, or 5.7 years of a 100 MW facility. It publishes 1.0 PB of eigenvalue spectra, with eigenvectors for a stored share.
- Computed once: US$360M at the energy site against US$461M per developer in a hyperscale facility; 92% saved for ten developers, 98% for fifty.
- Ground truth: certified precision 10.3% → 0.17%, at second order.
- Weights fitted on the shared basis: 2.4–11× lower error on geometric fields (24 of 24).
- Covariant descent: iterations do not grow with resolution; 228× fewer than gradient descent and 18× fewer than conjugate gradients at the finest mesh.

**Hot chip**
- Silicon: coolant limit 65 °C, 33% leakage, 3.0% of heat returned as electricity, no process band served.
- SiC: full power to a 465 °C coolant with under 0.1% leakage.

**Heat as secondary energy**
- Electricity returned: 24.0% at 300 °C, 35.0% at 465 °C; lower bound 21.3% with every ranged input at its least favourable end.
- Process heat: up to 280 °C and 445 °C; every steam band and solvent regeneration served.
- Best use at US prices: power, then condenser heat to solvent regeneration, US$22.49 per MWh of chip heat.
- Power beats direct heat above US$58.4/MWh in the US; above US$201/MWh (159–301) at European gas prices, before carbon costs.
- Water: up to 23,841 m³/day per 100 MW.

**Integrated energy facility**
- 73% of US industrial process heat (a continuous 268 GW) lies below 300 °C.
- Refinery: 1,380 TBtu of process heat (62%) within reach; at least 41% of refinery fuel freed (65% of refinery fuel is the refineries' own byproduct gas); at least 73 Mt CO₂ avoided; the heat of 46 GW of computation.
- Value added around each MWh of heat in the oil-to-products chain: 10–15× the gas displaced.
- Whole system per GW-year: 52–54% less purchased energy; 1.6–1.9 Mt CO₂ from gas avoided; US$121–197M saved.

**Supporting view: against data centers**
- SiC equals the best hyperscale facility at 66% of silicon's switching efficiency at 300 °C and 58% at 465 °C.
- Recovered electricity per GW of chip power: US$179M a year against hyperscale (lower bound US$159M), US$410M against the US average, US$529M against the global average.
- Overhead break-even: PUE equivalent 1.30.
