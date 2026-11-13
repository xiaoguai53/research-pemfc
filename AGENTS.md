# Research workspace instructions

This is a hydrogen PEMFC and air-cooled/open-cathode fuel-cell research project. Communicate with the user in Chinese by default. Read `USAGE.md`, `docs/research-roadmap.zh-CN.md`, and `research/project.json` for scope.

Use `.agents/skills/fuelcell-research/SKILL.md` for domain tasks and the complete upstream `.agents/skills/paper2agent/SKILL.md` for new paper/code conversions. Follow its specialist and independent-verifier workflow for conversions. Keep new paper conversions in separate directories/environments.

Scientific code must call its pinned upstream implementation. Do not expand the baseline's claims to air-cooled thermal/water dynamics, experimental calibration, fan control, or CFD without a corresponding implementation and validated reference. Preserve units and single-cell/stack distinctions.

Use the project's explicit Python interpreter. For original-source replay, restore `repo/opem/` using `scripts/restore_sources.py`. Project tests reside under `tests/code/`; runtime-only dependencies are under `src/requirements.txt`. Keep reports traceable and do not rewrite completed evidence merely to refresh hashes after code changes.

Do not commit raw measurements or unpublished papers from `research/inputs/`, credentials, virtual environments, or generated results. Existing `.gitignore` exclusions do not by themselves authorize publishing other private inputs.
