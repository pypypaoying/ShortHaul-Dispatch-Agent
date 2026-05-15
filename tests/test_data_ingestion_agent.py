import builtins
import json
import sys
from io import BytesIO
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent.data_ingestion_agent import (  # noqa: E402
    DataIngestionAgent,
    DataIngestionAgentConfig,
    _chat_completions_url,
    _route_file_batch,
)


def test_chat_completions_url_normalizes_base_url():
    assert _chat_completions_url("") == "https://api.openai.com/v1/chat/completions"
    assert _chat_completions_url("https://provider.example/v1") == "https://provider.example/v1/chat/completions"
    assert (
        _chat_completions_url("https://provider.example/v1/chat/completions")
        == "https://provider.example/v1/chat/completions"
    )


def test_llm_call_falls_back_to_http_when_openai_sdk_missing(monkeypatch):
    original_import = builtins.__import__
    captured = {}

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("no openai sdk")
        return original_import(name, *args, **kwargs)

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": '{"ok": true}'}}]}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr("shorthaul_agent.data_ingestion_agent.urllib.request.urlopen", fake_urlopen)

    agent = DataIngestionAgent(
        DataIngestionAgentConfig(
            provider="openai_compatible",
            api_key="test-key",
            base_url="https://provider.example/v1",
            model="custom-ingestion-model",
        )
    )

    assert agent._call_llm("hello") == '{"ok": true}'
    assert captured["url"] == "https://provider.example/v1/chat/completions"
    assert captured["timeout"] == 60
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "custom-ingestion-model"
    assert captured["body"]["messages"][1]["content"] == "hello"


def test_router_detects_raw_structured_attachment_batch():
    files = _raw_attachment_files()

    route = _route_file_batch(files)

    assert route.kind == "raw_structured_attachments"
    assert route.confidence >= 0.9
    assert set(route.file_roles.values()) == {
        "route_metadata",
        "history_10min",
        "known_daily",
        "milk_run_rules",
        "fleet_capacity",
    }


def test_router_sends_messy_business_export_to_llm_path():
    sample_dir = ROOT / "examples" / "messy_upload"
    files = [
        (path.name, path.read_bytes())
        for path in sorted(sample_dir.iterdir())
        if path.suffix.lower() in {".xlsx", ".txt"}
    ]

    route = _route_file_batch(files)

    assert route.kind == "llm_required"
    assert "No deterministic input standard matched" in route.reason
    assert route.file_roles == {}


def test_raw_structured_attachment_batch_builds_payload_without_llm():
    files = _raw_attachment_files()
    agent = DataIngestionAgent(DataIngestionAgentConfig(api_key=""))

    payload, meta = agent.build_payload_from_files(
        files,
        "请根据上传附件生成调度方案。",
        instance_id="raw-attachment-test",
        date="2024-12-16",
        prefer_cpsat=False,
    )

    assert meta["mode"] == "raw_structured_attachments"
    assert meta["router"]["kind"] == "raw_structured_attachments"
    assert payload["instance"]["id"] == "raw-attachment-test"
    assert len(payload["instance"]["routes"]) == 2
    assert len(payload["instance"]["fleets"]) == 1
    assert len(payload["instance"]["forecast"]) == 72
    assert payload["config_overrides"]["milk_run_pairs"] == [["站点1", "站点2"]]


def _raw_attachment_files():
    route_rows = pd.DataFrame(
        [
            {
                "线路编码": "场地1 - 站点1 - 0600",
                "起始场地": "场地1",
                "目的场地": "站点1",
                "发运节点": "06:00",
                "车队编码": "车队1",
                "在途时长": 1.0,
                "自有变动成本": 60,
                "外部承运商成本": 120,
            },
            {
                "线路编码": "场地1 - 站点2 - 1400",
                "起始场地": "场地1",
                "目的场地": "站点2",
                "发运节点": "14:00",
                "车队编码": "车队1",
                "在途时长": 1.0,
                "自有变动成本": 70,
                "外部承运商成本": 130,
            },
        ]
    )
    history_rows = []
    for route_id, minute in [
        ("场地1 - 站点1 - 0600", "21:00"),
        ("场地1 - 站点2 - 1400", "11:00"),
    ]:
        history_rows.append(
            {
                "线路编码": route_id,
                "日期": "2024-12-15",
                "分钟起始": minute,
                "包裹量": 100,
            }
        )
    known_rows = pd.DataFrame(
        [
            {"线路编码": "场地1 - 站点1 - 0600", "日期": "2024-12-15", "包裹量": 100},
            {"线路编码": "场地1 - 站点1 - 0600", "日期": "2024-12-16", "包裹量": 120},
            {"线路编码": "场地1 - 站点2 - 1400", "日期": "2024-12-15", "包裹量": 100},
            {"线路编码": "场地1 - 站点2 - 1400", "日期": "2024-12-16", "包裹量": 130},
        ]
    )
    pair_rows = pd.DataFrame([{"站点编号1": "站点1", "站点编号2": "站点2"}])
    fleet_rows = pd.DataFrame([{"车队编码": "车队1", "自有车数量": 2}])
    return [
        ("线路.xlsx", _xlsx_bytes(route_rows)),
        ("历史.xlsx", _xlsx_bytes(pd.DataFrame(history_rows))),
        ("预知.xlsx", _xlsx_bytes(known_rows)),
        ("串点.xlsx", _xlsx_bytes(pair_rows)),
        ("车队.xlsx", _xlsx_bytes(fleet_rows)),
    ]


def _xlsx_bytes(frame: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False)
    return buffer.getvalue()
