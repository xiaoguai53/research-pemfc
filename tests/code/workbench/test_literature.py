import pandas as pd
import pytest
import requests
from research_core import evidence
from ._helpers import call,artifact,load


PAYLOAD={"message":{"items":[{"DOI":"10.1234/ABC","title":["A source"],"published":{"date-parts":[[2024]]},"abstract":"<jats:p>Available abstract</jats:p>"},{"DOI":"10.1234/abc","title":["duplicate"]},{"DOI":"10.1234/other","title":["Metadata only"]}]}}


class Response:
    url="https://api.crossref.org/works?query.bibliographic=test"
    def raise_for_status(self):pass
    def json(self):return PAYLOAD


async def test_doi_dedup_and_access_levels_through_mcp(monkeypatch,tmp_path):
    monkeypatch.setattr(evidence.requests,"get",lambda *a,**k:Response())
    r=await call("research_search_literature",{"query":"fuel cell","limit":3,"output_dir":str(tmp_path)})
    records=load(artifact(r,"evidence.json"))["records"]
    assert len(records)==2 and [r["access_level"] for r in records]==["abstract","metadata"]
    assert all(v["full_text_reviewed"] is False for v in records)
    assert records[0]["doi"]=="10.1234/abc"
    assert records[0]["abstract"]=="Available abstract"
    assert r["summary"]["full_text_reviewed_count"]==0


async def test_service_failure_is_not_fabricated_success(monkeypatch,tmp_path):
    def bad(*a,**k):raise requests.HTTPError("503 upstream unavailable")
    monkeypatch.setattr(evidence.requests,"get",bad)
    with pytest.raises(Exception,match="503"):
        await call("research_search_literature",{"query":"fuel cell","output_dir":str(tmp_path)})
    assert not list(tmp_path.rglob("evidence.json"))


async def test_zero_records_still_export_a_readable_schema(monkeypatch,tmp_path):
    class Empty(Response):
        def json(self):return {"message":{"items":[]}}
    monkeypatch.setattr(evidence.requests,"get",lambda *a,**k:Empty())
    r=await call("research_search_literature",{"query":"fuel cell","output_dir":str(tmp_path)})
    frame=pd.read_csv(artifact(r,"literature.csv"))
    assert frame.empty and "doi" in frame.columns
