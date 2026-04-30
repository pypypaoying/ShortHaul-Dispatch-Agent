from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent.baseline_comparison import (  # noqa: E402
    add_delta_columns,
    best_by_problem,
    dataframe_to_markdown,
    paper_reference_rows,
    render_comparison_report,
    scenario_delta,
)


def test_paper_reference_rows_include_expected_benchmarks():
    rows = paper_reference_rows()
    assert rows[0]["problem"] == "problem2"
    assert rows[0]["total_cost"] == 56776.0
    assert rows[1]["problem"] == "problem3"
    assert rows[1]["own_vehicle_turnover"] == 2.62


def test_add_delta_columns_uses_problem_specific_paper_baselines():
    frame = pd.DataFrame(
        [
            {"scenario": "x", "problem": "problem2", "total_cost": 57000, "own_vehicle_turnover": 2.50},
            {"scenario": "y", "problem": "problem3", "total_cost": 47200, "own_vehicle_turnover": 2.60},
        ]
    )
    result = add_delta_columns(frame)
    assert result.loc[0, "cost_gap_vs_paper"] == 224.0
    assert round(result.loc[1, "turnover_gap_vs_paper"], 2) == -0.02


def test_best_by_problem_ignores_paper_reference_rows():
    frame = pd.DataFrame(
        [
            {"scenario": "Paper Reference", "problem": "problem2", "total_cost": 1, "solver": "paper", "own_vehicle_turnover": 1},
            {"scenario": "Current", "problem": "problem2", "total_cost": 10, "solver": "cpsat", "own_vehicle_turnover": 2},
            {"scenario": "Heuristic", "problem": "problem2", "total_cost": 8, "solver": "heuristic", "own_vehicle_turnover": 3},
        ]
    )
    best = best_by_problem(frame)
    assert best["problem2"]["scenario"] == "Heuristic"
    assert best["problem2"]["total_cost"] == 8.0


def test_scenario_delta_reports_current_minus_comparator():
    frame = pd.DataFrame(
        [
            {
                "scenario": "Current Multi-Agent",
                "problem": "problem2",
                "total_cost": 8,
                "own_vehicle_turnover": 3,
                "external_task_count": 2,
            },
            {
                "scenario": "Legacy Pipeline",
                "problem": "problem2",
                "total_cost": 10,
                "own_vehicle_turnover": 2,
                "external_task_count": 4,
            },
        ]
    )
    delta = scenario_delta(frame, "Current Multi-Agent", "Legacy Pipeline")
    assert delta["problem2"]["cost_delta"] == -2.0
    assert delta["problem2"]["turnover_delta"] == 1.0
    assert delta["problem2"]["external_task_delta"] == -2.0


def test_markdown_report_does_not_require_optional_tabulate():
    comparison = pd.DataFrame(
        [
            {
                "scenario": "Current",
                "problem": "problem2",
                "solver": "cpsat",
                "status": "FEASIBLE",
                "total_cost": 10,
                "own_vehicle_turnover": 2,
            }
        ]
    )
    summary = {
        "best_by_problem": {"problem2": {"scenario": "Current", "solver": "cpsat", "total_cost": 10, "own_vehicle_turnover": 2}},
        "multi_agent_assessment": {"current_agent_trace_steps": 12, "current_constraint_status": "pass"},
    }
    table = dataframe_to_markdown(comparison)
    report = render_comparison_report(summary, comparison)
    assert "| scenario | problem |" in table
    assert "Baseline Comparison Report" in report
    assert "Current multi-agent trace steps: 12" in report
