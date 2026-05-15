"""Optional FastAPI service for the scheduling agent."""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from shorthaul_agent import DispatchOrchestrator, ProblemConfig
from shorthaul_agent.data_ingestion_agent import DataIngestionAgent, DataIngestionAgentConfig
from shorthaul_agent.experiment import load_experiment_config, run_experiment
from shorthaul_agent.external_io import (
    CSV_TEMPLATES,
    build_payload_from_csv_dir,
    build_payload_from_workbook,
    render_contract_html,
    render_templates_html,
    schema_payload,
    workbook_template_bytes,
)
from shorthaul_agent.models import Instance
from shorthaul_agent.validation import validate_instance
from shorthaul_agent.web_ui import demo_payload, render_dashboard_html


CSV_UPLOAD_ALIASES = {
    "fleets": "fleets.csv",
    "fleets_csv": "fleets.csv",
    "fleets.csv": "fleets.csv",
    "routes": "routes.csv",
    "routes_csv": "routes.csv",
    "routes.csv": "routes.csv",
    "forecast": "forecast.csv",
    "forecast_csv": "forecast.csv",
    "forecast.csv": "forecast.csv",
    "milk_run_pairs": "milk_run_pairs.csv",
    "milk_run_pairs_csv": "milk_run_pairs.csv",
    "milk_run_pairs.csv": "milk_run_pairs.csv",
    "config_overrides": "config_overrides.json",
    "config_overrides_json": "config_overrides.json",
    "config_overrides.json": "config_overrides.json",
}
PAYLOAD_UPLOAD_FIELDS = {"payload", "payload_json", "schedule_payload"}
PAYLOAD_UPLOAD_FILENAMES = {"payload.json", "schedule_payload.json"}
WORKBOOK_UPLOAD_FIELDS = {"workbook", "xlsx", "excel", "scenario_workbook"}
WORKBOOK_UPLOAD_SUFFIXES = {".xlsx", ".xlsm", ".xls"}
DATA_AGENT_UPLOAD_FIELDS = {"data_file", "agent_file", "business_file", "user_data"}
TEXT_UPLOAD_SUFFIXES = {".csv", ".txt", ".tsv", ".json"}


def create_app():
    try:
        from fastapi import Body, FastAPI, HTTPException, Request
        from fastapi.responses import HTMLResponse, PlainTextResponse, Response
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

    @app.get("/contract", response_class=HTMLResponse)
    def contract() -> HTMLResponse:
        return HTMLResponse(render_contract_html())

    @app.get("/templates")
    def templates() -> Dict[str, str]:
        return CSV_TEMPLATES

    @app.get("/templates/view", response_class=HTMLResponse)
    def templates_view() -> HTMLResponse:
        return HTMLResponse(render_templates_html())

    @app.get("/templates/workbook.xlsx")
    def workbook_template() -> Response:
        return Response(
            content=workbook_template_bytes(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="shorthaul_dispatch_template.xlsx"'},
        )

    @app.get("/templates/csv/{template_name}")
    def csv_template(template_name: str) -> PlainTextResponse:
        if template_name not in CSV_TEMPLATES:
            raise HTTPException(status_code=404, detail="Template not found.")
        return PlainTextResponse(
            CSV_TEMPLATES[template_name],
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{template_name}"'},
        )

    @app.get("/assets/dispatch_ui_demo.png")
    def ui_preview_asset() -> Response:
        path = Path("docs/assets/dispatch_ui_demo.png")
        if not path.exists():
            raise HTTPException(status_code=404, detail="Asset not found.")
        return Response(content=path.read_bytes(), media_type="image/png")

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
        config = ProblemConfig(prefer_cpsat=payload.prefer_cpsat)
        return (
            DispatchOrchestrator(config, explicit_overrides=payload.config_overrides)
            .run(payload.request, instance)
            .to_dict()
        )

    @app.post("/schedule/upload")
    async def schedule_upload(request: Request) -> Dict[str, Any]:
        try:
            form = await request.form()
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="Cannot parse multipart upload. Install the API extra with python-multipart enabled.",
            ) from exc

        try:
            payload, upload_meta = await _payload_from_multipart_form(form)
            instance = Instance.from_dict(payload["instance"])
            overrides = payload.get("config_overrides", {})
            config = ProblemConfig(prefer_cpsat=bool(payload.get("prefer_cpsat", True)))
            result = (
                DispatchOrchestrator(config, explicit_overrides=overrides)
                .run(str(payload.get("request", "")), instance)
                .to_dict()
            )
            result["upload"] = upload_meta
            return result
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        config = ProblemConfig(prefer_cpsat=schedule_payload["prefer_cpsat"])
        return DispatchOrchestrator(config, explicit_overrides=schedule_payload["config_overrides"]).run(
            schedule_payload["request"], instance
        ).to_dict()

    @app.post("/experiments/d-problem")
    def run_d_problem(payload: ExperimentRequest = Body(...)) -> Dict[str, Any]:
        return run_experiment(Path(payload.data_dir), Path(payload.output_dir), prefer_cpsat=payload.prefer_cpsat)

    @app.post("/experiments/from-config")
    def run_from_config(config_path: str = "experiments/d_problem_baseline.yaml") -> Dict[str, Any]:
        config = load_experiment_config(Path(config_path))
        return run_experiment(Path(config.data_dir), Path(config.output_dir), prefer_cpsat=config.prefer_cpsat, config_path=Path(config_path))

    return app


app = create_app()


