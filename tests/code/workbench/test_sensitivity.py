import numpy as np
import pandas as pd
import pytest
from SALib.sample import sobol as sampler
from SALib.analyze import sobol as analyzer
from SALib.test_functions import Ishigami
from research_core import calibration
from ._helpers import call,artifact,load,EXAMPLES,native


async def test_ordered_design_all_native_responses_and_indices(tmp_path):
    args={"parameters_path":str(EXAMPLES/"model-parameters.json"),"bounds_path":str(EXAMPLES/"sensitivity-bounds.json"),"current_A":40.,"n_base":32,"seed":42,"output_dir":str(tmp_path)}
    r=await call("research_model_sensitivity",args)
    bounds=load(EXAMPLES/"sensitivity-bounds.json")["factors"]
    problem={"num_vars":len(bounds),"names":[f["name"] for f in bounds],"bounds":[[f["lower"],f["upper"]] for f in bounds]}
    expected_x=sampler.sample(problem,32,calc_second_order=False,seed=42)
    values=pd.read_csv(artifact(r,"ordered-sobol-responses.csv"))
    np.testing.assert_allclose(values[problem["names"]],expected_x,rtol=1e-12)
    base=load(EXAMPLES/"model-parameters.json")
    mapping={"temperature_K":"T","hydrogen_partial_pressure_atm":"PH2","oxygen_partial_pressure_atm":"PO2","active_area_cm2":"A","membrane_thickness_cm":"l","membrane_water_content":"lambda","cell_count":"N","max_current_density_A_cm2":"JMax","electronic_resistance_ohm":"R"}
    expected=[]
    for row in expected_x:
        p=dict(base);p.update(zip(problem["names"],row))
        expected.append(native.point_voltage(40.,{v:p[k] for k,v in mapping.items()}))
    np.testing.assert_allclose(values.stack_voltage_V,expected,rtol=1e-12,atol=1e-12)
    si=analyzer.analyze(problem,np.asarray(expected),calc_second_order=False,seed=42,print_to_console=False)
    actual=pd.read_csv(artifact(r,"sensitivity-indices.csv"))
    for key in ["S1","ST","S1_conf","ST_conf"]:np.testing.assert_allclose(actual[key],si[key],rtol=1e-12,atol=1e-12)
    assert r["summary"]["model_evaluations"]==160


def test_ishigami_analytic_benchmark():
    problem={"num_vars":3,"names":["x1","x2","x3"],"bounds":[[-np.pi,np.pi]]*3}
    x=sampler.sample(problem,4096,calc_second_order=False,seed=42)
    si=analyzer.analyze(problem,Ishigami.evaluate(x),calc_second_order=False,seed=42,print_to_console=False)
    np.testing.assert_allclose(si["S1"],[.3139,.4424,0],atol=.025)
    np.testing.assert_allclose(si["ST"],[.5576,.4424,.2437],atol=.025)


async def test_zero_variance_is_not_a_fake_zero_sensitivity(monkeypatch,tmp_path):
    monkeypatch.setattr(calibration,"amphlett_points",lambda *a,**k:np.array([3.]))
    with pytest.raises(Exception,match="undefined"):
        await call("research_model_sensitivity",{"parameters_path":str(EXAMPLES/"model-parameters.json"),"bounds_path":str(EXAMPLES/"sensitivity-bounds.json"),"current_A":40.,"n_base":32,"output_dir":str(tmp_path)})
    assert not list(tmp_path.rglob("sensitivity-indices.csv"))
