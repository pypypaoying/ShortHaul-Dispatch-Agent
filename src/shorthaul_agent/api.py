"""Optional FastAPI service for the scheduling agent."""

import csv
import json
import tempfile
import threading
import time
import uuid
import zipfile
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from shorthaul_agent import DispatchOrchestrator, ProblemConfig
from shorthaul_agent.data_ingestion_agent import DataIngestionAgent, DataIngestionAgentConfig, _route_file_batch
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
UPLOAD_JOB_STAGES = ("prepare", "router", "align", "validate", "solve", "render")
UPLOAD_JOBS: dict[str, dict[str, Any]] = {}
UPLOAD_JOBS_LOCK = threading.Lock()
ProgressCallback = Callable[[str, str, str], None]


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

    class ExportRequest(BaseModel):
        result: Dict[str, Any] = Field(..., description="Schedule result returned by /schedule or /schedule/upload.")
        files: list[str] = Field(default_factory=lambda: ["solution_json", "assignments_csv", "kpis_json"])

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

    @app.post("/schedule/upload/jobs")
    async def schedule_upload_job(request: Request) -> Dict[str, Any]:
        try:
            form = await request.form()
            fields, file_parts = await _multipart_form_to_parts(form)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="Cannot parse multipart upload. Install the API extra with python-multipart enabled.",
            ) from exc

        job_id = _create_upload_job()
        thread = threading.Thread(
            target=_run_upload_job,
            args=(job_id, fields, file_parts),
            name=f"shorthaul-upload-{job_id[:8]}",
            daemon=True,
        )
        thread.start()
        return {"job_id": job_id, "status_url": f"/schedule/upload/jobs/{job_id}"}

    @app.get("/schedule/upload/jobs/{job_id}")
    def schedule_upload_job_status(job_id: str) -> Dict[str, Any]:
        job = _get_upload_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Upload job not found.")
        return job

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

    @app.post("/schedule/export")
    def export_schedule(payload: ExportRequest = Body(...)) -> Response:
        try:
            archive = _export_result_archive(payload.result, payload.files)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return Response(
            content=archive,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="shorthaul_schedule_export.zip"'},
        )

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
    fields, file_parts = await _multipart_form_to_parts(form)
    return _payload_from_multipart_parts(fields, file_parts)


async def _multipart_form_to_parts(form: Any) -> tuple[dict[str, str], list[tuple[str, str, bytes]]]:
    fields: dict[str, str] = {}
    files: list[tuple[str, str, bytes]] = []
    for field_name, value in _form_items(form):
        if _is_upload_file(value):
            raw_name = str(getattr(value, "filename", "") or "")
            if not raw_name:
                continue
            files.append((str(field_name), Path(raw_name).name, await value.read()))
        else:
            fields[str(field_name)] = "" if value is None else str(value).strip()
    return fields, files


