"""Public metadata retrieval and human-reviewable prior-art search records."""

from datetime import datetime, timezone
import html
import re
from urllib.parse import quote, urlencode

import pandas as pd
import requests

from .common import finish_run, new_run, write_json

CROSSREF_COLUMNS = ("doi", "title", "year", "venue", "authors", "source_url",
                    "crossref_citation_count", "access_level", "abstract", "full_text_reviewed")

def parse_crossref(payload):
    items = payload.get("message", {}).get("items")
    if not isinstance(items, list):
        raise ValueError("Crossref response does not contain a works list.")
    records, seen = [], set()
    for item in items:
        doi = str(item.get("DOI", "")).strip().lower()
        if not re.fullmatch(r"10\.\d{4,9}/\S+", doi) or doi in seen:
            continue
        seen.add(doi)
        title = " ".join(item.get("title") or [])
        dates = (item.get("published") or item.get("issued") or {}).get("date-parts", [[]])
        year = dates[0][0] if dates and dates[0] else None
        abstract = html.unescape(re.sub(r"<[^>]*>", " ", item.get("abstract") or ""))
        records.append({
            "doi": doi, "title": html.unescape(title), "year": year,
            "venue": "; ".join(item.get("container-title") or []),
            "authors": "; ".join(" ".join(str(a.get(k, "")) for k in ("given", "family")).strip() for a in item.get("author", [])),
            "source_url": "https://doi.org/" + quote(doi, safe="/"),
            "crossref_citation_count": item.get("is-referenced-by-count"),
            "access_level": "abstract" if abstract.strip() else "metadata",
            "abstract": re.sub(r"\s+", " ", abstract).strip(),
            "full_text_reviewed": False,
        })
    return records


def search_literature(query, limit=15, year_from=2018, year_to=None, output_dir=None):
    year_to = datetime.now(timezone.utc).year if year_to is None else year_to
    if not isinstance(query, str) or not 3 <= len(query.strip()) <= 500:
        raise ValueError("Search query must contain 3–500 characters.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("Limit must be an integer between 1 and 50.")
    if not 1900 <= year_from <= year_to <= datetime.now(timezone.utc).year:
        raise ValueError("Invalid publication-year interval.")
    params = {"query.bibliographic": query.strip(), "rows": limit,
              "filter": f"from-pub-date:{year_from}-01-01,until-pub-date:{year_to}-12-31"}
    response = requests.get("https://api.crossref.org/works", params=params,
                            headers={"User-Agent": "research-pemfc/0.2 (https://github.com/xiaoguai53/research-pemfc)"},
                            timeout=(10, 30))
    response.raise_for_status()
    payload = response.json()
    records = parse_crossref(payload)
    run = new_run("literature", {"query": query, "year_from": year_from, "year_to": year_to,
                                 "source_endpoint": response.url, "requested_limit": limit}, output_dir)
    write_json(run / "crossref-response.json", payload)
    write_json(run / "evidence.json", {"records": records, "retrieved_at_utc": datetime.now(timezone.utc).isoformat()})
    pd.DataFrame(records, columns=CROSSREF_COLUMNS).to_csv(run / "literature.csv", index=False)
    return finish_run(run, {"record_count": len(records), "full_text_reviewed_count": 0},
                      {"name": "Crossref public works metadata", "url": "https://api.crossref.org/works"},
                      ["Search results are metadata/available abstracts, not reviewed full text or a novelty determination."])


def prior_art_plan(topic, technical_features, output_dir=None):
    if not isinstance(topic, str) or not 3 <= len(topic.strip()) <= 500:
        raise ValueError("Topic must contain 3–500 characters.")
    if not isinstance(technical_features, list) or not 1 <= len(technical_features) <= 12 or any(not isinstance(x, str) or not x.strip() or len(x) > 200 for x in technical_features):
        raise ValueError("Provide 1–12 explicit technical-feature search terms.")
    rows = []
    for feature in technical_features:
        query = f"{topic.strip()} {feature.strip()}"
        rows.append({"technical_feature": feature.strip(), "query": query,
                     "google_patents_url": "https://patents.google.com/?" + urlencode({"q": query}),
                     "espacenet_url": "https://worldwide.espacenet.com/patent/search?" + urlencode({"q": query}),
                     "review_status": "not_searched", "evidence_identifier": "", "source_url": "",
                     "access_level": "", "reported_technical_effect": "", "difference_to_test": ""})
    run = new_run("prior-art-plan", {"topic": topic, "technical_features": technical_features}, output_dir)
    pd.DataFrame(rows).to_csv(run / "prior-art-matrix.csv", index=False)
    write_json(run / "search-plan.json", {"queries": rows, "live_patent_search_performed": False,
                                         "novelty_determined": False})
    return finish_run(run, {"query_count": len(rows), "live_patent_search_performed": False,
                            "novelty_determined": False},
                      {"name": "Explicit feature-to-prior-art search matrix"},
                      ["The links and matrix prepare a search; inspect actual patent documents and dates before judging technical differences."])
