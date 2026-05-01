# Contributing

## Development Setup

```powershell
$env:CONDA_OVERRIDE_CUDA='0'
& D:\miniconda3\Scripts\conda.exe create -n shorthaul-agent-exp python=3.11 -y
conda activate shorthaul-agent-exp
python -m pip install -U pip
python -m pip install -e ".[solver,llm,api,dev,experiment]"
```

Install optional tracking support only when needed:

```powershell
python -m pip install -e ".[tracking]"
```

## Local Checks

Run these before committing:

```powershell
$env:PYTHONPATH="src"
python scripts/format_check.py
python -m compileall -q src tests scripts
python scripts/smoke_test.py
pytest
```

## Experiment Hygiene

- Do not commit private D-problem data.
- Do not commit generated `outputs*` directories.
- Keep experiment configs in `experiments/`.
- Keep project-facing documentation in `docs/` and update README when commands change.
- When W&B is enabled, prefer `wandb_mode: offline` for reproducible local runs unless the run is meant to sync to a shared project.

## Commit Style

Use concise, imperative messages, for example:

- `Add optional W&B experiment tracking`
- `Document D-problem benchmark workflow`
- `Tighten task-generation tuning report`
