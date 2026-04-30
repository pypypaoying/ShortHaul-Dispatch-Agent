"""Run a minimal end-to-end pipeline check without external services."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent import DispatchOrchestrator, ProblemConfig  # noqa: E402
from shorthaul_agent.io import load_instance  # noqa: E402


def main() -> None:
    instance = load_instance(ROOT / "examples" / "sample_instance.json")
    request_text = (ROOT / "examples" / "sample_request.txt").read_text(encoding="utf-8")
    result = DispatchOrchestrator(ProblemConfig(prefer_cpsat=False)).run(request_text, instance)
    assert result.solution.status in {"FEASIBLE", "OPTIMAL"}
    assert result.solution.kpis["assigned_task_count"] == result.solution.kpis["task_count"]
    assert result.solution.kpis["total_cost"] > 0
    print(result.explanation)


if __name__ == "__main__":
    main()
