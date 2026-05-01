# Short-Haul Dispatch Multi-Agent Scheduler

LLM + constraint programming system for short-haul transportation dispatch. The project turns natural-language scheduling needs and MathorCup D-problem data into structured tasks, auditable constraints, CP-SAT or heuristic schedules, result tables, reports, charts, and optional Weights & Biases experiment logs.

## What This Repository Delivers

- Multi-agent dispatch workflow: demand parsing, forecasting, task generation, constraint audit, solver call, repair, and explanation.
- Real D-problem experiment pipeline: Excel adapters, result table export, KPI summary, sensitivity analysis, focus-route report, and Gantt charts.
- Verifiable optimization backend: OR-Tools CP-SAT portfolio with heuristic fallback and deterministic repair logic.
- Baseline comparison tooling: paper reference, current multi-agent run, heuristic-only run, optional legacy run, and comparison plots.
- Optional W&B tracking: experiment metrics and output artifacts can be logged without making W&B a hard runtime dependency.
- CI-ready engineering layout with smoke tests, unit tests, format guard, and compile checks.

## Repository Layout

```text
.
|-- .github/workflows/ci.yml       # GitHub Actions: format, compile, smoke, pytest
|-- docs/                          # Architecture and experiment guides
|-- examples/                      # Small public JSON/text scheduling example
|-- experiments/                   # Reproducible YAML experiment configs
|-- reports/                       # Technical report drafts and generated report assets
|-- scripts/                       # Smoke test and format guard
|-- src/shorthaul_agent/           # Package source code
|   |-- agents.py                  # Natural-language scheduling orchestrator agents
|   |-- api.py                     # FastAPI showcase endpoints
|   |-- baseline_comparison.py     # Benchmark comparison runner
|   |-- cli.py                     # Command-line entrypoint
|   |-- experiment.py              # D-problem experiment workflow
|   |-- tracking.py                # Optional W&B logging
|   |-- solvers/                   # CP-SAT, heuristic, and task-generation logic
|   `-- models.py                  # Shared data structures
|-- tests/                         # Unit and integration tests
|-- MC25002885-D.pdf               # Original modeling paper/report PDF
|-- pyproject.toml
`-- README.md
```

Private competition data and generated outputs are intentionally excluded from Git. Keep the local D-problem folder and `outputs*` directories on the experiment machine.

## Installation

Windows + conda, matching the current experiment machine:

```powershell
$env:CONDA_OVERRIDE_CUDA='0'
& D:\miniconda3\Scripts\conda.exe create -n shorthaul-agent-exp python=3.11 -y
conda activate shorthaul-agent-exp
python -m pip install -U pip
python -m pip install -e ".[solver,llm,api,dev,experiment]"
```

Optional W&B support:

```powershell
python -m pip install -e ".[tracking]"
```

For local source-tree execution without installing the package:

```powershell
$env:PYTHONPATH="src"
```

## Quick Smoke Test

```powershell
$env:PYTHONPATH="src"
python scripts/smoke_test.py
pytest
```

Run the small public example:

```powershell
$env:PYTHONPATH="src"
python -m shorthaul_agent.cli --instance examples/sample_instance.json --request examples/sample_request.txt --output examples/sample_solution.json
```

## D-Problem Experiment

Run the current performance configuration:

```powershell
$env:PYTHONPATH="src"
D:\miniconda3\python.exe -m shorthaul_agent.cli run-experiment --config experiments/d_problem_performance.yaml --data-dir D_PROBLEM_DATA --output-dir outputs_performance_stage
```

Main outputs:

- `result_table_1.xlsx`
- `result_table_2.xlsx`
- `result_table_3.xlsx`
- `result_table_4.xlsx`
- `experiment_summary.json`
- `experiment_report.md`
- `constraint_audit.json`
- `constraint_audit.md`
- `sensitivity_analysis.csv`
- `sensitivity_analysis.xlsx`
- `focus_routes_report.md`
- `gantt_problem2.png`
- `gantt_problem3.png`
- `sensitivity_on_time.png`

Run baseline comparison:

```powershell
$env:PYTHONPATH="src"
D:\miniconda3\python.exe -m shorthaul_agent.cli compare-baselines --config experiments/d_problem_performance.yaml --data-dir D_PROBLEM_DATA --output-dir outputs_baseline_comparison
```

Run task-generation tuning:

```powershell
$env:PYTHONPATH="src"
D:\miniconda3\python.exe -m shorthaul_agent.cli tune-task-generation --config experiments/d_problem_performance.yaml --data-dir D_PROBLEM_DATA --output-dir outputs_task_generation_tuning --solver-time-limit 6 --cpsat-seeds 7 --tail-strategies saving_aware,cost_aware,duration_aware,fill_aware,min_count --candidate-strategies exhaustive,beam
```

Replace `D_PROBLEM_DATA` with the local competition data folder path.

## Current Benchmark Status

The project is an engineering reproduction and multi-agent optimization baseline, not an exact paper reimplementation. The current validated performance run is:

| Scenario | Problem 2 Cost | Problem 2 Turnover | Problem 3 Cost | Problem 3 Turnover |
| --- | ---: | ---: | ---: | ---: |
| Paper reference | 56776 | 2.49 | 47106 | 2.62 |
| Current multi-agent run | 67701 | 3.1727 | 67537 | 3.1818 |
| Heuristic-only run | 69577 | 3.0545 | 69577 | 3.0545 |
| Legacy pipeline run | 71806 | 3.1636 | 71806 | 3.1636 |

Compared with the legacy pipeline, the current multi-agent solver reduced cost by `4105` for problem 2 and `4269` for problem 3 in the latest comparison run. The latest task-generation sweep found `exhaustive_duration_aware` as the best short-run problem-2 strategy, with problem-2 cost `67615` and problem-3 cost `67570`.

## Optional W&B Tracking

Install the optional dependency:

```powershell
python -m pip install -e ".[tracking]"
```

Offline tracking configuration is provided in `experiments/d_problem_wandb.yaml`:

```powershell
$env:PYTHONPATH="src"
D:\miniconda3\python.exe -m shorthaul_agent.cli run-experiment --config experiments/d_problem_wandb.yaml --data-dir D_PROBLEM_DATA --output-dir outputs_performance_stage
```

Useful environment variables:

```powershell
$env:WANDB_PROJECT="shorthaul-dispatch-agent"
$env:WANDB_MODE="offline"
$env:WANDB_API_KEY="your-key-for-online-runs"
```

When W&B is not installed or cannot authenticate, the experiment still finishes. The skip or failure reason is written to `experiment_summary.json` under `tracking`.

For authenticated online runs, use `experiments/d_problem_wandb_online.yaml`. It is the same performance experiment with `wandb_mode: online`.

On Windows, use UTF-8 mode for online W&B runs if the workspace path contains non-ASCII characters:

```powershell
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
```

## API Showcase

```powershell
$env:PYTHONPATH="src"
uvicorn shorthaul_agent.api:app --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /health`
- `POST /schedule`
- `POST /experiments/d-problem`
- `POST /experiments/from-config`
- `GET /experiments`
- `GET /reports/{report_name}`
- `POST /validate`

## CI

GitHub Actions runs on `push` and `pull_request`:

```powershell
python scripts/format_check.py
python -m compileall -q src tests scripts
python scripts/smoke_test.py
pytest
```

See `docs/architecture.md` and `docs/experiments.md` for the project design and experiment protocol.
