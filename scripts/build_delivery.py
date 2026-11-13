"""Build the runtime-only archive after independent verification and installation checks."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "USAGE.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "third_party/OPEM-LICENSE",
    "third_party/Paper2Agent-LICENSE",
    "src/opem_mcp.py",
    "src/tools/amphlett.py",
    "src/requirements.txt",
    "scripts/run_polarization.py",
    "scripts/print_mcp_config.py",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    for report in ("mcp-project-environment.json", "mcp-clean-environment.json"):
        data = json.loads((ROOT / "reports" / report).read_text(encoding="utf-8"))
        if data.get("success") is not True or data.get("mode") != "calls":
            raise SystemExit(f"Required real-call runtime check has not passed: {report}")
    required = [ROOT / name for name in FILES]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Missing runtime files: " + ", ".join(missing))
    (ROOT / "dist").mkdir(exist_ok=True)
    archive = ROOT / "dist" / "opem-mcp.zip"
    provenance = {
        "scientific_repository": "https://github.com/ECSIM/opem",
        "scientific_commit": "27d343fb966361a4e6cc99650241f651778fc50f",
        "scientific_callable": "opem.Static.Amphlett.Static_Analysis",
        "wrapper_sha256": sha(ROOT / "src/tools/amphlett.py"),
        "requirements_sha256": sha(ROOT / "src/requirements.txt"),
        "tested_python": "3.12.14",
        "tested_platform": "Linux x86_64",
    }
    provenance_bytes = (json.dumps(provenance, indent=2) + "\n").encode()
    inventory = {}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in FILES:
            bundle.write(ROOT / name, f"opem-mcp/{name}")
            inventory[name] = sha(ROOT / name)
        bundle.writestr("opem-mcp/PROVENANCE.json", provenance_bytes)
        inventory["PROVENANCE.json"] = hashlib.sha256(provenance_bytes).hexdigest()
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise SystemExit("Archive integrity check failed.")
    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive": "dist/opem-mcp.zip",
        "archive_sha256": sha(archive),
        "packaged_files": inventory,
    }
    (ROOT / "reports/delivery-package.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
