# Tokenomics Analyzer

A Claude Code agent for rigorous token economic systems analysis. Given any description of a token model — verbal, structured, or partial — it produces a comprehensive audit: parsed model, severity-rated findings, simulations, Excel financial model, and a written report with fix proposals.

---

## What it produces

- **Completeness scorecard** — assesses input against 6 universal questions before analysis begins; surfaces gaps and asks targeted follow-up questions
- **Parsed TokenModel** — structured YAML extracted from any verbal description
- **Weakness scan** — 51 flags across 5 severity levels (Critical / High / Medium / Low / Informational); every Critical and High finding includes a specific, implementable fix proposal
- **Simulations** — cadCAD-style supply curves, Monte Carlo price bands, parameter sensitivity heatmaps, death spiral stress tests, staking reflexivity analysis, multi-actor behavioral dynamics, governance participation modeling, and adoption curve analysis
- **Excel financial model** — supply schedule, vesting unlocks, treasury runway, and revenue projections across Base / Bear / Stress scenarios
- **Audit report** — A–F grade with justification, system dynamics analysis, equilibrium conditions, viable operating region, sustainability requirements, and optimization roadmap

---

## Prerequisites

- [Claude Code](https://claude.ai/code)
- Python 3.10+

```bash
pip install -r requirements.txt
```

---

## Usage

Open a Claude Code session in this directory:

```bash
claude
```

Then use the slash commands:

```
/audit "describe your token here"          # full pipeline: parse → scan → simulate → report
/audit models/my-token.yaml               # same, starting from an existing model file

/assess-model "describe your token here"   # completeness check only — scorecard + gap questions
/parse-model "describe your token here"    # parse to structured YAML, no full audit

/simulate models/my-token.yaml            # run simulations for an existing model
/stress-test models/my-token.yaml         # adversarial scenarios: bear market, whale exit, revenue collapse
/benchmark models/my-token.yaml           # comparison table against comparable protocols
```

Outputs are saved to:

| Artifact | Location |
|---|---|
| Parsed model | `models/<token-name>.yaml` |
| Simulation scripts | `simulations/<token-name>/` |
| Charts and CSVs | `analysis/<token-name>/` |
| Excel model | `analysis/<token-name>/<token-name>_model.xlsx` |
| Audit report | `reports/<token-name>_audit.md` |

---

## Repository structure

```
models/         ← TokenModel YAML files + schema.yaml
knowledge/      ← domain knowledge base (selectively loaded per token features)
simulations/    ← simulation scripts (generated per audit)
analysis/       ← outputs: charts, CSVs, Excel models
reports/        ← final audit reports
templates/      ← report skeleton
requirements.txt
```

---

## Domain knowledge base

| File | Covers |
|---|---|
| `token_archetypes.md` | 7 archetypes with classification decision tree and failure patterns |
| `failure_postmortems.md` | Terra/LUNA, Iron Finance, OHM, Anchor, Basis Cash; 10-condition death spiral checklist |
| `failure_postmortems_2024.md` | Stream Finance/xUSD, Compound governance capture, 2024–2026 design patterns |
| `staking_dynamics.md` | Ethereum issuance formula (post-Dencun), reflexivity loop, equilibrium model |
| `governance_attacks.md` | Beanstalk flash loan, Tornado Cash, Build Finance; 22-item governance checklist |
| `vetokens_and_emissions.md` | veCRV boost formula, Solidly failure, Velodrome fixes, emission decay curves |
| `treasury_design.md` | Runway formula, diversification benchmarks, POL mechanics |
| `fee_economics.md` | FCR formula, revenue taxonomy, unit economics benchmarks, value accrual patterns |
| `token_velocity.md` | MV=PQ framework, velocity trap, sink mechanism effectiveness table |
| `scoring_rubric.md` | Grade A–F thresholds, F disqualifiers, scoring process |
| `red_flags_master.md` | 51 flags (8 Critical / 14 High / 14 Medium / 10 Low / 5 Informational) |
| `simulation_baselines.md` | Default simulation parameters, 5 scenarios, Monte Carlo config |
| `reference_benchmarks.md` | Live data: BTC / ETH / UNI / CRV / GMX / stETH |
| `worked_example.md` | Complete fictional audit (AgroFi/AGRO) as quality calibration anchor |
| `academic_citations.md` | Verified citations: Roughgarden, Ethereum specs, Buterin, Samani, Pfeffer |

---

## Status

| Component | Status |
|---|---|
| Knowledge base — 15 domain files | ✅ Complete |
| Schema, report template, slash commands | ✅ Complete |
| Weakness scanner — 51 flags across 5 severities | ✅ Complete |
| Completeness assessment — 6-question scorecard | ✅ Complete |
| Simulation suite — cadCAD/Mesa scripts | 🔴 In progress |
| Excel spreadsheet generator | 🔴 Pending |
| Extended knowledge base — GameFi, NFT, behavioral, theoretical foundations | 🔴 Pending |

---

## Stack

```
Python: numpy, pandas, matplotlib, scipy, mesa, openpyxl, plotly, jinja2, pyyaml, seaborn
Agent:  Claude Code (claude-sonnet-4-6 or later)
```
