"""Package the independently checked local research application, without private data."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    evidence = ROOT / "reports/workbench-v2"
    verification = json.loads((evidence / "verification.json").read_text())
    runtime = json.loads((evidence / "mcp-project-environment.json").read_text())
    assert verification["status"] == "succeeded" and runtime["success"] is True and runtime["mode"] == "calls"
    for name, expected in verification["tested_files"].items():
        assert sha(ROOT / name) == expected, f"Verified scientific file changed: {name}"
    names = ["app.py", "WORKBENCH.md", "USAGE.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "requirements-research.txt",
             "src/research_mcp.py", "src/opem_mcp.py", "src/requirements.txt", "src/tools/amphlett.py", ".streamlit/config.toml",
             "scripts/run_research.py", "scripts/print_research_mcp_config.py", "scripts/refresh_research_radar.py",
             "scripts/run_polarization.py", "scripts/print_mcp_config.py", "examples/amphlett-official.json", "dist/opem-mcp.zip",
             "reports/research-radar/github-metadata.json", "reports/research-radar/weekly-trending.json", "docs/github-research-2026-11-14.md"]
    for folder, pattern in [("src/research_core", "*.py"), ("examples/workbench", "*"), ("third_party", "*")]:
        names.extend(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).glob(pattern) if p.is_file())
    names = sorted(set(names))
    inventory = {name: sha(ROOT / name) for name in names}
    provenance = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "application": "research-pemfc non-writing workbench v0.2",
                  "scientific_source": {"repository": "https://github.com/ECSIM/opem", "commit": "27d343fb966361a4e6cc99650241f651778fc50f"},
                  "scientific_files": verification["tested_files"], "runtime_requirements_sha256": sha(ROOT / "requirements-research.txt"),
                  "example_data": "Explicitly synthetic software-validation cases, not experiment measurements.",
                  "tested_platform": "Linux/Python3.12.14", "archive_relocation_acceptance": "Separate delivery report; packaging alone is not acceptance."}
    readme = "# PEMFC 非写作研究工作台\n\n安装与使用请读 WORKBENCH.md。\n\n安装：`python3.12 -m venv research-env`，然后用该环境 Python 执行 `-m pip install -r requirements-research.txt`。\n启动：`research-env/bin/python -m streamlit run app.py`。Windows 使用 `research-env\\Scripts\\python.exe`。\n\n默认案例为合成验证数据。工作台不生成论文或专利文本。完整源代码与开发证据：https://github.com/xiaoguai53/research-pemfc\n"
    extra = {"PROVENANCE.json": (json.dumps(provenance, ensure_ascii=False, indent=2) + "\n").encode(), "README.md": readme.encode()}
    archive = ROOT / "dist/research-workbench.zip"
    archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in names:
            bundle.write(ROOT / name, "research-workbench/" + name)
        for name, value in extra.items():
            bundle.writestr("research-workbench/" + name, value)
            inventory[name] = hashlib.sha256(value).hexdigest()
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
    report = {"archive": "dist/research-workbench.zip", "archive_sha256": sha(archive), "packaged_files": inventory,
              "science_verification_sha256": sha(evidence / "verification.json"), "private_inputs_included": False}
    (evidence / "delivery-package.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"archive": str(archive), "sha256": report["archive_sha256"], "files": len(inventory)}))


if __name__ == "__main__":
    main()
