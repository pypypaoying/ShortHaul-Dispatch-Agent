from pathlib import Path
import sys

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from shorthaul_agent.api import create_app  # noqa: E402
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
