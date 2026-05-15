"""Benchmark Chat-Completions models on messy table ingestion.

The script intentionally evaluates only the data-alignment step plus a fast
end-to-end scheduling run. API keys are read from environment variables and are
never written to the report.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent import DispatchOrchestrator, ProblemConfig  # noqa: E402
from shorthaul_agent.data_ingestion_agent import DataIngestionAgent, DataIngestionAgentConfig, _route_file_batch  # noqa: E402
from shorthaul_agent.models import Instance  # noqa: E402
from shorthaul_agent.validation import validate_instance  # noqa: E402


DEFAULT_REQUEST = (
    "请把上传的业务导出表自动对齐为短途运输调度输入，并生成一个可求解方案。"
    "目标优先降低总成本，其次提升自有车周转率；容器允许使用，外部车只作为兜底。"
)


@dataclass
class ProviderCandidate:
    name: str
    provider: str
    base_url: str
    model: str
    api_key_env: str
    api_key: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark LLM ingestion providers on a messy short-haul upload.")
    parser.add_argument("--sample-dir", default="examples/messy_upload", help="Folder containing messy upload files.")
    parser.add_argument("--output-dir", default="outputs_llm_ingestion_benchmark", help="Folder for benchmark reports.")
    parser.add_argument("--request", default=DEFAULT_REQUEST, help="Natural-language scheduling request.")
    parser.add_argument("--date", default="2024-12-16", help="Planning date passed to the ingestion agent.")
    parser.add_argument("--instance-id", default="llm-ingestion-benchmark", help="Instance id for generated payloads.")
    parser.add_argument("--timeout-seconds", type=int, default=120, help="Per-model LLM request timeout.")
    parser.add_argument("--debug-errors", action="store_true", help="Include traceback snippets in the local benchmark report.")
    parser.add_argument("--prefer-cpsat", action="store_true", help="Use CP-SAT for the final solve. Default uses heuristic for speed.")
    parser.add_argument(
        "--providers-json",
        default="",
        help=(
            "Optional JSON list of providers. Each item can contain name, base_url, model, "
            "api_key_env, and provider. Environment variable SHORT_HAUL_LLM_BENCHMARK_PROVIDERS "
            "uses the same format."
        ),
    )
    args = parser.parse_args()

    sample_dir = Path(args.sample_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = _load_sample_files(sample_dir)
    route = _route_file_batch(files)
    candidates = discover_candidates(args.providers_json)
    if not candidates:
        summary = {
            "status": "skipped",
            "reason": "No provider API keys were found in environment variables.",
            "sample_dir": str(sample_dir),
            "router": route.__dict__,
            "expected_env_vars": [
                "DEEPSEEK_API_KEY",
                "DASHSCOPE_API_KEY",
                "OPENAI_API_KEY",
                "MOONSHOT_API_KEY",
                "ZHIPU_API_KEY",
                "OPENROUTER_API_KEY",
                "SHORT_HAUL_LLM_BENCHMARK_PROVIDERS",
            ],
        }
        _write_reports(output_dir, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    results = []
    for candidate in candidates:
        print(f"==> {candidate.name} / {candidate.model}")
        results.append(
            evaluate_candidate(
                candidate,
                files,
                request_text=args.request,
                instance_id=args.instance_id,
                date=args.date,
                timeout_seconds=args.timeout_seconds,
                prefer_cpsat=args.prefer_cpsat,
                debug_errors=args.debug_errors,
            )
        )

    ranked = sorted(results, key=lambda item: (-item["score"], item["latency_seconds"]))
    summary = {
        "status": "ok",
        "sample_dir": str(sample_dir),
        "router": route.__dict__,
        "prefer_cpsat": args.prefer_cpsat,
        "providers_tested": len(results),
        "best_provider": ranked[0]["provider"] if ranked else "",
        "best_model": ranked[0]["model"] if ranked else "",
        "results": ranked,
        "recommendation": build_recommendation(ranked),
    }
    _write_reports(output_dir, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def discover_candidates(providers_json: str = "") -> list[ProviderCandidate]:
    configured = providers_json or os.getenv("SHORT_HAUL_LLM_BENCHMARK_PROVIDERS", "")
    if configured:
        return [_candidate_from_mapping(item) for item in json.loads(configured)]

    specs = [
        {
            "name": "DeepSeek",
            "api_key_env": "DEEPSEEK_API_KEY",
            "base_url_env": "DEEPSEEK_BASE_URL",
            "model_env": "DEEPSEEK_MODEL",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-v4-flash",
        },
        {
            "name": "Qwen / DashScope",
            "api_key_env": "DASHSCOPE_API_KEY",
            "base_url_env": "DASHSCOPE_BASE_URL",
            "model_env": "DASHSCOPE_MODEL",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen3.6-flash",
        },
        {
            "name": "Google Gemini",
            "api_key_env": "GEMINI_API_KEY",
            "base_url_env": "GEMINI_BASE_URL",
            "model_env": "GEMINI_MODEL",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "model": "gemini-2.5-flash",
        },
        {
            "name": "OpenAI",
            "api_key_env": "OPENAI_API_KEY",
            "base_url_env": "OPENAI_BASE_URL",
            "model_env": "OPENAI_MODEL",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini",
            "provider": "openai",
        },
        {
            "name": "Moonshot / Kimi",
            "api_key_env": "MOONSHOT_API_KEY",
            "base_url_env": "MOONSHOT_BASE_URL",
            "model_env": "MOONSHOT_MODEL",
            "base_url": "https://api.moonshot.cn/v1",
            "model": "kimi-k2-turbo-preview",
        },
        {
            "name": "Zhipu GLM",
            "api_key_env": "ZHIPU_API_KEY",
            "base_url_env": "ZHIPU_BASE_URL",
            "model_env": "ZHIPU_MODEL",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-4.7-flash",
        },
        {
            "name": "OpenRouter",
            "api_key_env": "OPENROUTER_API_KEY",
            "base_url_env": "OPENROUTER_BASE_URL",
            "model_env": "OPENROUTER_MODEL",
            "base_url": "https://openrouter.ai/api/v1",
            "model": "google/gemini-2.5-flash",
        },
        {
            "name": "SiliconFlow",
            "api_key_env": "SILICONFLOW_API_KEY",
            "base_url_env": "SILICONFLOW_BASE_URL",
            "model_env": "SILICONFLOW_MODEL",
            "base_url": "https://api.siliconflow.cn/v1",
            "model": "Qwen/Qwen2.5-72B-Instruct",
        },
    ]
    candidates = []
    for spec in specs:
        api_key = os.getenv(spec["api_key_env"], "")
        if not api_key:
            continue
        candidates.append(
            ProviderCandidate(
                name=spec["name"],
                provider=spec.get("provider", "openai_compatible"),
                base_url=os.getenv(spec["base_url_env"], spec["base_url"]),
                model=os.getenv(spec["model_env"], spec["model"]),
                api_key_env=spec["api_key_env"],
                api_key=api_key,
            )
        )
    return candidates


def _candidate_from_mapping(item: dict[str, Any]) -> ProviderCandidate:
    api_key_env = str(item.get("api_key_env", "")).strip()
    api_key = str(item.get("api_key") or (os.getenv(api_key_env, "") if api_key_env else "")).strip()
    return ProviderCandidate(
        name=str(item.get("name") or item.get("model") or "custom-provider"),
        provider=str(item.get("provider") or "openai_compatible"),
        base_url=str(item.get("base_url") or ""),
        model=str(item.get("model") or "gpt-4.1-mini"),
        api_key_env=api_key_env,
        api_key=api_key,
    )


def evaluate_candidate(
    candidate: ProviderCandidate,
    files: list[tuple[str, bytes]],
    *,
    request_text: str,
    instance_id: str,
    date: str,
    timeout_seconds: int,
    prefer_cpsat: bool,
    debug_errors: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {
        "provider": candidate.name,
        "provider_type": candidate.provider,
        "base_url": _redact_base_url(candidate.base_url),
        "model": candidate.model,
        "api_key_env": candidate.api_key_env,
        "status": "failed",
        "score": 0,
        "latency_seconds": 0.0,
        "checks": {},
        "error": "",
    }
    try:
        agent = DataIngestionAgent(
            DataIngestionAgentConfig(
                provider=candidate.provider,
                api_key=candidate.api_key,
                base_url=candidate.base_url,
                model=candidate.model,
                timeout_seconds=timeout_seconds,
            )
        )
        payload, meta = agent.build_payload_from_files(
            files,
            request_text,
            instance_id=instance_id,
            date=date,
            prefer_cpsat=prefer_cpsat,
            config_overrides={
                "allow_container": True,
                "allow_external": True,
                "solver_time_limit_seconds": 5.0,
            },
        )
        instance = Instance.from_dict(payload["instance"])
        config = ProblemConfig(prefer_cpsat=prefer_cpsat).merged(payload.get("config_overrides", {}))
        validation = validate_instance(instance, config)
        schedule = DispatchOrchestrator(config).run(payload.get("request", request_text), instance)
        checks = score_payload(payload, validation.errors, schedule.to_dict())
        result.update(
            {
                "status": "ok" if checks["optimization_feasible"] and not validation.errors else "partial",
                "score": checks["score"],
                "checks": checks,
                "meta": _safe_meta(meta),
            }
        )
    except Exception as exc:  # noqa: BLE001 - benchmark should compare provider failures.
        result["error"] = f"{type(exc).__name__}: {exc}"
        if debug_errors:
            result["traceback"] = traceback.format_exc(limit=8)
    finally:
        result["latency_seconds"] = round(time.perf_counter() - started, 3)
    return result


def score_payload(payload: dict[str, Any], validation_errors: list[str], schedule: dict[str, Any]) -> dict[str, Any]:
    instance = payload.get("instance", {}) if isinstance(payload, dict) else {}
    fleets = instance.get("fleets", []) if isinstance(instance, dict) else []
    routes = instance.get("routes", []) if isinstance(instance, dict) else []
    forecast = instance.get("forecast", []) if isinstance(instance, dict) else []
    fleet_ids = {str(item.get("id")) for item in fleets if isinstance(item, dict)}
    route_ids = {str(item.get("id")) for item in routes if isinstance(item, dict)}
    route_fleets = {str(item.get("fleet_id")) for item in routes if isinstance(item, dict)}
    forecast_routes = {str(item.get("route_id")) for item in forecast if isinstance(item, dict)}
    solution = schedule.get("solution", {}) if isinstance(schedule, dict) else {}
    kpis = solution.get("kpis", {}) if isinstance(solution, dict) else {}
    checks = {
        "has_fleets": len(fleets) > 0,
        "has_routes": len(routes) > 0,
        "has_forecast": len(forecast) > 0,
        "route_fleets_known": bool(routes) and route_fleets.issubset(fleet_ids),
        "forecast_routes_known": bool(forecast) and forecast_routes.issubset(route_ids),
        "no_validation_errors": not validation_errors,
        "optimization_feasible": solution.get("status") == "FEASIBLE",
        "assigned_all_tasks": kpis.get("assigned_task_count") == kpis.get("task_count") and kpis.get("task_count", 0) > 0,
        "fleet_count": len(fleets),
        "route_count": len(routes),
        "forecast_bucket_count": len(forecast),
        "validation_errors": validation_errors[:8],
    }
    weighted = {
        "has_fleets": 10,
        "has_routes": 15,
        "has_forecast": 15,
        "route_fleets_known": 15,
        "forecast_routes_known": 15,
        "no_validation_errors": 10,
        "optimization_feasible": 15,
        "assigned_all_tasks": 5,
    }
    checks["score"] = sum(weight for key, weight in weighted.items() if checks[key])
    return checks


def build_recommendation(results: list[dict[str, Any]]) -> str:
    usable = [item for item in results if item.get("score", 0) >= 80]
    if not usable:
        return "No tested model reached the recommended threshold. Prefer deterministic templates or retry with a stronger instruction-following model."
    fastest = min(usable, key=lambda item: item.get("latency_seconds", 9999))
    best_score = max(item.get("score", 0) for item in usable)
    best = [item for item in usable if item.get("score", 0) == best_score]
    if len(best) == 1:
        return f"Recommended default: {best[0]['provider']} / {best[0]['model']}."
    latency_values = [item.get("latency_seconds", 0) for item in best]
    if latency_values and fastest in best and fastest.get("latency_seconds", 0) <= statistics.median(latency_values):
        return f"Recommended default: {fastest['provider']} / {fastest['model']} for the best score-speed balance."
    names = ", ".join(f"{item['provider']} / {item['model']}" for item in best)
    return f"Recommended candidates: {names}."


def _load_sample_files(sample_dir: Path) -> list[tuple[str, bytes]]:
    files = []
    for path in sorted(sample_dir.iterdir()):
        if path.suffix.lower() in {".xlsx", ".xlsm", ".xls", ".csv", ".tsv", ".txt", ".json"}:
            files.append((path.name, path.read_bytes()))
    if not files:
        raise ValueError(f"No benchmark files found in {sample_dir}")
    return files


def _write_reports(output_dir: Path, summary: dict[str, Any]) -> None:
    (output_dir / "llm_ingestion_benchmark.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [
        "# LLM Ingestion Benchmark",
        "",
        f"Status: `{summary.get('status')}`",
        f"Sample: `{summary.get('sample_dir')}`",
        "",
        "| Provider | Model | Status | Score | Latency (s) | Notes |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for item in summary.get("results", []):
        notes = item.get("error") or item.get("recommendation") or ""
        rows.append(
            f"| {item.get('provider', '')} | `{item.get('model', '')}` | {item.get('status', '')} | "
            f"{item.get('score', 0)} | {item.get('latency_seconds', 0)} | {str(notes).replace('|', '/')} |"
        )
    if summary.get("recommendation"):
        rows.extend(["", f"Recommendation: {summary['recommendation']}"])
    (output_dir / "llm_ingestion_benchmark.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _safe_meta(meta: dict[str, Any]) -> dict[str, Any]:
    safe = dict(meta or {})
    safe.pop("api_key", None)
    return safe


def _redact_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


if __name__ == "__main__":
    main()
