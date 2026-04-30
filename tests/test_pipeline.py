from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent import DispatchOrchestrator, ProblemConfig
from shorthaul_agent.io import load_instance


def test_sample_pipeline_is_feasible():
    instance = load_instance(ROOT / "examples" / "sample_instance.json")
    request_text = (ROOT / "examples" / "sample_request.txt").read_text(encoding="utf-8")
    result = DispatchOrchestrator(ProblemConfig(prefer_cpsat=False)).run(request_text, instance)

    assert result.solution.status == "FEASIBLE"
    assert result.solution.kpis["assigned_task_count"] == result.solution.kpis["task_count"]
    assert result.solution.kpis["external_task_count"] == 0
    assert result.solution.kpis["fill_rate"] > 0.7
