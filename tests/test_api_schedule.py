import sys
from contextlib import ExitStack
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from shorthaul_agent.api import create_app  # noqa: E402
from shorthaul_agent.external_io import write_workbook_template  # noqa: E402
from shorthaul_agent.web_ui import demo_payload  # noqa: E402


def test_schedule_endpoint_accepts_json_body():
    app = create_app()
    client = TestClient(app)
    payload = demo_payload()
    payload["prefer_cpsat"] = False

    response = client.post("/schedule", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["solution"]["status"] == "FEASIBLE"
    assert data["solution"]["kpis"]["assigned_task_count"] == data["solution"]["kpis"]["task_count"]


def test_dashboard_defaults_to_chinese_and_has_language_selector():
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "加载示例场景" in response.text
    assert 'id="language"' in response.text
    assert 'id="runUpload"' in response.text
    assert 'id="workbookFile"' in response.text
    assert 'id="ganttFilter"' in response.text
    assert "仅外部承运" in response.text
    assert "下载 Excel 模板" in response.text


def test_api_exposes_external_data_contract():
    app = create_app()
    client = TestClient(app)

    schema_response = client.get("/schema")
    template_response = client.get("/templates")

    assert schema_response.status_code == 200
    assert "routes.csv" in schema_response.json()["csv_schemas"]
    assert template_response.status_code == 200
    assert "fleets.csv" in template_response.json()

    contract_response = client.get("/contract")
    preview_response = client.get("/templates/view")
    workbook_response = client.get("/templates/workbook.xlsx")

    assert contract_response.status_code == 200
    assert "Excel 工作簿" in contract_response.text
    assert preview_response.status_code == 200
    assert "demand.sheet" in preview_response.text
    assert workbook_response.status_code == 200
    assert workbook_response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_schedule_upload_accepts_csv_files():
    pytest.importorskip("multipart")
    app = create_app()
    client = TestClient(app)
    csv_dir = ROOT / "examples" / "csv_template"

    with ExitStack() as stack:
        fleets = stack.enter_context((csv_dir / "fleets.csv").open("rb"))
        routes = stack.enter_context((csv_dir / "routes.csv").open("rb"))
        forecast = stack.enter_context((csv_dir / "forecast.csv").open("rb"))
        pairs = stack.enter_context((csv_dir / "milk_run_pairs.csv").open("rb"))
        response = client.post(
            "/schedule/upload",
            data={
                "request": "Schedule uploaded short-haul data.",
                "instance_id": "upload-test",
                "date": "2024-12-16",
                "prefer_cpsat": "false",
            },
            files={
                "fleets": ("fleets.csv", fleets, "text/csv"),
                "routes": ("routes.csv", routes, "text/csv"),
                "forecast": ("forecast.csv", forecast, "text/csv"),
                "milk_run_pairs": ("milk_run_pairs.csv", pairs, "text/csv"),
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["upload"]["source"] == "csv_upload"
    assert data["solution"]["status"] == "FEASIBLE"
    assert data["solution"]["kpis"]["assigned_task_count"] == data["solution"]["kpis"]["task_count"]


def test_schedule_upload_accepts_workbook(tmp_path):
    pytest.importorskip("multipart")
    app = create_app()
    client = TestClient(app)
    workbook = tmp_path / "shorthaul_dispatch_template.xlsx"
    write_workbook_template(workbook)

    with workbook.open("rb") as fp:
        response = client.post(
            "/schedule/upload",
            data={
                "request": "Schedule workbook short-haul data.",
                "instance_id": "workbook-upload-test",
                "date": "2024-12-16",
                "prefer_cpsat": "false",
            },
            files={
                "workbook": (
                    "shorthaul_dispatch_template.xlsx",
                    fp,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["upload"]["source"] == "workbook_upload"
    assert data["solution"]["status"] == "FEASIBLE"
    assert data["solution"]["kpis"]["assigned_task_count"] == data["solution"]["kpis"]["task_count"]
