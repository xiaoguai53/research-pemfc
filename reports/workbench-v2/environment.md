# Research workbench v2 environment handoff

- Agent identity: `/root/research_environment`
- Started at UTC: `2026-11-13T17:28:57.192001866Z`
- Finished at UTC: `2026-11-13T17:31:36.251408Z`
- Status: succeeded
- Interpreter: `/workspace/fuelcell-paper2agent/research-env/bin/python`
- Platform: Linux x86_64; Python 3.12.14; CPU route
- Runtime lock: `requirements-research.txt`
- Full development snapshot: `reports/workbench-v2/environment-freeze.txt`
- API/source evidence: `reports/workbench-v2/source-provenance.json`

## Isolation and source identity

Created the new project-owned `research-env/` with the existing Python 3.12 interpreter. Installation used the inherited HTTPS proxy and CA settings, official package registry distributions, and the exact original OPEM Git source commit. No credentials were added or exposed.

The original `opem-env/`, `src/requirements.txt`, original source tree, and v0.1 reports were not edited.

Installed OPEM is version 1.4 from `git+https://github.com/ECSIM/opem.git@27d343fb966361a4e6cc99650241f651778fc50f`. Its `direct_url.json` records that exact Git commit. The imported Amphlett source is under the new environment's site-packages, and SHA-256 `fafd388f1f6fded85f745de39ec03267ab301708260ad96333b9aa333f816bd6` matches the unchanged pinned checkout source.

## Tested package versions

| Package | Version |
| --- | --- |
| numpy | 2.5.4 |
| scipy | 1.18.1 |
| pandas | 3.1.1 |
| matplotlib | 3.11.2 |
| optuna | 5.0.0 |
| SALib | 1.6.0 |
| openpyxl | 3.1.5 |
| streamlit | 1.67.0 |
| fastmcp | 4.0.3 |
| opem | 1.4 |
| pytest | 9.2.0 |
| pytest-asyncio | 1.5.0 |

The complete development environment contains 111 installed packages, including pytest and pytest-asyncio. All installed package dependencies are compatible. No GPU, native scientific data service, notebook kernel or external model/API key is needed by these selected APIs.

## Runtime lock verification

The portable universal lock has 111 entries. All 77 original baseline requirements retain their exact pins, VCS URL and platform markers. 107 entries apply to this Linux/Python runtime and all match the installed versions. Remaining entries represent other platforms; those were resolved rather than executed. The lock has no editable/local paths or pytest development roots. Runtime SHA-256: `36a92350113cbecd802d86ec671c70a2bfed730384237d0d711b78a0267d79c6`.

The OPEM source is a fixed Git URL, so recipients need Git and network access to the official distribution sources. Windows/platform markers are included, but Windows execution has not been tested.

## Commands and actual outcomes

| Command/check | Outcome |
| --- | --- |
| `UV_CACHE_DIR=/tmp/fuelcell-research-uv-cache uv venv research-env --python python3.12` | Exit 0; Python 3.12.14 |
| `UV_CACHE_DIR=/tmp/fuelcell-research-uv-cache uv pip install --python research-env/bin/python -r requirements-research.in 'pytest==9.2.0' 'pytest-asyncio==1.5.0'` | Exit 0; 111 packages |
| `UV_CACHE_DIR=/tmp/fuelcell-research-uv-cache uv pip check --python research-env/bin/python` | Exit 0; compatible |
| `UV_CACHE_DIR=/tmp/fuelcell-research-uv-cache uv pip freeze --python research-env/bin/python > reports/workbench-v2/environment-freeze.txt` | Exit 0 |
| `UV_CACHE_DIR=/tmp/fuelcell-research-uv-cache uv pip compile --python research-env/bin/python --python-version 3.12 --universal --no-header --no-annotate --output-file requirements-research.txt requirements-research.in` | Exit 0; 111-entry runtime lock |
| OPEM installed/source hash and VCS direct_url inspection | Exit 0; exact source origin confirmed |
| Installed lock versions and baseline-pin comparison | Exit 0; all 77 original requirements preserved |
| Native API readiness checks | Exit 0; checks below passed |

uv reported that it could not hardlink the cache to the environment and copied the files instead. This was an installation-performance message, not a dependency or runtime failure.

## API readiness and version-specific guidance

Saved signatures and installed Python source-file hashes for the selected APIs are in `source-provenance.json`.

- `scipy.optimize.least_squares`: a native residual minimization smoke recovered a known scalar value.
- `scipy.stats.ttest_rel` and `ttest_ind(equal_var=False)`: results expose `confidence_interval(confidence_level=0.95)` and returned finite statistics/intervals.
- `scipy.stats.qmc.LatinHypercube`: supports both the current `rng` and compatibility `seed` argument; an 8-by-2 native sample had valid bounds.
- `SALib.sample.sobol.sample` and `SALib.analyze.sobol.analyze`: `calc_second_order=False`, `seed`, bootstrap count and 95% confidence options were inspected; a 128-base-sample additive smoke returned finite two-variable indices. This smoke establishes API readiness, not scientific acceptance accuracy.
- `optuna.samplers.TPESampler`, `Study.ask` and `Study.tell`: native observed-trial replay and a subsequent bounded suggestion passed.
- **Optuna 5 constraints:** `constraints_func` is still accepted but emits a FutureWarning and is deprecated. Use `trial.set_constraint(key, value)` before telling the trial's measured objective. All constraint values <= 0 mean feasible. `FrozenTrial.constraints` is the named constraint dictionary. A native four-observation replay plus next ask using this current API passed. `constant_liar=True` is available for pending batch trials. No experimental framework source was changed.

## Scope and handoff

This environment report establishes dependency restoration, source identity and API availability only. It does not establish the correctness of new workbench wrappers, complete experimental design, physical PEMFC calibration, independent scientific verification, browser UI behavior, clean-environment MCP packaging, or Windows execution. Those checks belong to the implementation/verification stages.

No scientific implementation files, shared coordinator state, user experimental inputs or previous reports were changed. Environment changes remain serialized through the coordinator.
