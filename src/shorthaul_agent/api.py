"""Optional FastAPI service for the scheduling agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from shorthaul_agent import DispatchOrchestrator, ProblemConfig
from shorthaul_agent.experiment import run_experiment
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

    @app.post("/schedule")
    def schedule(payload: ScheduleRequest) -> Dict[str, Any]:
        instance = Instance.from_dict(payload.instance)
        config = ProblemConfig(prefer_cpsat=payload.prefer_cpsat)
        return DispatchOrchestrator(config).run(payload.request, instance).to_dict()

    @app.post("/experiments/d-problem")
    def run_d_problem(payload: ExperimentRequest) -> Dict[str, Any]:
        return run_experiment(Path(payload.data_dir), Path(payload.output_dir), prefer_cpsat=payload.prefer_cpsat)

    return app


app = create_app()
