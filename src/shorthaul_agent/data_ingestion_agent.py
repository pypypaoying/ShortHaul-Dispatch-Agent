"""LLM-assisted data ingestion agent for external operational files."""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import time
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from shorthaul_agent.external_io import (
    WORKBOOK_SHEETS,
    _deep_merge,
    _write_workbook_rows,
    build_payload_from_csv_dir,
    build_payload_from_workbook,
)
from shorthaul_agent.models import Instance


WORKBOOK_SUFFIXES = {".xlsx", ".xlsm", ".xls"}
TEXT_SUFFIXES = {".csv", ".tsv", ".txt", ".json"}
PAYLOAD_FILENAMES = {"payload.json", "schedule_payload.json"}
CSV_FILE_ALIASES = {
    "fleets.csv": "fleets.csv",
    "routes.csv": "routes.csv",
    "forecast.csv": "forecast.csv",
    "milk_run_pairs.csv": "milk_run_pairs.csv",
    "config_overrides.json": "config_overrides.json",
}

RAW_ATTACHMENT_SCHEMAS = {
    "route_metadata": {"线路编码", "起始场地", "目的场地", "发运节点", "车队编码", "在途时长", "自有变动成本", "外部承运商成本"},
    "history_10min": {"线路编码", "日期", "分钟起始", "包裹量"},
    "known_daily": {"线路编码", "日期", "包裹量"},
    "milk_run_rules": {"站点编号1", "站点编号2"},
    "fleet_capacity": {"车队编码", "自有车数量"},
}

RAW_ATTACHMENT_CONFIG = {
    "vehicle_capacity": 1000,
    "container_capacity": 800,
    "max_stops": 3,
    "allow_container": True,
    "allow_external": True,
    "tail_cover_strategy": "cost_aware",
    "tail_candidate_strategy": "exhaustive",
    "tail_beam_width": 12,
    "solver_time_limit_seconds": 20.0,
    "objective_weights": {"cost": 1.0, "turnover": 0.5, "fill_rate": 0.2},
}


@dataclass
class IngestionRoute:
    """Router decision for an uploaded file batch."""

    kind: str
    confidence: float
    reason: str
    file_roles: dict[str, str]
    warnings: list[str]


@dataclass
class DataIngestionAgentConfig:
    """Configuration for the user-provided Chat Completions-compatible API."""

    provider: str = "openai_compatible"
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4.1-mini"

    @classmethod
    def from_values(
        cls,
        *,
        provider: str = "",
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ) -> "DataIngestionAgentConfig":
        return cls(
            provider=provider or os.getenv("SHORT_HAUL_INGESTION_PROVIDER", "openai_compatible"),
            api_key=api_key or os.getenv("SHORT_HAUL_INGESTION_API_KEY", "") or os.getenv("OPENAI_API_KEY", ""),
            base_url=base_url or os.getenv("SHORT_HAUL_INGESTION_BASE_URL", ""),
            model=model or os.getenv("SHORT_HAUL_INGESTION_MODEL", "gpt-4.1-mini"),
        )


