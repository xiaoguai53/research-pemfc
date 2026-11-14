from urllib.parse import urlparse,parse_qs
from ._helpers import call,artifact,load


async def test_prior_art_plan_is_encoded_and_never_a_novelty_claim(tmp_path):
    r=await call("research_prior_art_plan",{"topic":"air cooled fuel cell","technical_features":["fan control & net power","membrane water"],"output_dir":str(tmp_path)})
    plan=load(artifact(r,"search-plan.json"))
    assert plan["live_patent_search_performed"] is False and plan["novelty_determined"] is False
    assert len(plan["queries"])==2
    first=plan["queries"][0]
    assert parse_qs(urlparse(first["google_patents_url"]).query)["q"]==["air cooled fuel cell fan control & net power"]
    assert first["review_status"]=="not_searched"
