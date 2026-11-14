"""Fetch public GitHub repository metadata and the actual weekly Trending page."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request


REPOSITORIES = ["karpathy/autoresearch", "K-Dense-AI/scientific-agent-skills", "optuna/optuna", "scipy/scipy",
                "SALib/SALib", "meta-pytorch/botorch", "meta/Ax", "Future-House/paper-qa", "HKUDS/AI-Researcher",
                "SakanaAI/AI-Scientist", "microsoft/RD-Agent", "mlflow/mlflow", "treeverse/dvc", "streamlit/streamlit",
                "marimo-team/marimo", "docling-project/docling", "wanshuiyin/Auto-claude-code-research-in-sleep",
                "NVIDIA/auto-ontology", "google-deepmind/mujoco", "anthropics/skills"]


def get_bytes(url, github_api=False):
    headers = {"User-Agent": "research-pemfc/0.2", "Accept": "application/vnd.github+json" if github_api else "text/html"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if github_api and token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as response:
        return response.read(), response.url


def parse_weekly(raw):
    rows = []
    for article in re.findall(r"<article\b.*?</article>", raw.decode("utf-8"), re.S):
        match = re.search(r'<h2\b.*?<a\b[^>]*href="/([^\"]+)"', article, re.S)
        if not match:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", article)).strip()
        growth = re.search(r"([\d,]+) stars this week", text)
        rows.append({"rank": len(rows) + 1, "repository": match.group(1),
                     "weekly_stars": int(growth.group(1).replace(",", "")) if growth else None, "text": text[:600]})
    return rows


def refresh(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    def fetch(repo):
        try:
            raw, _ = get_bytes("https://api.github.com/repos/" + repo, github_api=True)
            source = json.loads(raw)
            record = {key: source.get(key) for key in ("full_name", "html_url", "stargazers_count", "forks_count", "pushed_at", "archived", "default_branch", "description", "language")}
            record["license"] = (source.get("license") or {}).get("spdx_id")
            record["fetched_at_utc"] = now
            return record
        except Exception as exc:
            return {"requested_repository": repo, "error": str(exc), "fetched_at_utc": now}
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows = list(pool.map(fetch, REPOSITORIES))
    metadata = {"fetched_at_utc": now, "display_timezone": "Asia/Shanghai",
                "source": "GitHub REST API; stargazers_count is cumulative, not weekly growth.", "repositories": rows}
    url = "https://github.com/trending?since=weekly"
    try:
        raw, final_url = get_bytes(url)
        entries = parse_weekly(raw)
        weekly = {"fetched_at_utc": now, "url": final_url, "sha256": hashlib.sha256(raw).hexdigest(),
                  "status": "parsed" if entries else "unparsed", "repositories": entries}
    except Exception as exc:
        weekly = {"fetched_at_utc": now, "url": url, "status": "unavailable", "error": str(exc), "repositories": []}
    for name, value in [("github-metadata.json", metadata), ("weekly-trending.json", weekly)]:
        temporary = output / (name + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output / name)
    return {"fetched_at_utc": now, "metadata_success": sum("full_name" in row for row in rows), "metadata_errors": sum("error" in row for row in rows),
            "weekly_status": weekly["status"], "weekly_entries": len(weekly["repositories"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "reports/research-radar")
    print(json.dumps(refresh(parser.parse_args().output), indent=2))
