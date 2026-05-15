"""Optional FastAPI service for the scheduling agent."""

import json
from pathlib import Path
from typing import Any, Dict

from shorthaul_agent import DispatchOrchestrator, ProblemConfig
from shorthaul_agent.experiment import load_experiment_config, run_experiment
from shorthaul_agent.external_io import CSV_TEMPLATES, build_payload_from_csv_dir, schema_payload
from shorthaul_agent.models import Instance
from shorthaul_agent.validation import validate_instance
from shorthaul_agent.web_ui import demo_payload, render_dashboard_html


def create_app():
    try:
        from fastapi import Body, FastAPI
        from fastapi.responses import HTMLResponse
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError("Install the API extra first: pip install -e '.[api]'") from exc

    class ScheduleRequest(BaseModel):
        request: str = Field(..., description="Natural-language dispatch request.")
        instance: Dict[str, Any] = Field(..., description="Short-haul instance JSON.")
        prefer_cpsat: bool = True
        config_overrides: Dict[str, Any] = Field(default_factory=dict, description="ProblemConfig overrides and objective weights.")

    class ExperimentRequest(BaseModel):
        data_dir: str = "D_PROBLEM_DATA"
        output_dir: str = "outputs"
        prefer_cpsat: bool = True

    class CsvScheduleRequest(BaseModel):
        data_dir: str = Field(..., description="Server-local folder containing fleets.csv, routes.csv, and forecast.csv.")
        request: str = Field(..., description="Natural-language dispatch request.")
        instance_id: str = "external-instance"
        date: str = ""
        prefer_cpsat: bool = True
        config_overrides: Dict[str, Any] = Field(default_factory=dict)

    app = FastAPI(
        title="Short-haul Dispatch Agent",
        version="0.1.0",
        description="LLM + constraint programming multi-agent scheduler for short-haul transportation.",
    )

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        return HTMLResponse(render_dashboard_html())

    @app.get("/demo")
    def demo() -> Dict[str, Any]:
        return demo_payload()

    @app.get("/schema")
    def schema() -> Dict[str, Any]:
        return schema_payload()

    @app.get("/templates")
    def templates() -> Dict[str, str]:
        return CSV_TEMPLATES

    @app.get("/experiments")
    def experiments() -> Dict[str, Any]:
        configs_dir = Path("experiments")
        configs = sorted(str(path) for path in configs_dir.glob("*.yaml")) if configs_dir.exists() else []
        return {"configs": configs, "default": "experiments/d_problem_baseline.yaml"}

    @app.get("/reports/{report_name}")
    def report(report_name: str, output_dir: str = "outputs") -> Dict[str, Any]:
        allowed = {
            "experiment_summary.json",
            "experiment_report.md",
            "constraint_audit.json",
            "constraint_audit.md",
            "focus_routes_report.md",
            "comparison_summary.json",
            "comparison_report.md",
        }
        if report_name not in allowed:
            return {"error": "unsupported report", "allowed": sorted(allowed)}
        path = Path(output_dir) / report_name
        if not path.exists():
            return {"error": "report not found", "path": str(path)}
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        return {"path": str(path), "content": path.read_text(encoding="utf-8")}

    @app.post("/validate")
    def validate(payload: ExperimentRequest = Body(...)) -> Dict[str, Any]:
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

    @app.post("/validate-instance")
    def validate_instance_payload(payload: ScheduleRequest = Body(...)) -> Dict[str, Any]:
        instance = Instance.from_dict(payload.instance)
        config = ProblemConfig(prefer_cpsat=payload.prefer_cpsat).merged(payload.config_overrides)
        report = validate_instance(instance, config)
        return {"status": "ok" if report.is_ok else "error", "errors": report.errors, "warnings": report.warnings}

    @app.post("/schedule")
    def schedule(payload: ScheduleRequest = Body(...)) -> Dict[str, Any]:
        instance = Instance.from_dict(payload.instance)
        config = ProblemConfig(prefer_cpsat=payload.prefer_cpsat).merged(payload.config_overrides)
        return DispatchOrchestrator(config).run(payload.request, instance).to_dict()

    @app.post("/schedule/from-csv-dir")
    def schedule_from_csv_dir(payload: CsvScheduleRequest = Body(...)) -> Dict[str, Any]:
        schedule_payload = build_payload_from_csv_dir(
            payload.data_dir,
            payload.request,
            instance_id=payload.instance_id,
            date=payload.date,
            prefer_cpsat=payload.prefer_cpsat,
            config_overrides=payload.config_overrides,
        )
        instance = Instance.from_dict(schedule_payload["instance"])
        config = ProblemConfig(prefer_cpsat=schedule_payload["prefer_cpsat"]).merged(schedule_payload["config_overrides"])
        return DispatchOrchestrator(config).run(schedule_payload["request"], instance).to_dict()

    @app.post("/experiments/d-problem")
    def run_d_problem(payload: ExperimentRequest = Body(...)) -> Dict[str, Any]:
        return run_experiment(Path(payload.data_dir), Path(payload.output_dir), prefer_cpsat=payload.prefer_cpsat)

    @app.post("/experiments/from-config")
    def run_from_config(config_path: str = "experiments/d_problem_baseline.yaml") -> Dict[str, Any]:
        config = load_experiment_config(Path(config_path))
        return run_experiment(Path(config.data_dir), Path(config.output_dir), prefer_cpsat=config.prefer_cpsat, config_path=Path(config_path))

    return app


app = create_app()
