"""Optional FastAPI service for the scheduling agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from shorthaul_agent import DispatchOrchestrator, ProblemConfig
from shorthaul_agent.experiment import load_experiment_config, run_experiment
from shorthaul_agent.models import Instance


def create_app():
    try:
        from fastapi import FastAPI
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError("Install the API extra first: pip install -e '.[api]'") from exc

    class ScheduleRequest(BaseModel):
        request: str = Field(..., description="Natural-language dispatch request.")
        instance: Dict[str, Any] = Field(..., description="Short-haul instance JSON.")
        prefer_cpsat: bool = True

    class ExperimentRequest(BaseModel):
        data_dir: str = "D题"
        output_dir: str = "outputs"
        prefer_cpsat: bool = True

    app = FastAPI(
        title="Short-haul Dispatch Agent",
        version="0.1.0",
        description="LLM + constraint programming multi-agent scheduler for short-haul transportation.",
    )

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/experiments")
    def experiments() -> Dict[str, Any]:
        configs_dir = Path("experiments")
        configs = sorted(str(path) for path in configs_dir.glob("*.yaml")) if configs_dir.exists() else []
        return {"configs": configs, "default": "experiments/d_problem_baseline.yaml"}

    @app.get("/reports/{report_name}")
    def report(report_name: str, output_dir: str = "outputs") -> Dict[str, Any]:
        allowed = {"experiment_summary.json", "experiment_report.md", "constraint_audit.json", "constraint_audit.md", "focus_routes_report.md"}
        if report_name not in allowed:
            return {"error": "unsupported report", "allowed": sorted(allowed)}
        path = Path(output_dir) / report_name
        if not path.exists():
            return {"error": "report not found", "path": str(path)}
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        return {"path": str(path), "content": path.read_text(encoding="utf-8")}

    @app.post("/validate")
    def validate(payload: ExperimentRequest) -> Dict[str, Any]:
        summary_path = Path(payload.output_dir) / "experiment_summary.json"
        audit_path = Path(payload.output_dir) / "constraint_audit.json"
        if not summary_path.exists() or not audit_path.exists():
            return {"status": "missing_outputs", "summary_exists": summary_path.exists(), "audit_exists": audit_path.exists()}
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        return {
            "status": "ok" if summary.get("constraint_audit", {}).get("status") == "pass" else "warning",
            "outputs": summary.get("outputs", {}),
            "constraint_audit": summary.get("constraint_audit", {}),
            "audit_sections": list(audit.keys()),
        }

    @app.post("/schedule")
    def schedule(payload: ScheduleRequest) -> Dict[str, Any]:
        instance = Instance.from_dict(payload.instance)
        config = ProblemConfig(prefer_cpsat=payload.prefer_cpsat)
        return DispatchOrchestrator(config).run(payload.request, instance).to_dict()

    @app.post("/experiments/d-problem")
    def run_d_problem(payload: ExperimentRequest) -> Dict[str, Any]:
        return run_experiment(Path(payload.data_dir), Path(payload.output_dir), prefer_cpsat=payload.prefer_cpsat)

    @app.post("/experiments/from-config")
    def run_from_config(config_path: str = "experiments/d_problem_baseline.yaml") -> Dict[str, Any]:
        config = load_experiment_config(Path(config_path))
        return run_experiment(Path(config.data_dir), Path(config.output_dir), prefer_cpsat=config.prefer_cpsat, config_path=Path(config_path))

    return app


app = create_app()
