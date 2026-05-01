"""Optional experiment tracking integrations.

The core scheduler must stay runnable without online services. W&B support is
therefore intentionally lazy: the module imports ``wandb`` only when a config
explicitly enables tracking, and missing credentials or packages are reported
in the experiment summary instead of failing the optimization run.
"""

from __future__ import annotations

import math
from numbers import Number
from pathlib import Path
from typing import Any, Dict


def log_experiment_to_wandb(config: Any, summary: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    """Log an experiment summary to Weights & Biases when enabled."""

    if not getattr(config, "wandb_enabled", False):
        return {"wandb_enabled": False, "status": "disabled"}

    try:
        import wandb  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local optional package state
        return {
            "wandb_enabled": True,
            "status": "skipped",
            "reason": f"wandb import failed: {type(exc).__name__}: {exc}",
        }

    run = None
    try:
        run_name = getattr(config, "wandb_run_name", "") or default_wandb_run_name(config, output_dir)
        init_kwargs: Dict[str, Any] = {
            "project": getattr(config, "wandb_project", "shorthaul-dispatch-agent"),
            "name": run_name,
            "tags": list(getattr(config, "wandb_tags", []) or []),
            "config": wandb_config_from_summary(summary),
        }
        entity = getattr(config, "wandb_entity", "")
        mode = getattr(config, "wandb_mode", "")
        if entity:
            init_kwargs["entity"] = entity
        if mode:
            init_kwargs["mode"] = mode

        run = wandb.init(**init_kwargs)
        metrics = flatten_experiment_metrics(summary)
        if metrics:
            wandb.log(metrics)

        artifact_files = existing_artifact_files(output_dir)
        if artifact_files:
            artifact = wandb.Artifact(
                name=f"{safe_artifact_name(init_kwargs['name'])}-outputs",
                type="experiment-output",
                description="Short-haul dispatch experiment output files.",
            )
            for path in artifact_files:
                artifact.add_file(str(path))
            run.log_artifact(artifact)

        run_url = getattr(run, "url", None)
        return {
            "wandb_enabled": True,
            "status": "logged",
            "project": init_kwargs["project"],
            "run_name": init_kwargs["name"],
            "mode": mode or "default",
            "run_url": run_url,
            "logged_metrics": sorted(metrics),
            "artifact_file_count": len(artifact_files),
        }
    except Exception as exc:  # pragma: no cover - exercised only with live wandb failures
        return {
            "wandb_enabled": True,
            "status": "failed",
            "reason": f"{type(exc).__name__}: {exc}",
        }
    finally:
        if run is not None:
            run.finish()


def wandb_config_from_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    experiment = dict(summary.get("experiment", {}))
    return {
        "experiment": experiment,
        "data": summary.get("data", {}),
        "outputs": summary.get("outputs", {}),
        "reproduction_status": summary.get("reproduction_status", {}).get("level"),
    }


def flatten_experiment_metrics(summary: Dict[str, Any]) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    for problem_name in ("problem2", "problem3"):
        problem = summary.get(problem_name, {})
        kpis = problem.get("kpis", {})
        for metric_name in (
            "total_cost",
            "own_vehicle_turnover",
            "avg_packages_per_vehicle",
            "external_task_count",
            "unused_capacity",
        ):
            value = kpis.get(metric_name)
            if is_number(value):
                metrics[f"{problem_name}/{metric_name}"] = float(value)
        task_count = problem.get("task_count")
        if is_number(task_count):
            metrics[f"{problem_name}/task_count"] = float(task_count)
        container_task_count = problem.get("container_task_count")
        if is_number(container_task_count):
            metrics[f"{problem_name}/container_task_count"] = float(container_task_count)

    audit = summary.get("constraint_audit", {})
    for metric_name in ("violation_count", "warning_count"):
        value = audit.get(metric_name)
        if is_number(value):
            metrics[f"constraint_audit/{metric_name}"] = float(value)

    sensitivity = summary.get("sensitivity", {})
    for metric_name in (
        "baseline_loaded_volume",
        "baseline_stranded_volume",
        "baseline_on_time_rate",
        "worst_on_time_rate",
        "worst_stranded_volume",
        "max_stranded_volume",
    ):
        value = sensitivity.get(metric_name)
        if is_number(value):
            metrics[f"sensitivity/{metric_name}"] = float(value)

    trace = summary.get("agent_trace", [])
    if isinstance(trace, list):
        metrics["agent_trace/step_count"] = float(len(trace))
    return metrics


def existing_artifact_files(output_dir: Path) -> list[Path]:
    filenames = [
        "result_table_1.xlsx",
        "result_table_2.xlsx",
        "result_table_3.xlsx",
        "result_table_4.xlsx",
        "constraint_audit.json",
        "constraint_audit.md",
        "sensitivity_analysis.csv",
        "sensitivity_analysis.xlsx",
        "focus_routes_report.md",
        "gantt_problem2.png",
        "gantt_problem3.png",
        "sensitivity_on_time.png",
        "experiment_summary.json",
        "experiment_report.md",
    ]
    return [output_dir / filename for filename in filenames if (output_dir / filename).exists()]


def default_wandb_run_name(config: Any, output_dir: Path) -> str:
    base_name = getattr(config, "name", "") or "shorthaul-experiment"
    suffix = output_dir.name
    if suffix and suffix not in {base_name, "outputs"}:
        return f"{base_name}-{suffix}"
    return base_name


def safe_artifact_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in value)
    return cleaned.strip("-") or "shorthaul-experiment"


def is_number(value: Any) -> bool:
    return isinstance(value, Number) and not isinstance(value, bool) and math.isfinite(float(value))
