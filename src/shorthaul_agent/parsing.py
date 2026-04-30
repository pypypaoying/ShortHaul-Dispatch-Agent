"""Requirement parsing with an optional LLM path and a deterministic fallback."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from shorthaul_agent.models import ParsedRequirement


class RequirementParser:
    """Parse natural-language scheduling requests into structured controls."""

    def parse(self, text: str) -> ParsedRequirement:
        llm_result = self._try_llm_parse(text)
        if llm_result is not None:
            return llm_result
        return self._rule_parse(text)

    def _try_llm_parse(self, text: str) -> Optional[ParsedRequirement]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            from openai import OpenAI
        except ImportError:
            return None

        schema_hint = {
            "target_date": "YYYY-MM-DD or null",
            "route_focus": ["route names mentioned by the user"],
            "config_overrides": {
                "allow_container": "boolean if explicit",
                "vehicle_capacity": "integer if explicit",
                "container_capacity": "integer if explicit",
                "objective_weights": {"cost": "float", "turnover": "float", "fill_rate": "float"},
            },
            "hard_constraints": ["must-have operational constraints"],
            "soft_preferences": ["optimization preferences"],
            "warnings": ["ambiguities or missing information"],
        }
        prompt = (
            "你是短途运输调度需求解析 Agent。只输出 JSON，不要解释。\n"
            f"JSON 字段模板：{json.dumps(schema_hint, ensure_ascii=False)}\n"
            f"用户需求：{text}"
        )
        try:
            client = OpenAI(api_key=api_key)
            response = client.responses.create(
                model=os.getenv("SHORT_HAUL_LLM_MODEL", "gpt-4.1-mini"),
                input=prompt,
                temperature=0,
            )
            payload = json.loads(response.output_text)
        except Exception:
            return None
        return ParsedRequirement(raw_text=text, **_clean_payload(payload))

    def _rule_parse(self, text: str) -> ParsedRequirement:
        result = ParsedRequirement(raw_text=text)
        date_match = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})", text)
        if date_match:
            year, month, day = date_match.groups()
            result.target_date = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

        result.route_focus = _extract_route_mentions(text)
        overrides: dict[str, Any] = {}

        capacity_match = re.search(r"(?:车辆|标称)?容量(?:为|=|:)?\s*(\d{3,5})", text)
        if capacity_match:
            overrides["vehicle_capacity"] = int(capacity_match.group(1))

        container_capacity_match = re.search(r"容器(?:容量|装载量)(?:为|=|:)?\s*(\d{3,5})", text)
        if container_capacity_match:
            overrides["container_capacity"] = int(container_capacity_match.group(1))

        if re.search(r"不使用|禁用|不用", text) and "容器" in text:
            overrides["allow_container"] = False
        elif "容器" in text:
            overrides["allow_container"] = True

        weights = {}
        if any(keyword in text for keyword in ["成本优先", "降低成本", "最小成本", "成本最低"]):
            weights["cost"] = 1.4
        if any(keyword in text for keyword in ["周转率优先", "提高周转", "自有车优先"]):
            weights["turnover"] = 0.9
        if any(keyword in text for keyword in ["装载率", "填充率", "均包裹数"]):
            weights["fill_rate"] = 0.5
        if weights:
            overrides["objective_weights"] = weights

        if any(keyword in text for keyword in ["必须", "不得", "不超过", "最晚"]):
            result.hard_constraints.append("用户包含硬约束表述，需由约束检查 Agent 复核。")
        if any(keyword in text for keyword in ["优先", "尽量", "平衡"]):
            result.soft_preferences.append("用户包含偏好目标，已映射到多目标权重。")

        if not result.target_date:
            result.warnings.append("未识别到明确日期，将使用实例文件中的日期。")
        result.config_overrides = overrides
        return result


def _extract_route_mentions(text: str) -> list[str]:
    route_pattern = re.compile(r"场地\s*\d+\s*-\s*站点\s*\d+\s*-\s*\d{4}")
    mentions = [re.sub(r"\s+", " ", item).replace(" - ", "-").replace("-", " - ") for item in route_pattern.findall(text)]
    return list(dict.fromkeys(mentions))


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "target_date",
        "route_focus",
        "config_overrides",
        "hard_constraints",
        "soft_preferences",
        "warnings",
    }
    cleaned = {key: value for key, value in payload.items() if key in allowed}
    for key in ("route_focus", "hard_constraints", "soft_preferences", "warnings"):
        if key in cleaned and not isinstance(cleaned[key], list):
            cleaned[key] = [str(cleaned[key])]
    if "config_overrides" in cleaned and not isinstance(cleaned["config_overrides"], dict):
        cleaned["config_overrides"] = {}
    return cleaned
