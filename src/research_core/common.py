"""Shared local input and provenance handling for research operations."""

from datetime import datetime, timezone
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile
import zipfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
MAX_ROWS = 100_000
MAX_BYTES = 25 * 1024 * 1024


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"Nonfinite JSON number: {value}")

    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=invalid)


def input_info(path):
    path = Path(path)
    result = {"filename": path.name, "sha256": file_sha256(path), "bytes": path.stat().st_size}
    sidecar = path.with_suffix(".provenance.json")
    if sidecar.is_file():
        if sidecar.stat().st_size > 512 * 1024:
            raise ValueError("Derived-input provenance is too large.")
        result["declared_derivation"] = read_json(sidecar)
    return result


def load_table(path, sheet_name=0, string_columns=None):
    """Read bounded CSV/TSV/XLSX without changing labels or modifying the source."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Input must be an existing table no larger than 25 MiB.")
    suffix = path.suffix.lower()
    dtype = {name: "string" for name in (string_columns or [])}
    if suffix in (".csv", ".tsv"):
        sep = "\t" if suffix == ".tsv" else ","
        with path.open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream, delimiter=sep), [])
        reader = lambda: pd.read_csv(path, sep=sep, encoding="utf-8-sig", nrows=MAX_ROWS + 1, keep_default_na=False, na_values=[""], dtype=dtype)
    elif suffix == ".xlsx":
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > 5000 or sum(member.file_size for member in members) > 250 * 1024 * 1024:
                raise ValueError("Workbook exceeds the supported expanded size.")
        header = pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=1, engine="openpyxl").iloc[0].tolist()
        reader = lambda: pd.read_excel(path, sheet_name=sheet_name, nrows=MAX_ROWS + 1, engine="openpyxl", keep_default_na=False, na_values=[""], dtype=dtype)
    else:
        raise ValueError("Supported inputs are UTF-8 CSV/TSV and .xlsx; convert other formats explicitly.")
    if not header or len(header) > 200 or any(not isinstance(x, str) or not x.strip() for x in header):
        raise ValueError("Table needs 1–200 nonempty text column names.")
    if len(header) != len(set(header)):
        raise ValueError("Duplicate column names are not supported; rename them explicitly.")
    frame = reader()
    if frame.empty or len(frame) > MAX_ROWS:
        raise ValueError("Table must contain 1–100,000 rows; no rows were silently sampled.")
    return frame


def new_run(kind, inputs, output_dir=None):
    base = Path(output_dir).expanduser().resolve() if output_dir else ROOT / "results" / "workbench"
    base.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=kind + "-", dir=base))
    write_json(run / "inputs.json", inputs)
    return run


def finish_run(run, summary, method, warnings=None):
    """Return small metadata and paths; full scientific data stay in local files."""
    run = Path(run)
    warnings = list(warnings or [])
    write_json(run / "summary.json", summary)
    versions = {}
    for package in ("opem", "numpy", "scipy", "pandas", "optuna", "SALib", "matplotlib", "streamlit"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    files = sorted(path for path in run.rglob("*") if path.is_file() and path.name != "manifest.json")
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "versions": versions,
        "summary": summary,
        "warnings": warnings,
        "files": {path.relative_to(run).as_posix(): file_sha256(path) for path in files},
    }
    write_json(run / "manifest.json", manifest)
    files.append(run / "manifest.json")
    reference = method.get("url") or method.get("physical_model_source") or method.get("source") or method["name"]
    return {"message": "Research operation completed; inspect the method, provenance and limits with the results.", "reference": reference,
            "summary": summary, "method": method, "warnings": warnings,
            "run_dir": str(run.resolve()),
            "artifacts": [{"description": path.relative_to(run).as_posix(), "path": str(path.resolve())} for path in files]}


def export_run(run_dir):
    run = Path(run_dir).resolve()
    manifest = read_json(run / "manifest.json")
    names = list(manifest["files"]) + ["manifest.json"]
    for name in names:
        path = (run / name).resolve()
        if not path.is_relative_to(run) or not path.is_file():
            raise ValueError("Artifact escapes its run or is missing.")
        if name in manifest["files"] and file_sha256(path) != manifest["files"][name]:
            raise ValueError(f"Artifact changed since the run: {name}")
    archive = run / "research-evidence.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in names:
            bundle.write(run / name, f"research-evidence/{name}")
    return archive
