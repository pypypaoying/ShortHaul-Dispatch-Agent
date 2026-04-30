"""Baseline comparison experiments for the D-problem pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from shorthaul_agent.experiment import PAPER_BASELINES, run_experiment


def compare_baselines(
    data_dir: Path,
    output_dir: Path,
    config_path: Optional[Path] = None,
    legacy_summary: Optional[Path] = None,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    runs_dir = output_dir / "runs"
    current_dir = runs_dir / "current_multi_agent"
    heuristic_dir = runs_dir / "heuristic_only"

    current_summary = run_experiment(data_dir, current_dir, prefer_cpsat=True, config_path=config_path)
    heuristic_summary = run_experiment(data_dir, heuristic_dir, prefer_cpsat=False, config_path=config_path)

    rows = []
    rows.extend(paper_reference_rows())
    rows.extend(summary_to_rows("Current Multi-Agent", current_summary))
    rows.extend(summary_to_rows("Heuristic Only", heuristic_summary))
    rows.extend(problem3_candidate_rows("Pure CP-SAT P3", current_summary["problem3"].get("pure_cpsat_candidate", {})))
    rows.extend(problem3_candidate_rows("CP-SAT + Repair Baseline", current_summary["problem3"].get("non_regression_baseline", {})))

    if legacy_summary and legacy_summary.exists():
        legacy = json.loads(legacy_summary.read_text(encoding="utf-8"))
        rows.extend(summary_to_rows("Legacy Pipeline", legacy))

    comparison = add_delta_columns(pd.DataFrame(rows))
    comparison.to_excel(output_dir / "comparison_table.xlsx", index=False)
    comparison.to_csv(output_dir / "comparison_table.csv", index=False, encoding="utf-8-sig")

    summary = {
        "runs": {
            "current_multi_agent": str(current_dir),
            "heuristic_only": str(heuristic_dir),
            "legacy_summary": str(legacy_summary) if legacy_summary else None,
        },
        "table_rows": len(comparison),
        "best_by_problem": best_by_problem(comparison),
        "current_vs_legacy": scenario_delta(comparison, "Current Multi-Agent", "Legacy Pipeline"),
        "current_vs_heuristic": scenario_delta(comparison, "Current Multi-Agent", "Heuristic Only"),
        "multi_agent_assessment": assess_multi_agent(current_summary, heuristic_summary),
    }
    (output_dir / "comparison_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "comparison_report.md").write_text(render_comparison_report(summary, comparison), encoding="utf-8")
    write_plots(output_dir, comparison, current_summary, heuristic_summary)
    return summary


def paper_reference_rows() -> list:
    return [
        {
            "scenario": "Paper Reference",
            "problem": "problem2",
            "solver": "paper",
            "status": "reference",
            "total_cost": PAPER_BASELINES["problem2"]["total_cost"],
            "own_vehicle_turnover": PAPER_BASELINES["problem2"]["own_vehicle_turnover"],
            "avg_packages_per_vehicle": None,
            "external_task_count": None,
            "container_task_count": 0,
            "constraint_status": "n/a",
            "agent_trace_steps": 0,
            "worst_on_time_rate": None,
            "max_stranded_volume": None,
        },
        {
            "scenario": "Paper Reference",
            "problem": "problem3",
            "solver": "paper",
            "status": "reference",
            "total_cost": PAPER_BASELINES["problem3"]["total_cost"],
            "own_vehicle_turnover": PAPER_BASELINES["problem3"]["own_vehicle_turnover"],
            "avg_packages_per_vehicle": None,
            "external_task_count": None,
            "container_task_count": None,
            "constraint_status": "n/a",
            "agent_trace_steps": 0,
            "worst_on_time_rate": None,
            "max_stranded_volume": None,
        },
    ]


def summary_to_rows(scenario: str, summary: Dict[str, Any]) -> list:
    rows = []
    for problem in ("problem2", "problem3"):
        item = summary[problem]
        kpis = item.get("kpis", {})
        sensitivity = summary.get("sensitivity", {})
        rows.append(
            {
                "scenario": scenario,
                "problem": problem,
                "solver": item.get("solver"),
                "status": item.get("status"),
                "total_cost": kpis.get("total_cost"),
                "own_vehicle_turnover": kpis.get("own_vehicle_turnover"),
                "avg_packages_per_vehicle": kpis.get("avg_packages_per_vehicle"),
                "external_task_count": kpis.get("external_task_count"),
                "container_task_count": item.get("container_task_count", 0),
                "constraint_status": summary.get("constraint_audit", {}).get("status", "unknown"),
                "agent_trace_steps": len(summary.get("agent_trace", [])),
                "worst_on_time_rate": sensitivity.get("worst_on_time_rate"),
                "max_stranded_volume": sensitivity.get("max_stranded_volume"),
            }
        )
    return rows


def problem3_candidate_rows(scenario: str, candidate: Dict[str, Any]) -> list:
    if not candidate:
        return []
    return [
        {
            "scenario": scenario,
            "problem": "problem3",
            "solver": candidate.get("solver"),
            "status": candidate.get("status"),
            "total_cost": candidate.get("total_cost"),
            "own_vehicle_turnover": candidate.get("own_vehicle_turnover"),
            "avg_packages_per_vehicle": None,
            "external_task_count": None,
            "container_task_count": candidate.get("container_task_count"),
            "constraint_status": "candidate",
            "agent_trace_steps": None,
            "worst_on_time_rate": None,
            "max_stranded_volume": None,
        }
    ]


def add_delta_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    baselines = {
        ("problem2", "cost"): PAPER_BASELINES["problem2"]["total_cost"],
        ("problem3", "cost"): PAPER_BASELINES["problem3"]["total_cost"],
        ("problem2", "turnover"): PAPER_BASELINES["problem2"]["own_vehicle_turnover"],
        ("problem3", "turnover"): PAPER_BASELINES["problem3"]["own_vehicle_turnover"],
    }
    frame["cost_gap_vs_paper"] = [
        row.total_cost - baselines[(row.problem, "cost")]
        if pd.notna(row.total_cost) and row.problem in {"problem2", "problem3"}
        else None
        for row in frame.itertuples(index=False)
    ]
    frame["turnover_gap_vs_paper"] = [
        row.own_vehicle_turnover - baselines[(row.problem, "turnover")]
        if pd.notna(row.own_vehicle_turnover) and row.problem in {"problem2", "problem3"}
        else None
        for row in frame.itertuples(index=False)
    ]
    return frame


def best_by_problem(frame: pd.DataFrame) -> Dict[str, Any]:
    result = {}
    for problem in ("problem2", "problem3"):
        subset = frame[(frame["problem"] == problem) & (frame["scenario"] != "Paper Reference") & frame["total_cost"].notna()]
        if subset.empty:
            continue
        best = subset.sort_values("total_cost").iloc[0]
        result[problem] = {
            "scenario": best["scenario"],
            "solver": best["solver"],
            "total_cost": float(best["total_cost"]),
            "own_vehicle_turnover": float(best["own_vehicle_turnover"]) if pd.notna(best["own_vehicle_turnover"]) else None,
        }
    return result


def scenario_delta(frame: pd.DataFrame, left_scenario: str, right_scenario: str) -> Dict[str, Any]:
    result = {}
    for problem in ("problem2", "problem3"):
        left = frame[(frame["scenario"] == left_scenario) & (frame["problem"] == problem)]
        right = frame[(frame["scenario"] == right_scenario) & (frame["problem"] == problem)]
        if left.empty or right.empty:
            continue
        left_row = left.iloc[0]
        right_row = right.iloc[0]
        result[problem] = {
            "cost_delta": numeric_delta(left_row.get("total_cost"), right_row.get("total_cost")),
            "turnover_delta": numeric_delta(left_row.get("own_vehicle_turnover"), right_row.get("own_vehicle_turnover")),
            "external_task_delta": numeric_delta(left_row.get("external_task_count"), right_row.get("external_task_count")),
        }
    return result


def numeric_delta(left: Any, right: Any) -> Optional[float]:
    if pd.isna(left) or pd.isna(right):
        return None
    return float(left) - float(right)


def assess_multi_agent(current: Dict[str, Any], heuristic: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "current_agent_trace_steps": len(current.get("agent_trace", [])),
        "current_constraint_status": current.get("constraint_audit", {}).get("status"),
        "heuristic_constraint_status": heuristic.get("constraint_audit", {}).get("status"),
        "current_outputs": current.get("outputs", {}),
        "heuristic_outputs": heuristic.get("outputs", {}),
        "assessment": "Multi-agent architecture improves traceability and auditability; optimization quality remains benchmarked separately.",
    }


def format_best_row(row: Dict[str, Any]) -> str:
    if not row:
        return "n/a"
    return (
        f"{row.get('scenario')} using {row.get('solver')} "
        f"(cost={row.get('total_cost')}, turnover={row.get('own_vehicle_turnover')})"
    )


def value_to_markdown(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def dataframe_to_markdown(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in frame.itertuples(index=False):
        lines.append("| " + " | ".join(value_to_markdown(value) for value in row) + " |")
    return "\n".join(lines)


def render_comparison_report(summary: Dict[str, Any], comparison: pd.DataFrame) -> str:
    best = summary["best_by_problem"]
    assessment = summary["multi_agent_assessment"]
    lines = [
        "# Baseline Comparison Report",
        "",
        "## Key Findings",
        f"- Best problem 2 run: {format_best_row(best.get('problem2', {}))}",
        f"- Best problem 3 run: {format_best_row(best.get('problem3', {}))}",
        f"- Current multi-agent trace steps: {assessment['current_agent_trace_steps']}",
        f"- Current constraint audit status: {assessment['current_constraint_status']}",
        f"- Current vs legacy delta: {summary.get('current_vs_legacy', {})}",
        f"- Current vs heuristic delta: {summary.get('current_vs_heuristic', {})}",
        "",
        "## KPI Table",
        dataframe_to_markdown(comparison),
        "",
        "## Interpretation",
        "- Paper Reference rows are the benchmark values cited in the original paper.",
        "- Legacy Pipeline is optional and is filled only when an old experiment summary is supplied.",
        "- The multi-agent score is not treated as a cost optimizer by itself; it is measured through traceability, auditability, repair metadata, and the same solver KPIs.",
    ]
    return "\n".join(lines)


def write_plots(output_dir: Path, comparison: pd.DataFrame, current: Dict[str, Any], heuristic: Dict[str, Any]) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return

    subset = comparison[(comparison["scenario"] != "Paper Reference") & comparison["total_cost"].notna()].copy()
    if not subset.empty:
        labels = subset["scenario"] + "\n" + subset["problem"]
        fig, ax1 = plt.subplots(figsize=(12, 6))
        ax1.bar(labels, subset["total_cost"], color="#2563EB", alpha=0.75)
        ax1.set_ylabel("Total cost")
        ax1.tick_params(axis="x", rotation=35)
        ax2 = ax1.twinx()
        ax2.plot(labels, subset["own_vehicle_turnover"], color="#DC2626", marker="o")
        ax2.set_ylabel("Own vehicle turnover")
        ax1.set_title("Cost and turnover comparison")
        fig.tight_layout()
        fig.savefig(output_dir / "cost_turnover_comparison.png", dpi=160)
        plt.close(fig)

    robustness_rows = []
    for name, run_summary in [("Current Multi-Agent", current), ("Heuristic Only", heuristic)]:
        sensitivity = run_summary.get("sensitivity", {})
        if sensitivity:
            robustness_rows.append(
                {
                    "scenario": name,
                    "worst_on_time_rate": sensitivity.get("worst_on_time_rate"),
                    "max_stranded_volume": sensitivity.get("max_stranded_volume"),
                }
            )
    robust = pd.DataFrame(robustness_rows)
    if not robust.empty:
        fig, ax1 = plt.subplots(figsize=(8, 5))
        ax1.bar(robust["scenario"], robust["max_stranded_volume"], color="#F97316", alpha=0.65)
        ax1.set_ylabel("Max stranded volume")
        ax2 = ax1.twinx()
        ax2.plot(robust["scenario"], robust["worst_on_time_rate"], color="#16A34A", marker="o")
        ax2.set_ylabel("Worst on-time rate")
        ax1.set_title("Robustness comparison")
        fig.tight_layout()
        fig.savefig(output_dir / "robustness_comparison.png", dpi=160)
        plt.close(fig)
