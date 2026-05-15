from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent import DispatchOrchestrator, ProblemConfig  # noqa: E402
from shorthaul_agent.models import Instance  # noqa: E402
from shorthaul_agent.web_ui import demo_payload, render_dashboard_html  # noqa: E402


def test_demo_payload_runs_with_heuristic_solver():
    payload = demo_payload()
    instance = Instance.from_dict(payload["instance"])
    config = ProblemConfig(prefer_cpsat=False).merged(payload["config_overrides"])

    result = DispatchOrchestrator(config).run(payload["request"], instance)

    assert result.solution.status == "FEASIBLE"
    assert result.solution.kpis["task_count"] > 0
    assert result.solution.kpis["assigned_task_count"] == result.solution.kpis["task_count"]


def test_dashboard_html_exposes_demo_and_schedule_controls():
    html = render_dashboard_html()

    assert "ShortHaul Dispatch Agent" in html
    assert 'fetch("/demo")' in html
    assert 'fetch("/schedule"' in html
    assert "vehicleCapacity" in html
    assert "Dispatch Gantt" in html
