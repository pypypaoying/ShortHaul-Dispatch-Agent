from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_existing_experiment_summary_has_multi_agent_schema():
    summary_path = ROOT / "outputs" / "experiment_summary.json"
    if not summary_path.exists():
        return

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["experiment"]["forecast_model"]
    assert summary["agent_trace"]
    assert summary["constraint_audit"]["status"] in {"pass", "fail"}
    assert "pure_cpsat_candidate" in summary["problem3"]
    assert "non_regression_baseline" in summary["problem3"]
