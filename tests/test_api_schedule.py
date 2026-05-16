import json
import sys
import time
import zipfile
from contextlib import ExitStack
from io import BytesIO
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


def test_favicon_request_does_not_log_404():
    app = create_app()
    client = TestClient(app)

    response = client.get("/favicon.ico")

    assert response.status_code == 204


def test_schedule_export_returns_selected_zip_files():
    app = create_app()
    client = TestClient(app)
    payload = demo_payload()
    payload["prefer_cpsat"] = False
    schedule_response = client.post("/schedule", json=payload)
    assert schedule_response.status_code == 200

    response = client.post(
        "/schedule/export",
        json={
            "result": schedule_response.json(),
            "files": ["solution_json", "assignments_csv", "kpis_json"],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == ["assignments.csv", "kpis.json", "solution.json"]
        assignments_bytes = archive.read("assignments.csv")
        assert assignments_bytes.startswith(b"\xef\xbb\xbf")
        assert "task_id" in assignments_bytes.decode("utf-8-sig")


def test_dashboard_defaults_to_chinese_and_has_language_selector():
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "智能接入并运行" in response.text
    assert "数据接入 Agent LLM 接入配置" in response.text
    assert 'id="agentProvider"' in response.text
    assert "第三方兼容 / 自定义" in response.text
    assert "最小输入格式" not in response.text
    assert "示例场景与高级编辑" not in response.text
    assert 'id="language"' in response.text
    assert 'id="runUpload"' in response.text
    assert 'id="dataFile"' in response.text
    assert 'id="dataFile" type="file" multiple' in response.text
    assert 'id="ganttFilter"' in response.text
    assert "仅外部承运" in response.text
    assert 'data-stage="router"' in response.text
    assert 'id="exportSelected"' in response.text
    assert 'value="deepseek"' in response.text


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


def test_schedule_upload_job_reports_progress_and_result():
    pytest.importorskip("multipart")
    app = create_app()
    client = TestClient(app)
    payload = demo_payload()
    payload["prefer_cpsat"] = False

    start_response = client.post(
        "/schedule/upload/jobs",
        data={
            "request": "Schedule uploaded payload.",
            "prefer_cpsat": "false",
        },
        files={
            "payload_json": (
                "payload.json",
                BytesIO(json.dumps(payload).encode("utf-8")),
                "application/json",
            )
        },
    )

    assert start_response.status_code == 200
    job_id = start_response.json()["job_id"]
    job = {}
    for _ in range(60):
        status_response = client.get(f"/schedule/upload/jobs/{job_id}")
        assert status_response.status_code == 200
        job = status_response.json()
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert job["status"] == "completed"
    assert job["stages"]["router"]["state"] == "done"
    assert job["stages"]["solve"]["state"] == "done"
    assert job["result"]["solution"]["status"] == "FEASIBLE"


def test_schedule_explicit_config_overrides_parsed_request():
    app = create_app()
    client = TestClient(app)
    payload = demo_payload()
    payload["prefer_cpsat"] = False
    payload["config_overrides"]["allow_container"] = False

    response = client.post("/schedule", json=payload)

    assert response.status_code == 200
    assignments = response.json()["solution"]["assignments"]
    assert assignments
    assert not any(item["use_container"] for item in assignments)


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
                "request": "Schedule workbook short-haul data and allow containers.",
                "instance_id": "workbook-upload-test",
                "date": "2024-12-16",
                "prefer_cpsat": "false",
                "config_overrides_json": '{"allow_container": false}',
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
    assert not any(item["use_container"] for item in data["solution"]["assignments"])


def test_schedule_upload_data_agent_accepts_aligned_workbook(tmp_path):
    pytest.importorskip("multipart")
    app = create_app()
    client = TestClient(app)
    workbook = tmp_path / "business_export.xlsx"
    write_workbook_template(workbook)

    with workbook.open("rb") as fp:
        response = client.post(
            "/schedule/upload",
            data={
                "request": "Schedule this business export.",
                "instance_id": "agent-upload-test",
                "date": "2024-12-16",
                "prefer_cpsat": "false",
                "use_data_agent": "true",
            },
            files={
                "data_file": (
                    "business_export.xlsx",
                    fp,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["upload"]["source"] == "data_agent_workbook"
    assert data["upload"]["data_agent"]["mode"] == "deterministic"
    assert data["solution"]["status"] == "FEASIBLE"


def test_schedule_upload_data_agent_accepts_multiple_standard_files():
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
                "request": "Schedule this uploaded file batch.",
                "instance_id": "agent-multi-file-test",
                "date": "2024-12-16",
                "prefer_cpsat": "false",
                "use_data_agent": "true",
            },
            files=[
                ("data_file", ("fleets.csv", fleets, "text/csv")),
                ("data_file", ("routes.csv", routes, "text/csv")),
                ("data_file", ("forecast.csv", forecast, "text/csv")),
                ("data_file", ("milk_run_pairs.csv", pairs, "text/csv")),
            ],
        )

    assert response.status_code == 200
    data = response.json()
    assert data["upload"]["source"] == "data_agent_files"
    assert data["upload"]["data_agent"]["mode"] == "csv_bundle"
    assert data["upload"]["files"] == [
        "fleets.csv",
        "routes.csv",
        "forecast.csv",
        "milk_run_pairs.csv",
    ]
    assert data["solution"]["status"] == "FEASIBLE"


def test_schedule_upload_data_agent_accepts_pasted_payload_json():
    pytest.importorskip("multipart")
    app = create_app()
    client = TestClient(app)
    payload = demo_payload()
    payload["prefer_cpsat"] = False

    response = client.post(
        "/schedule/upload",
        data={
            "request": "Schedule pasted payload.",
            "instance_id": "agent-text-test",
            "date": "2024-12-16",
            "prefer_cpsat": "false",
            "use_data_agent": "true",
            "raw_data_text": json.dumps(payload),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["upload"]["source"] == "data_agent_text"
    assert data["upload"]["data_agent"]["mode"] == "direct_json"
    assert data["solution"]["status"] == "FEASIBLE"
