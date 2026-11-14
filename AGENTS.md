# Research workspace instructions

This is a hydrogen PEMFC and air-cooled/open-cathode fuel-cell research project. Communicate with the user in Chinese by default. Read `WORKBENCH.md`, `docs/research-roadmap.zh-CN.md`, and `research/project.json` for scope. The user has writing tools: exclude manuscript/patent drafting from this workbench. `USAGE.md` and original runtime records describe the retained v0.1 single-model server.

Use `.agents/skills/fuelcell-research/SKILL.md` for domain tasks and the complete upstream `.agents/skills/paper2agent/SKILL.md` for new paper/code conversions. Follow its specialist and independent-verifier workflow for conversions. Keep new paper conversions in separate directories/environments.

Scientific code must call its pinned upstream implementation. Do not expand the baseline's claims to air-cooled thermal/water dynamics, experimental calibration, fan control, or CFD without a corresponding implementation and validated reference. Preserve units and single-cell/stack distinctions.

Use the project's explicit Python interpreter. For original-source replay, restore `repo/opem/` using `scripts/restore_sources.py`. Project tests reside under `tests/code/`; runtime-only dependencies are under `src/requirements.txt`. Keep reports traceable and do not rewrite completed evidence merely to refresh hashes after code changes.

Do not commit raw measurements or unpublished papers from `research/inputs/`, credentials, virtual environments, or generated results. Existing `.gitignore` exclusions do not by themselves authorize publishing other private inputs.

The v0.2 entry points are app.py and src/research_mcp.py; scientific methods live in src/research_core. Use research-env/bin/python and requirements-research.txt. Keep original v0.1 production/evidence intact. New validation and source records belong under reports/workbench-v2; do not refresh old hashes to falsely imply coverage of new code.

Count actual experimental replicates, never time rows, for inference. Preserve prescribed/grouped holdouts and do not use test responses for fitting. Distinguish measured auxiliary power from unknown power; no zero imputation to manufacture net efficiency. Label all synthetic examples. Sobol analysis requires its actual ordered design, and constrained recommendations remain pending measurements. Literature metadata/abstracts and patent search plans must not be represented as full-text review or novelty determinations.
