"""Non-writing research workflows, with the original model tool retained."""

from typing import Annotated, Literal
from datetime import datetime, timezone

from fastmcp import FastMCP
from pydantic import BeforeValidator, Field

from research_core import data, calibration, design, evidence
from tools.amphlett import amphlett_mcp


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Physical numeric arguments must be numbers, not booleans or strings.")
    return value


def _integer(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Integer arguments must be integers, not booleans or strings.")
    return value


Real = Annotated[float, BeforeValidator(_number)]
Integer = Annotated[int, BeforeValidator(_integer)]
mcp = FastMCP(name="PEMFC Research Workbench")
mcp.mount(amphlett_mcp)


@mcp.tool()
def research_analyze_measurements(
    data_path: Annotated[str, Field(description="Local CSV/TSV/XLSX; required current_A and stack_voltage_V, optional measured power/metadata columns.")],
    sheet_name: Annotated[str, Field(description="Excel sheet name; empty selects the first sheet.")] = "",
    output_dir: Annotated[str | None, Field(description="Local output base; each operation creates a fresh run.")] = None,
) -> dict:
    """Check measured data and derive explicitly supported electrical quantities.
    Local table → quality records, derived CSV, figures and provenance.
    """
    return data.analyze_measurements(data_path, output_dir=output_dir, sheet_name=sheet_name or 0)


@mcp.tool()
def research_compare_conditions(
    data_path: Annotated[str, Field(description="Table containing real condition and replicate IDs, measurements and the selected metric.")],
    metric: Annotated[str, Field(description="Prespecified numeric outcome column; use a measured or explicitly derived quantity.")],
    group_a: Annotated[str, Field(description="Baseline condition label, preserved exactly.")],
    group_b: Annotated[str, Field(description="Candidate condition label; effect is B minus A.")],
    design_type: Annotated[Literal["paired", "independent"], Field(description="Actual experimental design, chosen before looking at significance.")],
    target_current_A: Annotated[Real, Field(description="Matched comparison current in A.")],
    current_tolerance_A: Annotated[Real, Field(description="Allowed current deviation in A around the target.")] = 0.1,
    condition_column: Annotated[str, Field(description="Column of actual user-supplied condition labels.")] = "condition",
    replicate_column: Annotated[str, Field(description="Column identifying real independent experiments or matched pairs.")] = "replicate_id",
    output_dir: Annotated[str | None, Field(description="Fresh local result directory base.")] = None,
) -> dict:
    """Compare conditions after aggregating repeated rows within real replicates.
    Prespecified matched-load comparison → effect, 95% interval and applicable test statistics.
    """
    return data.compare_conditions(data_path, metric, group_a, group_b, design_type, target_current_A,
                                   current_tolerance_A, condition_column, replicate_column, output_dir=output_dir)


@mcp.tool()
def research_calibrate_model(
    data_path: Annotated[str, Field(description="Local polarization table, optionally containing per-row measured temperature and run IDs.")],
    config_path: Annotated[str, Field(description="JSON with known model parameters, R/lambda fit bounds and explicit holdout settings.")],
    output_dir: Annotated[str | None, Field(description="Fresh local calibration output base.")] = None,
) -> dict:
    """Calibrate native Amphlett parameters using bounded SciPy optimization.
    Measurements and model config → fitted parameters, held-out predictions and identifiability diagnostics.
    """
    return calibration.calibrate_amphlett(data_path, config_path, output_dir=output_dir)


@mcp.tool()
def research_design_experiments(
    bounds_path: Annotated[str, Field(description="JSON factors with unique names, lower/upper bounds and units.")],
    n_samples: Annotated[Integer, Field(description="Number of Latin-hypercube screening candidates, 2–256.")] = 12,
    center_replicates: Annotated[Integer, Field(description="Planned repeated center points, 0–20.")] = 3,
    seed: Annotated[Integer, Field(description="Recorded random seed for reproducible design.")] = 42,
    output_dir: Annotated[str | None, Field(description="Fresh local design output base.")] = None,
) -> dict:
    """Generate a randomized Latin-hypercube experiment plan with center repeats.
    User-declared factor bounds → pending experiment CSV and a design plot.
    """
    return design.generate_design(bounds_path, n_samples, center_replicates, seed, output_dir)


@mcp.tool()
def research_model_sensitivity(
    parameters_path: Annotated[str, Field(description="JSON containing known/fitted readable Amphlett parameters.")],
    bounds_path: Annotated[str, Field(description="Independent uniform bounds for continuous parameters actually used by Amphlett.")],
    current_A: Annotated[Real, Field(description="Fixed positive operating current in A.")],
    n_base: Annotated[Integer, Field(description="Sobol base sample size: power of two between 32 and 2048.")] = 128,
    seed: Annotated[Integer, Field(description="Recorded sampling/bootstrap seed.")] = 42,
    output_dir: Annotated[str | None, Field(description="Fresh local model-sensitivity output base.")] = None,
) -> dict:
    """Estimate model-conditional voltage sensitivities using SALib Sobol analysis.
    Original model and ordered sampling design → first/total indices, confidence estimates and figures.
    """
    return design.model_sensitivity(parameters_path, bounds_path, current_A, n_base, seed, output_dir)


@mcp.tool()
def research_suggest_experiments(
    history_path: Annotated[str, Field(description="One row per real completed trial with ID, inputs, measured objective and measured constraint.")],
    bounds_path: Annotated[str, Field(description="Declared numeric input bounds with units.")],
    objective_column: Annotated[str, Field(description="Measured objective to maximize, such as net_power_W.")],
    constraint_column: Annotated[str, Field(description="Measured outcome constrained above, such as stack_temperature_C.")],
    constraint_upper: Annotated[Real, Field(description="Explicit upper bound in the constraint column's measured units.")],
    n_candidates: Annotated[Integer, Field(description="Number of distinct pending candidates, 1–16.")] = 3,
    seed: Annotated[Integer, Field(description="Reproducibility seed.")] = 42,
    trial_id_column: Annotated[str, Field(description="Column of unique independently completed trial IDs.")] = "trial_id",
    output_dir: Annotated[str | None, Field(description="Fresh local recommendation output base.")] = None,
) -> dict:
    """Recommend the next measured experiments with constrained Optuna TPE.
    Observed history and bounds → pending candidates without invented outcomes or feasibility guarantees.
    """
    return design.suggest_experiments(history_path, bounds_path, objective_column, constraint_column,
                                      constraint_upper, n_candidates, seed, trial_id_column, output_dir)


@mcp.tool()
def research_search_literature(
    query: Annotated[str, Field(description="Public research search terms sent to Crossref, not private experiment files.")],
    limit: Annotated[Integer, Field(description="Maximum metadata records to retrieve, 1–50.")] = 15,
    year_from: Annotated[Integer, Field(description="First publication year.")] = 2018,
    year_to: Annotated[Integer, Field(description="Last publication year.")] = datetime.now(timezone.utc).year,
    output_dir: Annotated[str | None, Field(description="Fresh local evidence output base.")] = None,
) -> dict:
    """Retrieve DOI-linked public research metadata and available abstracts.
    Search terms → deduplicated evidence records with explicit access levels and raw-response provenance.
    """
    return evidence.search_literature(query, limit, year_from, year_to, output_dir)


@mcp.tool()
def research_prior_art_plan(
    topic: Annotated[str, Field(description="Explicit research topic for human-reviewed prior-art searching.")],
    technical_features: Annotated[list[str], Field(description="One to twelve technical features to examine individually.")],
    output_dir: Annotated[str | None, Field(description="Fresh local search-plan output base.")] = None,
) -> dict:
    """Prepare feature-specific patent search links and an evidence matrix.
    Topic and features → search queries for actual document review, with no novelty verdict.
    """
    return evidence.prior_art_plan(topic, technical_features, output_dir)


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
