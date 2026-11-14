---
name: fuelcell-research
description: Use this workspace for hydrogen PEM fuel cell and air-cooled/open-cathode fuel cell literature, reproducible model reuse, and Paper2Agent conversions.
---

# Fuel cell research workspace

Read the workspace `WORKBENCH.md` and `docs/research-roadmap.zh-CN.md` before using its tools. Reply in Chinese unless the user requests another language. This project excludes manuscript and patent drafting; the user has a separate writing tool.

For a new paper or code repository, use the neighboring `paper2agent/SKILL.md` and keep each conversion's environments and outputs separate. The existing OPEM baseline does not imply a different paper or stack has been reproduced.

## Existing capability

The research workbench exposes measured-data profiling, replicate-aware comparison, bounded calibration, model Sobol sensitivity, LHS design, constrained Optuna 5 next-trial recommendations and source-level evidence records. New core functions are under `src/research_core`; the server is `src/research_mcp.py`. Use `research-env` and `requirements-research.txt`. Keep synthesis-only and actual measurements clearly separated. The old single-model `USAGE.md`, source and validation remain a historical intact component.

Before inference, identify real independent replicates and prescribed contrasts. Aggregate time samples within actual replicates, align paired IDs explicitly and compare matched loads. Preserve holdout groups and test-response separation. Do not use model-fit residuals to invent parameter certainty, and never claim pending candidates satisfy unmeasured outcome constraints. Export facts, data and uncertainty for the user's writing tool, not drafted conclusions.

`opem_simulate_polarization` wraps OPEM's original Amphlett static model. Read its actual schema and documented units. The scientific implementation must remain a direct upstream call. Keep the input/source version with results.

## Domain boundaries

- Distinguish single-cell voltage from stack voltage, amperes from A/cm², Kelvin from Celsius, absolute pressure from gauge pressure, and oxygen partial pressure from total air pressure.
- Membrane water content lambda is not relative humidity. Fan duty cycle is not measured airflow.
- OPEM's specified temperature is not a prediction of an air-cooled stack's temperature. Static sweeps do not establish dynamic stability or water balance.
- OPEM's native thermal-power approximation is not a validated fan-sizing heat load. Gross stack power excludes auxiliary power unless the selected source explicitly models it.
- Identify forced-convection open-cathode, passive air-breathing, and separate cooling-channel designs before transferring a model.
- Do not invent stack measurements, fitted parameters, experimental validation, or a scientific algorithm to fill missing source code. Retain blocked work and the evidence needed to proceed.

Inputs in `research/inputs/` are private by default. Do not publish measurements, proprietary geometries, credentials, or unpublished manuscripts merely because the code workspace is tracked in Git.
