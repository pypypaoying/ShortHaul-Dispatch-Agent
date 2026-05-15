from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent import DispatchOrchestrator, ProblemConfig  # noqa: E402
from shorthaul_agent.d_problem_package import write_upload_package  # noqa: E402
from shorthaul_agent.external_io import build_payload_from_csv_dir, load_instance_from_csv_dir, schema_payload  # noqa: E402
from shorthaul_agent.models import Instance  # noqa: E402
from shorthaul_agent.web_ui import demo_payload  # noqa: E402


def test_csv_template_builds_runnable_payload():
    payload = build_payload_from_csv_dir(
        ROOT / "examples" / "csv_template",
        "Schedule the external short-haul scenario.",
        instance_id="template-test",
        date="2024-12-16",
        prefer_cpsat=False,
    )

    instance = Instance.from_dict(payload["instance"])
    config = ProblemConfig(prefer_cpsat=False).merged(payload["config_overrides"])
    result = DispatchOrchestrator(config).run(payload["request"], instance)

    assert instance.id == "template-test"
    assert len(instance.routes) == 3
    assert len(instance.fleets) == 2
    assert config.milk_run_pairs == {("Stop-01", "Stop-02")}
    assert result.solution.status == "FEASIBLE"
    assert result.solution.kpis["assigned_task_count"] == result.solution.kpis["task_count"]


def test_schema_lists_required_external_files():
    schema = schema_payload()

    assert schema["required_files"] == ["fleets.csv", "routes.csv", "forecast.csv"]
    assert "routes.csv" in schema["csv_schemas"]
    assert schema["endpoints"]["multipart_upload_solve"] == "POST /schedule/upload"


def test_csv_minute_offsets_preserve_next_day_values():
    instance = load_instance_from_csv_dir(ROOT / "examples" / "csv_template")

    latest_by_route = {route.id: route.latest_dispatch_minute for route in instance.routes}

    assert latest_by_route["Site-A - Stop-01 - 0600"] == 1800
    assert latest_by_route["Site-B - Stop-03 - 1400"] == 2280


def test_upload_package_writer_round_trips_to_csv(tmp_path):
    payload = demo_payload()
    manifest = write_upload_package(payload, tmp_path)
    rebuilt = build_payload_from_csv_dir(
        tmp_path,
        payload["request"],
        instance_id=payload["instance"]["id"],
        date=payload["instance"]["date"],
        prefer_cpsat=False,
    )

    instance = Instance.from_dict(rebuilt["instance"])

    assert manifest["route_count"] == len(payload["instance"]["routes"])
    assert (tmp_path / "payload.json").exists()
    assert len(instance.routes) == len(payload["instance"]["routes"])
    assert len(instance.forecast) == len(payload["instance"]["forecast"])
