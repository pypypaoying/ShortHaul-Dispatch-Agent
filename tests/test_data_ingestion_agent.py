import builtins
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent.data_ingestion_agent import (  # noqa: E402
    DataIngestionAgent,
    DataIngestionAgentConfig,
    _chat_completions_url,
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