async def _payload_from_multipart_form(form: Any) -> tuple[Dict[str, Any], Dict[str, Any]]:
    request_text = _form_text(form, "request") or "请根据上传数据生成短途运输调度方案。"
    instance_id = _form_text(form, "instance_id") or "uploaded-instance"
    date = _form_text(form, "date") or ""
    prefer_cpsat = _form_bool(form.get("prefer_cpsat"), default=True)
    form_overrides = _parse_json_text(_form_text(form, "config_overrides_json") or "", default={})
    force_request = _form_bool(form.get("force_request"), default=False)
    use_data_agent = _form_bool(form.get("use_data_agent"), default=False)
    raw_data_text = _form_text(form, "raw_data_text")
    agent_config = DataIngestionAgentConfig.from_values(
        api_key=_form_text(form, "data_agent_api_key"),
        base_url=_form_text(form, "data_agent_base_url"),
        model=_form_text(form, "data_agent_model"),
    )

    uploaded_payload: Optional[Dict[str, Any]] = None
    uploaded_workbook: Optional[tuple[str, bytes]] = None
    uploaded_files: Dict[str, bytes] = {}
    uploaded_names: list[str] = []
    for field_name, value in _form_items(form):
        if not _is_upload_file(value):
            continue
        raw_name = str(getattr(value, "filename", "") or "")
        if not raw_name:
            continue
        content = await value.read()
        filename = Path(raw_name).name
        filename_key = filename.lower()
        field_key = str(field_name).lower()
        suffix = Path(filename_key).suffix
        uploaded_names.append(filename)
        if field_key in DATA_AGENT_UPLOAD_FIELDS and suffix in WORKBOOK_UPLOAD_SUFFIXES:
            uploaded_workbook = (filename, content)
            use_data_agent = True
            continue
        if field_key in DATA_AGENT_UPLOAD_FIELDS and suffix in TEXT_UPLOAD_SUFFIXES:
            raw_data_text = content.decode("utf-8-sig")
            use_data_agent = True
            continue
        if field_key in PAYLOAD_UPLOAD_FIELDS or filename_key in PAYLOAD_UPLOAD_FILENAMES:
            uploaded_payload = json.loads(content.decode("utf-8-sig"))
            continue
        if field_key in WORKBOOK_UPLOAD_FIELDS or suffix in WORKBOOK_UPLOAD_SUFFIXES:
            uploaded_workbook = (filename, content)
            continue
        canonical = CSV_UPLOAD_ALIASES.get(field_key) or CSV_UPLOAD_ALIASES.get(filename_key)
        if canonical:
            uploaded_files[canonical] = content

    if uploaded_payload is not None:
        payload = dict(uploaded_payload)
        if force_request or not payload.get("request"):
            payload["request"] = request_text
        payload["prefer_cpsat"] = prefer_cpsat
        payload["config_overrides"] = _merge_dicts(payload.get("config_overrides", {}), form_overrides)
        return payload, {"source": "payload_json", "files": uploaded_names}

    if uploaded_workbook is not None:
        filename, content = uploaded_workbook
        with tempfile.TemporaryDirectory(prefix="shorthaul-workbook-upload-") as tmp_dir:
            workbook_path = Path(tmp_dir) / filename
            workbook_path.write_bytes(content)
            if use_data_agent:
                payload, agent_meta = DataIngestionAgent(agent_config).build_payload_from_workbook(
                    workbook_path,
                    request_text,
                    instance_id=instance_id,
                    date=date,
                    prefer_cpsat=prefer_cpsat,
                    config_overrides=form_overrides,
                )
                return payload, {"source": "data_agent_workbook", "files": [filename], "data_agent": agent_meta}
            payload = build_payload_from_workbook(
                workbook_path,
                request_text,
                instance_id=instance_id,
                date=date,
                prefer_cpsat=prefer_cpsat,
                config_overrides=form_overrides,
            )
        return payload, {"source": "workbook_upload", "files": [filename]}

    if use_data_agent and raw_data_text:
        payload, agent_meta = DataIngestionAgent(agent_config).build_payload_from_text(
            raw_data_text,
            request_text,
            instance_id=instance_id,
            date=date,
            prefer_cpsat=prefer_cpsat,
            config_overrides=form_overrides,
        )
        return payload, {"source": "data_agent_text", "files": uploaded_names, "data_agent": agent_meta}

    missing = [name for name in ("fleets.csv", "routes.csv", "forecast.csv") if name not in uploaded_files]
    if missing:
        raise ValueError(f"Missing required upload files: {', '.join(missing)}")

    with tempfile.TemporaryDirectory(prefix="shorthaul-upload-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        for filename, content in uploaded_files.items():
            (tmp_path / filename).write_bytes(content)
        payload = build_payload_from_csv_dir(
            tmp_path,
            request_text,
            instance_id=instance_id,
            date=date,
            prefer_cpsat=prefer_cpsat,
            config_overrides=form_overrides,
        )
    return payload, {"source": "csv_upload", "files": sorted(uploaded_files)}


def _form_text(form: Any, key: str) -> str:
    value = form.get(key)
    return "" if value is None or _is_upload_file(value) else str(value).strip()


def _form_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _form_items(form: Any) -> list[tuple[str, Any]]:
    if hasattr(form, "multi_items"):
        return list(form.multi_items())
    return list(form.items())


def _is_upload_file(value: Any) -> bool:
    return hasattr(value, "filename") and hasattr(value, "read")


def _parse_json_text(text: str, default: Dict[str, Any]) -> Dict[str, Any]:
    if not text:
        return dict(default)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("config_overrides_json must be a JSON object.")
    return value


def _merge_dicts(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base or {})
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged
