"""LLM-assisted data ingestion agent for external operational files."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from shorthaul_agent.external_io import (
    WORKBOOK_SHEETS,
    _deep_merge,
    _write_workbook_rows,
    build_payload_from_workbook,
)
from shorthaul_agent.models import Instance


@dataclass
class DataIngestionAgentConfig:
    """Configuration for the user-provided OpenAI-compatible ingestion API."""

    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4.1-mini"

    @classmethod
    def from_values(
        cls,
        *,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ) -> "DataIngestionAgentConfig":
        return cls(
            api_key=api_key or os.getenv("SHORT_HAUL_INGESTION_API_KEY", "") or os.getenv("OPENAI_API_KEY", ""),
            base_url=base_url or os.getenv("SHORT_HAUL_INGESTION_BASE_URL", ""),
            model=model or os.getenv("SHORT_HAUL_INGESTION_MODEL", "gpt-4.1-mini"),
        )


class DataIngestionAgent:
    """Align user files or pasted data to the internal scheduling payload."""

    def __init__(self, config: DataIngestionAgentConfig | None = None) -> None:
        self.config = config or DataIngestionAgentConfig.from_values()

    def build_payload_from_workbook(
        self,
        workbook_path: str | Path,
        request_text: str,
        *,
        instance_id: str = "agent-ingested-instance",
        date: str = "",
        prefer_cpsat: bool = True,
        config_overrides: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Build a schedule payload from a user workbook.

        The agent first tries the deterministic adapter. If the workbook is not
        already aligned with known aliases, it asks the configured LLM API for a
        sheet/column mapping and rewrites a normalized temporary workbook.
        """
        try:
            payload = build_payload_from_workbook(
                workbook_path,
                request_text,
                instance_id=instance_id,
                date=date,
                prefer_cpsat=prefer_cpsat,
                config_overrides=config_overrides,
            )
            Instance.from_dict(payload["instance"])
            return payload, {"mode": "deterministic", "model": "", "warnings": []}
        except Exception as deterministic_error:
            if not self.config.api_key:
                raise ValueError(
                    "数据接入 Agent 无法自动识别该文件。请配置 SHORT_HAUL_INGESTION_API_KEY "
                    "或在界面填写 Agent API Key 后重试。"
                ) from deterministic_error

        mapping = self._map_workbook_with_llm(Path(workbook_path))
        with tempfile.TemporaryDirectory(prefix="shorthaul-agent-mapped-") as tmp_dir:
            normalized_path = Path(tmp_dir) / "agent_normalized_workbook.xlsx"
            self._write_mapped_workbook(Path(workbook_path), mapping, normalized_path)
            payload = build_payload_from_workbook(
                normalized_path,
                request_text,
                instance_id=instance_id,
                date=date,
                prefer_cpsat=prefer_cpsat,
                config_overrides=config_overrides,
            )
        Instance.from_dict(payload["instance"])
        return payload, {"mode": "llm_mapping", "model": self.config.model, "mapping": mapping, "warnings": []}

    def build_payload_from_text(
        self,
        raw_text: str,
        request_text: str,
        *,
        instance_id: str = "agent-ingested-instance",
        date: str = "",
        prefer_cpsat: bool = True,
        config_overrides: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Build a schedule payload from pasted tables, CSV text, or JSON."""
        raw_text = raw_text.strip()
        if not raw_text:
            raise ValueError("No raw data text was provided.")

        direct = self._try_direct_json_payload(raw_text, request_text, prefer_cpsat, config_overrides)
        if direct is not None:
            return direct, {"mode": "direct_json", "model": "", "warnings": []}

        if not self.config.api_key:
            raise ValueError("粘贴数据需要配置数据接入 Agent API Key，才能自动转换为调度输入。")

        payload = self._payload_from_text_with_llm(raw_text, request_text, instance_id, date, prefer_cpsat)
        if config_overrides:
            payload["config_overrides"] = _deep_merge(payload.get("config_overrides", {}), config_overrides)
        Instance.from_dict(payload["instance"])
        return payload, {"mode": "llm_text_payload", "model": self.config.model, "warnings": []}

    def _map_workbook_with_llm(self, workbook_path: Path) -> dict[str, Any]:
        summary = _workbook_summary(workbook_path)
        schema = {
            sheet: [column[0] for column in meta["columns"]]
            for sheet, meta in WORKBOOK_SHEETS.items()
        }
        prompt = (
            "你是 ShortHaul Dispatch Agent 的数据接入 Agent。"
            "用户上传的是业务系统导出的 Excel，不一定符合内部字段名。"
            "请只输出 JSON，不要解释。JSON 结构："
            "{\"sheets\":{\"fleets\":\"源sheet\",\"routes\":\"源sheet\",\"demand\":\"源sheet\","
            "\"compatibility\":\"源sheet或空\",\"settings\":\"源sheet或空\"},"
            "\"columns\":{\"fleets\":{\"fleet_id\":\"源列名\",\"owned_vehicles\":\"源列名\"},"
            "\"routes\":{},\"demand\":{},\"compatibility\":{},\"settings\":{}}}。"
            "目标字段如下："
            f"{json.dumps(schema, ensure_ascii=False)}。"
            "若找不到可选字段，填空字符串。"
            f"工作簿摘要：{json.dumps(summary, ensure_ascii=False)}"
        )
        return _extract_json_object(self._call_llm(prompt))

    def _payload_from_text_with_llm(
        self,
        raw_text: str,
        request_text: str,
        instance_id: str,
        date: str,
        prefer_cpsat: bool,
    ) -> dict[str, Any]:
        prompt = (
            "你是 ShortHaul Dispatch Agent 的数据接入 Agent。"
            "请把用户粘贴的业务数据转换成 /schedule API payload。只输出 JSON，不要解释。"
            "payload 必须包含 request, prefer_cpsat, config_overrides, instance。"
            "instance 必须包含 id, date, fleets, routes, forecast。"
            "字段含义：fleets 使用 id、vehicle_count；routes 使用 id、origin、destination、wave、"
            "latest_dispatch_minute、travel_minutes、fleet_id；forecast 使用 route_id、minute、volume。"
            "缺失的装卸时间和成本可使用合理默认值。"
            f"instance_id={instance_id}, date={date}, prefer_cpsat={prefer_cpsat}。"
            f"调度需求：{request_text}\n用户数据：{raw_text[:12000]}"
        )
        payload = _extract_json_object(self._call_llm(prompt))
        payload.setdefault("request", request_text)
        payload.setdefault("prefer_cpsat", prefer_cpsat)
        payload.setdefault("config_overrides", {})
        payload.setdefault("instance", {})
        payload["instance"].setdefault("id", instance_id)
        payload["instance"].setdefault("date", date)
        return payload

    def _write_mapped_workbook(self, source_path: Path, mapping: dict[str, Any], output_path: Path) -> None:
        source = pd.read_excel(source_path, sheet_name=None)
        rows: dict[str, list[list[Any]]] = {}
        sheet_map = mapping.get("sheets", {})
        column_map = mapping.get("columns", {})
        for target_sheet, meta in WORKBOOK_SHEETS.items():
            source_sheet = _mapping_value(sheet_map.get(target_sheet))
            if not source_sheet or source_sheet not in source:
                rows[target_sheet] = []
                continue
            frame = source[source_sheet].dropna(how="all")
            mapped_columns = column_map.get(target_sheet, {})
            headers = [column[0] for column in meta["columns"]]
            sheet_rows = []
            for _, raw in frame.iterrows():
                row = []
                for target_col in headers:
                    source_col = _mapping_value(mapped_columns.get(target_col))
                    row.append(raw.get(source_col, "") if source_col else "")
                if any(str(item).strip() for item in row):
                    sheet_rows.append(row)
            rows[target_sheet] = sheet_rows
        _write_workbook_rows(rows, output_path)

    def _call_llm(self, prompt: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ValueError("数据接入 Agent 需要安装 openai：python -m pip install -e '.[llm]'") from exc

        client_kwargs = {"api_key": self.config.api_key}
        if self.config.base_url:
            client_kwargs["base_url"] = self.config.base_url
        client = OpenAI(**client_kwargs)
        response = client.chat.completions.create(
            model=self.config.model,
            messages=[
                {
                    "role": "system",
                    "content": "你只输出可以被 json.loads 解析的 JSON。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content or ""
        return content.strip()

    def _try_direct_json_payload(
        self,
        raw_text: str,
        request_text: str,
        prefer_cpsat: bool,
        config_overrides: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        if "instance" not in payload:
            return None
        payload = dict(payload)
        payload.setdefault("request", request_text)
        payload["prefer_cpsat"] = prefer_cpsat
        payload["config_overrides"] = _deep_merge(payload.get("config_overrides", {}), config_overrides or {})
        Instance.from_dict(payload["instance"])
        return payload


def _workbook_summary(path: Path) -> list[dict[str, Any]]:
    sheets = pd.read_excel(path, sheet_name=None)
    summary = []
    for sheet_name, frame in sheets.items():
        sample = frame.dropna(how="all").head(5)
        rows = []
        for raw in sample.to_dict(orient="records"):
            rows.append({str(key): _preview_value(value) for key, value in raw.items()})
        summary.append(
            {
                "sheet": str(sheet_name),
                "columns": [str(column) for column in frame.columns],
                "sample_rows": rows,
            }
        )
    return summary


def _preview_value(value: Any) -> Any:
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    text = str(value)
    return text if len(text) <= 120 else text[:117] + "..."


def _extract_json_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("数据接入 Agent 未返回 JSON。")
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("数据接入 Agent 返回的内容不是 JSON object。")
    return payload


def _mapping_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