class DataIngestionAgent:
    """Align user files or pasted data to the internal scheduling payload."""

    def __init__(self, config: DataIngestionAgentConfig | None = None) -> None:
        self.config = config or DataIngestionAgentConfig.from_values()

    def build_payload_from_files(
        self,
        files: list[tuple[str, bytes]],
        request_text: str,
        *,
        instance_id: str = "agent-ingested-instance",
        date: str = "",
        prefer_cpsat: bool = True,
        config_overrides: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Build a schedule payload from one or more uploaded business files."""
        cleaned = [(Path(name).name, content) for name, content in files if name and content]
        if not cleaned:
            raise ValueError("No data files were provided.")

        route = _route_file_batch(cleaned)
        deterministic = self._try_deterministic_file_batch(
            cleaned,
            request_text,
            route=route,
            instance_id=instance_id,
            date=date,
            prefer_cpsat=prefer_cpsat,
            config_overrides=config_overrides,
        )
        if deterministic is not None:
            return deterministic

        if not self.config.api_key:
            raise ValueError(
                "多文件业务数据无法在本地自动识别。请配置数据接入 Agent API Key，"
                "或上传标准 payload、标准 CSV 文件组、单个已规整工作簿、可识别的原始业务附件包。"
            )

        payload = self._payload_from_files_with_llm(cleaned, request_text, instance_id, date, prefer_cpsat)
        if config_overrides:
            payload["config_overrides"] = _deep_merge(payload.get("config_overrides", {}), config_overrides)
        Instance.from_dict(payload["instance"])
        return payload, {
            "mode": "llm_file_batch_payload",
            "provider": self.config.provider,
            "model": self.config.model,
            "router": _route_to_dict(route),
            "files": [name for name, _ in cleaned],
            "warnings": [],
        }

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
            return payload, {"mode": "deterministic", "provider": self.config.provider, "model": "", "warnings": []}
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
        return payload, {
            "mode": "llm_mapping",
            "provider": self.config.provider,
            "model": self.config.model,
            "mapping": mapping,
            "warnings": [],
        }

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
            return direct, {"mode": "direct_json", "provider": self.config.provider, "model": "", "warnings": []}

        if not self.config.api_key:
            raise ValueError("粘贴数据需要配置数据接入 Agent API Key，才能自动转换为调度输入。")

        payload = self._payload_from_text_with_llm(raw_text, request_text, instance_id, date, prefer_cpsat)
        if config_overrides:
            payload["config_overrides"] = _deep_merge(payload.get("config_overrides", {}), config_overrides)
        Instance.from_dict(payload["instance"])
        return payload, {
            "mode": "llm_text_payload",
            "provider": self.config.provider,
            "model": self.config.model,
            "warnings": [],
        }

    def _try_deterministic_file_batch(
        self,
        files: list[tuple[str, bytes]],
        request_text: str,
        *,
        route: IngestionRoute,
        instance_id: str,
        date: str,
        prefer_cpsat: bool,
        config_overrides: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        if route.kind == "raw_structured_attachments":
            payload = _build_payload_from_raw_structured_attachments(
                files,
                route,
                request_text,
                instance_id=instance_id,
                date=date,
                prefer_cpsat=prefer_cpsat,
                config_overrides=config_overrides,
            )
            return payload, {
                "mode": "raw_structured_attachments",
                "provider": self.config.provider,
                "model": "",
                "router": _route_to_dict(route),
                "warnings": route.warnings,
            }

        for filename, content in files:
            if filename.lower() in PAYLOAD_FILENAMES:
                direct = self._try_direct_json_payload(
                    content.decode("utf-8-sig"),
                    request_text,
                    prefer_cpsat,
                    config_overrides,
                )
                if direct is not None:
                    return direct, {
                        "mode": "direct_json_file",
                        "provider": self.config.provider,
                        "model": "",
                        "router": _route_to_dict(route),
                        "warnings": [],
                    }

        csv_bundle = {
            CSV_FILE_ALIASES[filename.lower()]: content
            for filename, content in files
            if filename.lower() in CSV_FILE_ALIASES
        }
        if {"fleets.csv", "routes.csv", "forecast.csv"}.issubset(csv_bundle):
            with tempfile.TemporaryDirectory(prefix="shorthaul-agent-csv-batch-") as tmp_dir:
                tmp_path = Path(tmp_dir)
                for filename, content in csv_bundle.items():
                    (tmp_path / filename).write_bytes(content)
                payload = build_payload_from_csv_dir(
                    tmp_path,
                    request_text,
                    instance_id=instance_id,
                    date=date,
                    prefer_cpsat=prefer_cpsat,
                    config_overrides=config_overrides,
                )
            Instance.from_dict(payload["instance"])
            return payload, {
                "mode": "csv_bundle",
                "provider": self.config.provider,
                "model": "",
                "router": _route_to_dict(route),
                "warnings": [],
            }

        if len(files) == 1:
            filename, content = files[0]
            suffix = Path(filename.lower()).suffix
            if suffix in WORKBOOK_SUFFIXES:
                with tempfile.TemporaryDirectory(prefix="shorthaul-agent-workbook-") as tmp_dir:
                    workbook_path = Path(tmp_dir) / filename
                    workbook_path.write_bytes(content)
                    return self.build_payload_from_workbook(
                        workbook_path,
                        request_text,
                        instance_id=instance_id,
                        date=date,
                        prefer_cpsat=prefer_cpsat,
                        config_overrides=config_overrides,
                    )
            if suffix in TEXT_SUFFIXES:
                return self.build_payload_from_text(
                    content.decode("utf-8-sig"),
                    request_text,
                    instance_id=instance_id,
                    date=date,
                    prefer_cpsat=prefer_cpsat,
                    config_overrides=config_overrides,
                )
        return None

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

    def _payload_from_files_with_llm(
        self,
        files: list[tuple[str, bytes]],
        request_text: str,
        instance_id: str,
        date: str,
        prefer_cpsat: bool,
    ) -> dict[str, Any]:
        summary = _file_batch_summary(files)
        prompt = (
            "你是 ShortHaul Dispatch Agent 的数据接入 Agent。"
            "用户一次上传了多个业务数据文件，请根据文件摘要把它们整合为 /schedule API payload。"
            "只输出 JSON，不要解释。payload 必须包含 request, prefer_cpsat, config_overrides, instance。"
            "instance 必须包含 id, date, fleets, routes, forecast。"
            "字段含义：fleets 使用 id、vehicle_count；routes 使用 id、origin、destination、wave、"
            "latest_dispatch_minute、travel_minutes、fleet_id；forecast 使用 route_id、minute、volume。"
            "如果多文件中存在容量、容器、串点、外部承运或目标权重设置，请写入 config_overrides。"
            "缺失的装卸时间和成本可使用合理默认值。"
            f"instance_id={instance_id}, date={date}, prefer_cpsat={prefer_cpsat}。"
            f"调度需求：{request_text}\n文件摘要：{json.dumps(summary, ensure_ascii=False)}"
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
        except ImportError:
            return self._call_llm_via_http(prompt)

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

    def _call_llm_via_http(self, prompt: str) -> str:
        url = _chat_completions_url(self.config.base_url)
        body = json.dumps(
            {
                "model": self.config.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你只输出可以被 json.loads 解析的 JSON。",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ValueError(f"数据接入 Agent LLM API 请求失败：HTTP {exc.code} {detail[:500]}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(f"数据接入 Agent LLM API 无法连接：{exc.reason}") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("数据接入 Agent LLM API 返回格式不兼容 Chat Completions。") from exc
        return str(content or "").strip()

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
    return _summarize_sheets(sheets)


def _workbook_bytes_summary(content: bytes) -> list[dict[str, Any]]:
    sheets = pd.read_excel(BytesIO(content), sheet_name=None)
    return _summarize_sheets(sheets)


def _summarize_sheets(sheets: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
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


def _file_batch_summary(files: list[tuple[str, bytes]]) -> list[dict[str, Any]]:
    summary = []
    for filename, content in files:
        suffix = Path(filename.lower()).suffix
        item: dict[str, Any] = {"file": filename, "suffix": suffix, "bytes": len(content)}
        try:
            if suffix in WORKBOOK_SUFFIXES:
                item["sheets"] = _workbook_bytes_summary(content)
            elif suffix in {".csv", ".tsv"}:
                separator = "\t" if suffix == ".tsv" else ","
                frame = pd.read_csv(BytesIO(content), sep=separator)
                item["columns"] = [str(column) for column in frame.columns]
                item["sample_rows"] = [
                    {str(key): _preview_value(value) for key, value in row.items()}
                    for row in frame.dropna(how="all").head(8).to_dict(orient="records")
                ]
            elif suffix == ".json":
                text = content.decode("utf-8-sig", errors="replace")
                item["text_preview"] = text[:5000]
                try:
                    parsed = json.loads(text)
                    item["json_type"] = type(parsed).__name__
                    if isinstance(parsed, dict):
                        item["json_keys"] = list(parsed.keys())[:40]
                except json.JSONDecodeError:
                    pass
            else:
                item["text_preview"] = content.decode("utf-8-sig", errors="replace")[:5000]
        except Exception as exc:
            item["read_error"] = str(exc)
            item["text_preview"] = content.decode("utf-8-sig", errors="replace")[:2000]
        summary.append(item)
    return summary


def _route_file_batch(files: list[tuple[str, bytes]]) -> IngestionRoute:
    names = [filename for filename, _ in files]
    lower_names = {filename.lower() for filename in names}
    if lower_names & PAYLOAD_FILENAMES:
        return IngestionRoute(
            kind="payload_json",
            confidence=1.0,
            reason="Uploaded files include a complete payload JSON.",
            file_roles={filename: "payload_json" for filename in names if filename.lower() in PAYLOAD_FILENAMES},
            warnings=[],
        )
    if {"fleets.csv", "routes.csv", "forecast.csv"}.issubset(lower_names):
        roles = {
            filename: CSV_FILE_ALIASES[filename.lower()]
            for filename in names
            if filename.lower() in CSV_FILE_ALIASES
        }
        return IngestionRoute(
            kind="csv_bundle",
            confidence=1.0,
            reason="Uploaded files match the standard CSV bundle names.",
            file_roles=roles,
            warnings=[],
        )
    if len(files) == 1:
        filename, content = files[0]
        suffix = Path(filename.lower()).suffix
        if suffix in WORKBOOK_SUFFIXES:
            workbook_kind = _classify_standard_workbook(content)
            if workbook_kind:
                return IngestionRoute(
                    kind="standard_workbook",
                    confidence=0.95,
                    reason=workbook_kind,
                    file_roles={filename: "standard_workbook"},
                    warnings=[],
                )
            return IngestionRoute(
                kind="llm_required",
                confidence=0.2,
                reason="Workbook does not expose the standard fleets/routes/demand sheets.",
                file_roles={filename: "unclassified_workbook"},
                warnings=[],
            )
        if suffix in TEXT_SUFFIXES:
            return IngestionRoute(
                kind="text_or_json",
                confidence=0.8,
                reason="Single text-like upload can be parsed as JSON locally or routed to LLM.",
                file_roles={filename: "text_or_json"},
                warnings=[],
            )

    raw_roles, raw_warnings = _classify_raw_structured_attachments(files)
    required = {"route_metadata", "history_10min", "known_daily", "fleet_capacity"}
    if required.issubset(set(raw_roles.values())):
        confidence = 0.98 if "milk_run_rules" in raw_roles.values() else 0.9
        return IngestionRoute(
            kind="raw_structured_attachments",
            confidence=confidence,
            reason="Uploaded tables match the built-in raw short-haul attachment column standards.",
            file_roles=raw_roles,
            warnings=raw_warnings,
        )

    return IngestionRoute(
        kind="llm_required",
        confidence=0.0,
        reason="No deterministic input standard matched the uploaded file batch.",
        file_roles=raw_roles,
        warnings=raw_warnings,
    )


def _route_to_dict(route: IngestionRoute) -> dict[str, Any]:
    return {
        "kind": route.kind,
        "confidence": route.confidence,
        "reason": route.reason,
        "file_roles": route.file_roles,
        "warnings": route.warnings,
    }


def _classify_standard_workbook(content: bytes) -> str:
    try:
        sheets = pd.read_excel(BytesIO(content), sheet_name=None, nrows=2)
    except Exception:
        return ""
    normalized = {str(name).strip().lower() for name in sheets}
    if {"fleets", "routes", "demand"}.issubset(normalized):
        return "Workbook contains the standard fleets/routes/demand sheets."
    return ""


def _classify_raw_structured_attachments(files: list[tuple[str, bytes]]) -> tuple[dict[str, str], list[str]]:
    roles: dict[str, str] = {}
    warnings: list[str] = []
    for filename, content in files:
        suffix = Path(filename.lower()).suffix
        if suffix not in WORKBOOK_SUFFIXES and suffix not in {".csv", ".tsv"}:
            continue
        try:
            columns = _read_table_columns(filename, content)
        except Exception as exc:
            warnings.append(f"{filename}: cannot inspect columns ({exc})")
            continue
        role = _raw_attachment_role(columns)
        if role:
            if role in roles.values():
                warnings.append(f"{filename}: duplicate candidate for {role}")
            roles[filename] = role
    return roles, warnings


def _read_table_columns(filename: str, content: bytes) -> set[str]:
    suffix = Path(filename.lower()).suffix
    if suffix in WORKBOOK_SUFFIXES:
        frame = pd.read_excel(BytesIO(content), nrows=2)
    else:
        separator = "\t" if suffix == ".tsv" else ","
        frame = pd.read_csv(BytesIO(content), sep=separator, nrows=2)
    return {str(column).strip() for column in frame.columns}


def _raw_attachment_role(columns: set[str]) -> str:
    for role, required in RAW_ATTACHMENT_SCHEMAS.items():
        if required.issubset(columns):
            return role
    return ""


def _build_payload_from_raw_structured_attachments(
    files: list[tuple[str, bytes]],
    route: IngestionRoute,
    request_text: str,
    *,
    instance_id: str,
    date: str,
    prefer_cpsat: bool,
    config_overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    from shorthaul_agent.experiment import (
        DDataset,
        build_instance,
        build_milk_run_pairs,
        disaggregate_to_10min,
        forecast_daily_volume,
        normalize_fleet_code,
        normalize_route_code,
    )

    frame_by_role: dict[str, pd.DataFrame] = {}
    for filename, content in files:
        role = route.file_roles.get(filename)
        if role:
            frame_by_role[role] = _read_uploaded_table(filename, content)

    target_date = _target_date_from_raw_attachments(frame_by_role["known_daily"], date)
    base_date = target_date - pd.Timedelta(days=1)

    routes = frame_by_role["route_metadata"].copy()
    history = frame_by_role["history_10min"].copy()
    known_daily = frame_by_role["known_daily"].copy()
    fleets = frame_by_role["fleet_capacity"].copy()
    milk_run_rules = frame_by_role.get("milk_run_rules", pd.DataFrame(columns=["站点编号1", "站点编号2"])).copy()

    for frame in (routes, history, known_daily):
        frame["线路编码"] = frame["线路编码"].map(normalize_route_code)
    routes["车队编码"] = routes["车队编码"].map(normalize_fleet_code)
    fleets["车队编码"] = fleets["车队编码"].map(normalize_fleet_code)

    result2_template = _build_result2_template(routes, target_date)
    dataset = DDataset(
        routes=routes,
        history=history,
        known_daily=known_daily,
        milk_run_rules=milk_run_rules,
        fleets=fleets,
        result_templates={"结果表2": result2_template},
    )
    daily_forecast = forecast_daily_volume(dataset, target_date)
    ten_min_forecast = disaggregate_to_10min(dataset, daily_forecast, target_date)
    instance = build_instance(dataset, ten_min_forecast, target_date, base_date).to_dict()
    instance["id"] = instance_id or "raw-structured-attachments"

    overrides = dict(RAW_ATTACHMENT_CONFIG)
    pairs = sorted([list(pair) for pair in build_milk_run_pairs(milk_run_rules)]) if not milk_run_rules.empty else []
    if pairs:
        overrides["milk_run_pairs"] = pairs
    if config_overrides:
        overrides = _deep_merge(overrides, config_overrides)
    return {
        "request": request_text,
        "prefer_cpsat": prefer_cpsat,
        "config_overrides": overrides,
        "instance": instance,
    }


def _read_uploaded_table(filename: str, content: bytes) -> pd.DataFrame:
    suffix = Path(filename.lower()).suffix
    if suffix in WORKBOOK_SUFFIXES:
        return pd.read_excel(BytesIO(content))
    separator = "\t" if suffix == ".tsv" else ","
    return pd.read_csv(BytesIO(content), sep=separator)


def _target_date_from_raw_attachments(known_daily: pd.DataFrame, date: str) -> pd.Timestamp:
    if date:
        return pd.Timestamp(date).normalize()
    dates = pd.to_datetime(known_daily["日期"], errors="coerce").dropna()
    if not dates.empty:
        return dates.max().normalize()
    return pd.Timestamp("2024-12-16")


def _build_result2_template(routes: pd.DataFrame, target_date: pd.Timestamp) -> pd.DataFrame:
    records = []
    for row in routes.itertuples(index=False):
        route_id = getattr(row, "线路编码")
        wave = str(route_id).split(" - ")[-1]
        if wave == "0600":
            start = target_date - pd.Timedelta(hours=3)
            periods = 54
        else:
            start = target_date + pd.Timedelta(hours=11)
            periods = 18
        for idx in range(periods):
            moment = start + pd.Timedelta(minutes=10 * idx)
            records.append(
                {
                    "线路编码": route_id,
                    "日期": moment.normalize(),
                    "分钟起始": time(moment.hour, moment.minute),
                    "包裹量": 0,
                }
            )
    return pd.DataFrame(records)


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


def _chat_completions_url(base_url: str) -> str:
    base = (base_url or "https://api.openai.com/v1").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"