def _payload_from_multipart_parts(
    fields: dict[str, str],
    file_parts: list[tuple[str, str, bytes]],
    progress: Optional[ProgressCallback] = None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    progress = progress or (lambda stage, state, label: None)
    progress("prepare", "active", "解析上传表单")
    request_text = fields.get("request", "").strip() or "请根据上传数据生成短途运输调度方案。"
    instance_id = fields.get("instance_id", "").strip() or "uploaded-instance"
    date = fields.get("date", "").strip() or ""
    prefer_cpsat = _form_bool(fields.get("prefer_cpsat"), default=True)
    form_overrides = _parse_json_text(fields.get("config_overrides_json", "") or "", default={})
    force_request = _form_bool(fields.get("force_request"), default=False)
    use_data_agent = _form_bool(fields.get("use_data_agent"), default=False)
    raw_data_text = fields.get("raw_data_text", "").strip()
    agent_config = DataIngestionAgentConfig.from_values(
        provider=fields.get("data_agent_provider", ""),
        api_key=fields.get("data_agent_api_key", ""),
        base_url=fields.get("data_agent_base_url", ""),
        model=fields.get("data_agent_model", ""),
        timeout_seconds=fields.get("data_agent_timeout_seconds", "") or None,
    )

    uploaded_payload: Optional[Dict[str, Any]] = None
    uploaded_workbook: Optional[tuple[str, bytes]] = None
    data_agent_uploads: list[tuple[str, bytes]] = []
    uploaded_files: Dict[str, bytes] = {}
    uploaded_names: list[str] = []
    for field_name, filename, content in file_parts:
        if not filename:
            continue
        filename_key = filename.lower()
        field_key = str(field_name).lower()
        suffix = Path(filename_key).suffix
        uploaded_names.append(filename)
        if field_key in DATA_AGENT_UPLOAD_FIELDS:
            data_agent_uploads.append((filename, content))
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
    progress("prepare", "done", f"{len(uploaded_names)} 个文件")

    if uploaded_payload is not None:
        progress("router", "done", "payload_json")
        progress("align", "done", "跳过")
        payload = dict(uploaded_payload)
        if force_request or not payload.get("request"):
            payload["request"] = request_text
        payload["prefer_cpsat"] = prefer_cpsat
        payload["config_overrides"] = _merge_dicts(payload.get("config_overrides", {}), form_overrides)
        return payload, {"source": "payload_json", "files": uploaded_names}

    if data_agent_uploads:
        route = _route_file_batch(data_agent_uploads)
        progress("router", "done", route.kind)
        progress("align", "active", "LLM 对齐中" if route.kind == "llm_required" else "本地适配中")
        payload, agent_meta = DataIngestionAgent(agent_config).build_payload_from_files(
            data_agent_uploads,
            request_text,
            instance_id=instance_id,
            date=date,
            prefer_cpsat=prefer_cpsat,
            config_overrides=form_overrides,
        )
        progress("align", "done", str(agent_meta.get("mode", "完成")))
        return payload, {
            "source": _data_agent_upload_source(data_agent_uploads),
            "files": [name for name, _ in data_agent_uploads],
            "data_agent": agent_meta,
        }

    if uploaded_workbook is not None:
        filename, content = uploaded_workbook
        progress("router", "done", "workbook")
        progress("align", "active", "Agent 适配中" if use_data_agent else "标准工作簿")
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
                progress("align", "done", str(agent_meta.get("mode", "完成")))
                return payload, {"source": "data_agent_workbook", "files": [filename], "data_agent": agent_meta}
            payload = build_payload_from_workbook(
                workbook_path,
                request_text,
                instance_id=instance_id,
                date=date,
                prefer_cpsat=prefer_cpsat,
                config_overrides=form_overrides,
            )
        progress("align", "done", "标准工作簿")
        return payload, {"source": "workbook_upload", "files": [filename]}

    if use_data_agent and raw_data_text:
        progress("router", "done", "text")
        progress("align", "active", "文本对齐中")
        payload, agent_meta = DataIngestionAgent(agent_config).build_payload_from_text(
            raw_data_text,
            request_text,
            instance_id=instance_id,
            date=date,
            prefer_cpsat=prefer_cpsat,
            config_overrides=form_overrides,
        )
        progress("align", "done", str(agent_meta.get("mode", "完成")))
        return payload, {"source": "data_agent_text", "files": uploaded_names, "data_agent": agent_meta}

    missing = [name for name in ("fleets.csv", "routes.csv", "forecast.csv") if name not in uploaded_files]
    if missing:
        raise ValueError(f"Missing required upload files: {', '.join(missing)}")

    progress("router", "done", "csv_bundle")
    progress("align", "done", "跳过")
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


def _data_agent_upload_source(files: list[tuple[str, bytes]]) -> str:
    if len(files) != 1:
        return "data_agent_files"
    suffix = Path(files[0][0].lower()).suffix
    if suffix in WORKBOOK_UPLOAD_SUFFIXES:
        return "data_agent_workbook"
    return "data_agent_text"


def _create_upload_job() -> str:
    job_id = uuid.uuid4().hex
    now = time.time()
    job = {
        "job_id": job_id,
        "status": "queued",
        "stage": "prepare",
        "message": "等待处理",
        "created_at": now,
        "updated_at": now,
        "stages": {
            stage: {"state": "pending", "label": "等待中"}
            for stage in UPLOAD_JOB_STAGES
        },
        "result": None,
        "error": "",
    }
    with UPLOAD_JOBS_LOCK:
        UPLOAD_JOBS[job_id] = job
    return job_id


def _get_upload_job(job_id: str) -> Optional[dict[str, Any]]:
    with UPLOAD_JOBS_LOCK:
        job = UPLOAD_JOBS.get(job_id)
        return json.loads(json.dumps(job, ensure_ascii=False)) if job is not None else None


def _set_upload_job_stage(job_id: str, stage: str, state: str, label: str) -> None:
    with UPLOAD_JOBS_LOCK:
        job = UPLOAD_JOBS.get(job_id)
        if job is None:
            return
        job["status"] = "running"
        job["stage"] = stage
        job["message"] = label
        job["updated_at"] = time.time()
        if stage in job["stages"]:
            job["stages"][stage] = {"state": state, "label": label}


def _finish_upload_job(job_id: str, result: dict[str, Any]) -> None:
    with UPLOAD_JOBS_LOCK:
        job = UPLOAD_JOBS.get(job_id)
        if job is None:
            return
        job["status"] = "completed"
        job["stage"] = "render"
        job["message"] = "完成"
        job["updated_at"] = time.time()
        job["result"] = result
        job["stages"]["render"] = {"state": "done", "label": "完成"}


def _fail_upload_job(job_id: str, stage: str, exc: Exception) -> None:
    with UPLOAD_JOBS_LOCK:
        job = UPLOAD_JOBS.get(job_id)
        if job is None:
            return
        label = str(exc)
        job["status"] = "failed"
        job["stage"] = stage if stage in UPLOAD_JOB_STAGES else "align"
        job["message"] = label
        job["updated_at"] = time.time()
        job["error"] = label
        if job["stage"] in job["stages"]:
            job["stages"][job["stage"]] = {"state": "error", "label": "失败"}


def _run_upload_job(job_id: str, fields: dict[str, str], file_parts: list[tuple[str, str, bytes]]) -> None:
    current_stage = "prepare"

    def progress(stage: str, state: str, label: str) -> None:
        nonlocal current_stage
        current_stage = stage
        _set_upload_job_stage(job_id, stage, state, label)

    try:
        payload, upload_meta = _payload_from_multipart_parts(fields, file_parts, progress=progress)
        progress("validate", "active", "校验实例")
        instance = Instance.from_dict(payload["instance"])
        overrides = payload.get("config_overrides", {})
        config = ProblemConfig(prefer_cpsat=bool(payload.get("prefer_cpsat", True)))
        validation = validate_instance(instance, config.merged(overrides))
        if validation.errors:
            raise ValueError("; ".join(validation.errors))
        progress("validate", "done", "通过")
        progress("solve", "active", "求解中")
        result = (
            DispatchOrchestrator(config, explicit_overrides=overrides)
            .run(str(payload.get("request", "")), instance)
            .to_dict()
        )
        result["upload"] = upload_meta
        solver = str(result.get("solution", {}).get("solver", "完成"))
        progress("solve", "done", solver)
        progress("render", "active", "准备结果")
        _finish_upload_job(job_id, result)
    except Exception as exc:  # noqa: BLE001 - job status must capture user-visible failures.
        _fail_upload_job(job_id, current_stage, exc)


def _export_result_archive(result: Dict[str, Any], selected_files: list[str]) -> bytes:
    allowed = set(selected_files or [])
    solution = result.get("solution", {}) if isinstance(result, dict) else {}
    assignments = solution.get("assignments", []) if isinstance(solution, dict) else []
    kpis = solution.get("kpis", {}) if isinstance(solution, dict) else {}
    upload = result.get("upload", {}) if isinstance(result, dict) else {}
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        if "solution_json" in allowed:
            archive.writestr("solution.json", json.dumps(result, ensure_ascii=False, indent=2))
        if "assignments_csv" in allowed:
            archive.writestr("assignments.csv", _assignments_csv(assignments))
        if "kpis_json" in allowed:
            archive.writestr("kpis.json", json.dumps(kpis, ensure_ascii=False, indent=2))
        if "upload_meta_json" in allowed:
            archive.writestr("upload_meta.json", json.dumps(upload, ensure_ascii=False, indent=2))
        if "warnings_txt" in allowed:
            warnings = solution.get("warnings", []) if isinstance(solution, dict) else []
            archive.writestr("warnings.txt", "\n".join(str(item) for item in warnings))
    if not buffer.tell():
        raise ValueError("No export files were selected.")
    return buffer.getvalue()


def _assignments_csv(assignments: Any) -> str:
    headers = [
        "task_id",
        "route_ids",
        "vehicle_id",
        "fleet_id",
        "start_minute",
        "end_minute",
        "dispatch_minute",
        "volume",
        "use_container",
        "is_external",
    ]
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(headers)
    if not isinstance(assignments, list):
        return "\ufeff" + buffer.getvalue()
    for item in assignments:
        if not isinstance(item, dict):
            continue
        row = []
        for key in headers:
            value = item.get(key, "")
            if isinstance(value, list):
                value = "|".join(str(part) for part in value)
            row.append(str(value))
        writer.writerow(row)
    return "\ufeff" + buffer.getvalue()
