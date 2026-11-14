"""Measurement profiling and replicate-aware, prespecified comparisons."""

from pathlib import Path
from numbers import Real
import warnings as python_warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from .common import finish_run, input_info, load_table, new_run, write_json


def numeric_column(frame, name, required=True):
    """Parse declared numeric measurements without imputing missing values."""
    if name not in frame:
        raise ValueError(f"Missing required column: {name}")
    values = frame[name]
    if values.map(lambda value: isinstance(value, (bool, np.bool_))).any():
        raise ValueError(f"{name} must contain numeric measurements, not booleans.")
    try:
        parsed = pd.to_numeric(values, errors="raise").astype(float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} contains a nonnumeric measurement.") from exc
    if np.isinf(parsed.to_numpy()).any() or (required and parsed.isna().any()):
        raise ValueError(f"{name} must contain finite {'complete ' if required else ''}measurements.")
    return parsed


def _add_derived(frame, name, values):
    if name in frame:
        existing = numeric_column(frame, name, required=False)
        if not np.allclose(existing, values, rtol=1e-9, atol=1e-12, equal_nan=True):
            raise ValueError(f"Reported {name} disagrees with its declared inputs; rename the reported column before deriving it.")
    frame[name] = values


def derive_measurements(frame):
    """Create an explicit derived copy; no source file or group labels change."""
    derived = frame.copy(deep=True)
    current = numeric_column(derived, "current_A")
    voltage = numeric_column(derived, "stack_voltage_V")
    if (current < 0).any():
        raise ValueError("Fuel-cell current_A must be nonnegative; reverse-current data need a separate declared analysis.")
    derived["current_A"], derived["stack_voltage_V"] = current, voltage
    _add_derived(derived, "gross_power_W", current * voltage)
    notes = []
    if (voltage < 0).any():
        notes.append("Negative measured stack voltages are retained; inspect reversal/sensor conditions before interpreting performance.")
    present = {}
    for name in ("fan_power_W", "other_aux_power_W"):
        if name in derived:
            values = numeric_column(derived, name, required=False)
            if (values.dropna() < 0).any():
                raise ValueError(f"{name} represents consumed power and must be nonnegative.")
            derived[name] = values
            present[name] = values
            if values.isna().any():
                notes.append(f"Missing {name} values remain missing; no zero power was imputed.")
    if "fan_power_W" in present:
        _add_derived(derived, "gross_minus_fan_power_W", derived["gross_power_W"] - present["fan_power_W"])
        if "other_aux_power_W" in present:
            _add_derived(derived, "net_power_W", derived["gross_minus_fan_power_W"] - present["other_aux_power_W"])
            boundary = "gross_minus_measured_fan_and_declared_other_auxiliaries"
        else:
            if "net_power_W" in derived:
                raise ValueError("net_power_W needs measured fan_power_W and other_aux_power_W; rename any separately reported net metric explicitly.")
            boundary = "gross_minus_measured_fan_only"
            notes.append("Gross-minus-fan power is not full system net power: other auxiliary power was not supplied.")
    else:
        if "net_power_W" in derived or "gross_minus_fan_power_W" in derived:
            raise ValueError("Derived net/fan-subtracted columns require their measured auxiliary-power inputs.")
        boundary = "gross_stack_electrical_power_only"
        notes.append("Fan consumption was not supplied; no net-power result is claimed.")
    if "cell_count" in derived:
        count = numeric_column(derived, "cell_count", required=False)
        known = count.dropna()
        if (known <= 0).any() or not np.equal(known, np.floor(known)).all():
            raise ValueError("cell_count must contain positive integers when supplied.")
        _add_derived(derived, "cell_voltage_V", voltage / count)
    if "active_area_cm2" in derived:
        area = numeric_column(derived, "active_area_cm2", required=False)
        if (area.dropna() <= 0).any():
            raise ValueError("active_area_cm2 must be positive when supplied.")
        _add_derived(derived, "current_density_A_cm2", current / area)
    kind = "user_supplied_unverified"
    if "data_kind" in derived:
        kinds = derived["data_kind"].dropna().astype(str).unique().tolist()
        if kinds:
            kind = "; ".join(kinds)
    return derived, boundary, notes, kind


def _save_figure(fig, run, stem):
    fig.tight_layout()
    fig.savefig(Path(run) / f"{stem}.png", dpi=300)
    fig.savefig(Path(run) / f"{stem}.svg")
    plt.close(fig)


def analyze_measurements(data_path, output_dir=None, sheet_name=0):
    frame = load_table(data_path, sheet_name=sheet_name, string_columns=["replicate_id", "condition", "run_id", "sample_id", "trial_id"])
    data, boundary, notes, kind = derive_measurements(frame)
    quality = {
        "rows_read": int(len(frame)), "columns_read": int(len(frame.columns)),
        "missing_values": {str(name): int(frame[name].isna().sum()) for name in frame},
        "duplicate_complete_rows": int(frame.duplicated().sum()),
        "negative_stack_voltage_rows": int((data["stack_voltage_V"] < 0).sum()),
        "source_rows_removed": 0, "imputed_values": 0, "data_kind": kind,
    }
    if "time_s" in frame:
        time = numeric_column(frame, "time_s", required=False)
        quality["time_order_screen"] = "Nonmonotonic time may represent multiple runs; no rows were reordered."
        quality["negative_time_steps_in_input_order"] = int((time.diff() < 0).sum())
    run = new_run("measurements", {"source": input_info(data_path), "sheet_name": sheet_name}, output_dir)
    data.to_csv(run / "derived-measurements.csv", index=False)
    write_json(run / "quality.json", quality)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].scatter(data["current_A"], data["stack_voltage_V"], s=15, color="#207178", rasterized=True)
    axes[0].set(xlabel="Current / A", ylabel="Measured stack voltage / V")
    axes[1].scatter(data["current_A"], data["gross_power_W"], s=15, label="Gross stack", color="#207178", rasterized=True)
    if "gross_minus_fan_power_W" in data:
        axes[1].scatter(data["current_A"], data["gross_minus_fan_power_W"], s=13, label="Gross minus measured fan", color="#c47b29", rasterized=True)
    if "net_power_W" in data:
        axes[1].scatter(data["current_A"], data["net_power_W"], s=12, label="Gross minus declared auxiliaries", color="#5b548a", rasterized=True)
    axes[1].set(xlabel="Current / A", ylabel="Electrical power / W")
    axes[1].legend(fontsize=8)
    _save_figure(fig, run, "measurement-curves")
    summary = {"row_count": len(data), "data_kind": kind, "power_boundary": boundary,
               "max_observed_gross_power_W": float(data["gross_power_W"].max()),
               "source_rows_removed": 0, "imputed_values": 0}
    for metric in ("gross_minus_fan_power_W", "net_power_W"):
        if metric in data:
            known = data[metric].dropna()
            summary[f"valid_{metric}_rows"] = int(len(known))
            summary[f"max_observed_{metric}"] = float(known.max()) if len(known) else None
    return finish_run(run, summary, {"name": "Measured-data profile and explicit electrical-power accounting", "numeric_source": "pandas/NumPy; P_gross=I*V; subtraction of supplied consumed powers only"}, notes)


def compare_conditions(data_path, metric, group_a, group_b, design, target_current_A,
                       current_tolerance_A=0.1, condition_column="condition",
                       replicate_column="replicate_id", output_dir=None, sheet_name=0):
    if design not in ("paired", "independent"):
        raise ValueError("design must be explicitly paired or independent.")
    if group_a == group_b:
        raise ValueError("Select two distinct conditions.")
    if isinstance(target_current_A, (bool, np.bool_)) or not isinstance(target_current_A, Real) or not np.isfinite(target_current_A) or target_current_A < 0:
        raise ValueError("target_current_A must be finite and nonnegative.")
    if isinstance(current_tolerance_A, (bool, np.bool_)) or not isinstance(current_tolerance_A, Real) or not np.isfinite(current_tolerance_A) or current_tolerance_A < 0:
        raise ValueError("current_tolerance_A must be finite and nonnegative.")
    frame = load_table(data_path, sheet_name=sheet_name, string_columns=[condition_column, replicate_column])
    data, boundary, notes, kind = derive_measurements(frame)
    for name in (condition_column, replicate_column):
        if name not in data or data[name].isna().any() or data[name].astype(str).str.strip().eq("").any():
            raise ValueError(f"Complete actual identifiers are required in {name}.")
    data[condition_column] = data[condition_column].astype(str)
    data[replicate_column] = data[replicate_column].astype(str)
    selected = data.loc[data[condition_column].isin([str(group_a), str(group_b)]) &
                        (data["current_A"] - target_current_A).abs().le(current_tolerance_A)].copy()
    if selected.empty:
        raise ValueError("No observations match both conditions and the specified current band.")
    selected[metric] = numeric_column(selected, metric)
    per_rep = selected.groupby([condition_column, replicate_column], sort=True).agg(
        metric_mean=(metric, "mean"), raw_row_count=(metric, "size"),
        current_min_A=("current_A", "min"), current_max_A=("current_A", "max")).reset_index()
    a = per_rep.loc[per_rep[condition_column] == str(group_a)].set_index(replicate_column)["metric_mean"]
    b = per_rep.loc[per_rep[condition_column] == str(group_b)].set_index(replicate_column)["metric_mean"]
    if len(a) < 2 or len(b) < 2:
        raise ValueError("At least two actual replicates in each condition are required; repeated rows are not replicates.")
    if design == "paired":
        if set(a.index) != set(b.index):
            raise ValueError("Paired conditions have unmatched replicate IDs; supply aligned actual pairs.")
        a = a.sort_index()
        b = b.reindex(a.index)
    av, bv = a.to_numpy(dtype=float), b.to_numpy(dtype=float)
    effect = float(np.mean(bv) - np.mean(av))
    def numerically_constant(values_):
        scale = max(1.0, float(np.max(np.abs(values_))))
        return bool(np.ptp(values_) <= np.finfo(float).eps * scale * 16)
    degenerate = numerically_constant(bv-av) if design == "paired" else numerically_constant(av) and numerically_constant(bv)
    test = None
    if not degenerate:
        with python_warnings.catch_warnings():
            python_warnings.simplefilter("ignore", RuntimeWarning)
            test = stats.ttest_rel(bv, av) if design == "paired" else stats.ttest_ind(bv, av, equal_var=False)
        interval = test.confidence_interval(confidence_level=0.95)
        numbers = [test.statistic, test.pvalue, test.df, interval.low, interval.high]
        if not np.isfinite(numbers).all():
            degenerate = True
            test = None
    inference = {"status": "degenerate_no_inferential_claim" if degenerate else "computed_under_declared_design",
                 "statistic": float(test.statistic) if test is not None else None,
                 "degrees_of_freedom": float(test.df) if test is not None else None,
                 "p_value_two_sided": float(test.pvalue) if test is not None else None,
                 "confidence_level": 0.95,
                 "mean_difference_ci": [float(interval.low), float(interval.high)] if test is not None else None}
    if degenerate:
        notes.append("The replicate contrast has zero variance or undefined inference; effect is retained, p value and confidence interval are not manufactured.")
    notes.append("Replicate independence and matched operating conditions come from experimental design; this computation cannot establish them.")
    ranges = {str(group): {"min_A": float(rows["current_A"].min()), "max_A": float(rows["current_A"].max())}
              for group, rows in selected.groupby(condition_column, sort=True)}
    summary = {"metric": metric, "contrast": "group_b_minus_group_a", "group_a": str(group_a), "group_b": str(group_b),
               "design": design, "n_replicates_a": len(a), "n_replicates_b": len(b),
               "mean_a": float(np.mean(av)), "mean_b": float(np.mean(bv)), "mean_difference": effect,
               "inference": inference, "actual_current_ranges": ranges,
               "target_current_A": float(target_current_A), "current_tolerance_A": float(current_tolerance_A),
               "data_kind": kind, "power_boundary": boundary}
    run = new_run("condition-comparison", {"source": input_info(data_path), "sheet_name": sheet_name,
                  "metric": metric, "group_a": group_a, "group_b": group_b, "design": design,
                  "target_current_A": float(target_current_A), "current_tolerance_A": float(current_tolerance_A),
                  "condition_column": condition_column, "replicate_column": replicate_column}, output_dir)
    per_rep.to_csv(run / "per-replicate.csv", index=False)
    selected.to_csv(run / "matched-observations.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for x, values_, label in [(0, av, str(group_a)), (1, bv, str(group_b))]:
        axes[0].scatter(np.full(len(values_), x), values_, s=25, label=label)
        axes[0].plot([x-.15, x+.15], [np.mean(values_)]*2, color="black", linewidth=2)
    if design == "paired":
        for va, vb in zip(av, bv):
            axes[0].plot([0, 1], [va, vb], color="#999999", alpha=.35, linewidth=.8)
    axes[0].set(xticks=[0, 1], xticklabels=[str(group_a), str(group_b)], ylabel=metric)
    axes[1].scatter([0], [effect], color="#207178")
    if inference["mean_difference_ci"] is not None:
        lo, hi = inference["mean_difference_ci"]
        axes[1].vlines(0, lo, hi, color="#207178", linewidth=2)
    axes[1].axhline(0, color="grey", linestyle="--", linewidth=.8)
    axes[1].set(xticks=[0], xticklabels=["B minus A"], ylabel=f"Mean difference / {metric}")
    _save_figure(fig, run, "replicate-comparison")
    return finish_run(run, summary, {"name": "Prespecified replicate-level paired t-test" if design == "paired" else "Prespecified replicate-level Welch t-test",
                                    "source": "scipy.stats.ttest_rel" if design == "paired" else "scipy.stats.ttest_ind(equal_var=False)",
                                    "multiple_testing": "One requested contrast; no automatic multiplicity adjustment or outcome-driven test selection."}, notes)
