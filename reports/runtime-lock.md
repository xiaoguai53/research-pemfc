# Portable runtime lock

- Agent: `/root/environment`
- Started at (UTC): `2026-11-13T16:52:02.371248966Z`
- Finished at (UTC): `2026-11-13T16:53:15.167147Z`
- Outcome: succeeded
- Resolver: uv 0.13.6
- Python target: 3.12; project interpreter is CPython 3.12.14

## Direct runtime requirements

`src/requirements.in` contains only:

```text
fastmcp==4.0.3
opem @ git+https://github.com/ECSIM/opem.git@27d343fb966361a4e6cc99650241f651778fc50f
```

The Git source resolved successfully. Recipient installation requires Git, a Python 3.12 environment, and network access to GitHub and the configured official package registry. It does not depend on the development checkout, editable installs, or any `/workspace` path.

## Compile procedure and exit status

Generated a temporary constraints file from `importlib.metadata.distributions()` in the tested project environment, excluding `opem` so its exact Git source could replace the local source URL, and excluding the two direct development roots `pytest` and `pytest-asyncio`. Constraints restrict versions without adding packages. The installed development-only `iniconfig` and `pluggy` therefore are absent from the resolved runtime closure as well.

Ran from the project root with inherited proxy and CA settings:

```bash
export UV_CACHE_DIR=/tmp/fuelcell-opem-uv-cache
uv pip compile --python opem-env/bin/python --python-version 3.12 --universal \
  --constraint /tmp/fuelcell-runtime-tested-constraints.txt \
  --no-header --no-annotate src/requirements.in --output-file src/requirements.txt
```

Exit status: 0. The resolver fetched the pinned Git revision, resolved the full 77-entry closure in 4.06 seconds, and wrote `src/requirements.txt`. The delivered lock is self-contained; the temporary constraints file is not needed for installation.

`--universal` preserves operating-system markers for portability. All 74 entries applicable to this Linux CPython 3.12 environment match the already-tested installed versions, including OPEM's source revision, FastMCP 4.0.3, MCP 2.3.0, and Pydantic 2.14.3. The additional platform-only pins are:

| Package | Pin | Applicability |
| --- | --- | --- |
| httpx2-jsfetch | 1.0 | Emscripten |
| pywin32 | 312 | Windows |
| pywin32-ctypes | 0.2.3 | Windows |

These additional pins were dependency-resolved, not executed on those platforms. Universal resolution does not establish Windows runtime validation.

## Checks

A metadata consistency check using `packaging.requirements.Requirement` completed with exit 0 and established:

- Every ordinary distribution has a single exact `==` version pin.
- Every applicable pin matches its installed tested distribution version.
- The OPEM URL names the full immutable source commit exactly.
- No pytest, pytest-asyncio, iniconfig, or pluggy entry appears.
- No local `file://`, editable, or `/workspace` reference appears in the delivered lock.

No dependencies were installed or modified for this assignment. The original immutable environment report remains untouched. Clean-environment installation and real scientific MCP calls remain separate acceptance checks.

## Artifact hashes

- `src/requirements.in`: `3c18070415abbc66704c815039a3b1011b3087496de0e3a30985adbf5f7c4e64`
- `src/requirements.txt`: `5df7c61ef917749b7d5598618f3fbc0771ed63bf1d4e7ce05ff8267414f06f75`
