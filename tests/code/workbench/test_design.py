import numpy as np
import pandas as pd
import pytest
from ._helpers import call,artifact,load,dump,EXAMPLES


async def test_latin_hypercube_strata_centers_and_reproducibility(tmp_path):
    args={"bounds_path":str(EXAMPLES/"experiment-bounds.json"),"n_samples":8,"center_replicates":3,"seed":7,"output_dir":str(tmp_path)}
    a=await call("research_design_experiments",args);b=await call("research_design_experiments",args)
    av=pd.read_csv(artifact(a,"planned-experiments.csv"));bv=pd.read_csv(artifact(b,"planned-experiments.csv"))
    pd.testing.assert_frame_equal(av,bv)
    assert a["run_dir"]!=b["run_dir"]
    factors=load(EXAMPLES/"experiment-bounds.json")["factors"]
    for f in factors:
        vals=av.loc[av.design_role=="lhs_screening",f["name"]]
        strata=np.floor((vals-f["lower"])/(f["upper"]-f["lower"])*8).astype(int)
        assert sorted(strata)==list(range(8))
        np.testing.assert_allclose(av.loc[av.design_role=="center_repeat",f["name"]],(f["lower"]+f["upper"])/2)
    assert set(av.status)=={"awaiting_measurement"}
    assert av.candidate_id.is_unique and av.execution_order.tolist()==list(range(1,12))


async def test_reserved_output_column_cannot_overwrite_factor(tmp_path):
    cfg={"factors":[{"name":"status","unit":"1","lower":0.,"upper":1.}]}
    with pytest.raises(Exception,match="reserved"):
        await call("research_design_experiments",{"bounds_path":dump(tmp_path/"bounds.json",cfg),"output_dir":str(tmp_path)})
