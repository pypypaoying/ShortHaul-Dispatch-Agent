from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent.experiment import load_experiment_config  # noqa: E402
from shorthaul_agent.tracking import (  # noqa: E402
    default_wandb_run_name,
    flatten_experiment_metrics,
    log_experiment_to_wandb,
    safe_artifact_name,
)


def sample_summary():
    return {
        "experiment": {"name": "unit"},
        "data": {"routes": 2},
        "outputs": {"result_table_3_rows": 3},
        "problem2": {
            "task_count": 10,
            "container_task_count": 0,
            "kpis": {"total_cost": 100, "own_vehicle_turnover": 2.5, "external_task_count": 1},
        },
        "problem3": {
            "task_count": 11,
            "container_task_count": 2,
            "kpis": {"total_cost": 90, "own_vehicle_turnover": 2.7, "external_task_count": 0},
        },
        "constraint_audit": {"violation_count": 0, "warning_count": 1},
        "sensitivity": {"worst_on_time_rate": 0.95, "max_stranded_volume": 12},
        "agent_trace": [{"agent": "SolverAgent"}],
        "reproduction_status": {"level": "engineering_baseline_not_exact_reproduction"},
    }


def test_flatten_experiment_metrics_uses_wandb_friendly_names():
    metrics = flatten_experiment_metrics(sample_summary())

    assert metrics["problem2/total_cost"] == 100.0
    assert metrics["problem3/container_task_count"] == 2.0
    assert metrics["constraint_audit/warning_count"] == 1.0
    assert metrics["agent_trace/step_count"] == 1.0


def test_wandb_tracking_disabled_is_noop():
    config = load_experiment_config(ROOT / "experiments" / "d_problem_baseline.yaml")

    result = log_experiment_to_wandb(config, sample_summary(), ROOT)

    assert result == {"wandb_enabled": False, "status": "disabled"}


def test_wandb_config_file_loads_tracking_fields():
    config = load_experiment_config(ROOT / "experiments" / "d_problem_wandb.yaml")

    assert config.wandb_enabled is True
    assert config.wandb_project == "shorthaul-dispatch-agent"
    assert config.wandb_mode == "offline"
    assert config.wandb_tags == ["d-problem", "performance", "cpsat"]


def test_online_wandb_config_loads_online_mode():
    config = load_experiment_config(ROOT / "experiments" / "d_problem_wandb_online.yaml")

    assert config.wandb_enabled is True
    assert config.wandb_mode == "online"
    assert "online" in config.wandb_tags


def test_default_wandb_run_name_includes_output_leaf():
    config = load_experiment_config(ROOT / "experiments" / "d_problem_wandb_online.yaml")

    run_name = default_wandb_run_name(config, ROOT / "outputs_wandb_baseline" / "runs" / "heuristic_only")

    assert run_name == "d_problem_performance_wandb_online-heuristic_only"


def test_safe_artifact_name_removes_path_separators():
    assert safe_artifact_name("run/name with spaces") == "run-name-with-spaces"
