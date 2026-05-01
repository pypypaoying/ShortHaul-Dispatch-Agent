# Experiment Guide

This guide records the reproducible commands used by the project. All commands assume PowerShell on Windows.

## Environment

```powershell
$env:CONDA_OVERRIDE_CUDA='0'
& D:\miniconda3\Scripts\conda.exe create -n shorthaul-agent-exp python=3.11 -y
conda activate shorthaul-agent-exp
python -m pip install -U pip
python -m pip install -e ".[solver,llm,api,dev,experiment]"
```

Optional W&B:

```powershell
python -m pip install -e ".[tracking]"
```

## Validation Commands

```powershell
$env:PYTHONPATH="src"
D:\miniconda3\python.exe scripts\format_check.py
D:\miniconda3\python.exe -m compileall -q src tests scripts
D:\miniconda3\python.exe scripts\smoke_test.py
D:\miniconda3\python.exe -m pytest
```

## Main D-Problem Run

```powershell
$env:PYTHONPATH="src"
D:\miniconda3\python.exe -m shorthaul_agent.cli run-experiment --config experiments/d_problem_performance.yaml --data-dir D_PROBLEM_DATA --output-dir outputs_performance_stage
```

Expected checks:

- Result table 1 has 280 rows and no missing forecast volume.
- Result table 2 has 10080 rows and no missing package volume.
- Result tables 3 and 4 are non-empty.
- Focus routes have forecast and dispatch rows.
- Constraint audit status is `pass`.

## Baseline Comparison

```powershell
$env:PYTHONPATH="src"
D:\miniconda3\python.exe -m shorthaul_agent.cli compare-baselines --config experiments/d_problem_performance.yaml --data-dir D_PROBLEM_DATA --output-dir outputs_baseline_comparison
```

Generated files:

- `comparison_table.xlsx`
- `comparison_table.csv`
- `comparison_summary.json`
- `comparison_report.md`
- `cost_turnover_comparison.png`
- `robustness_comparison.png`

## Task-Generation Tuning

```powershell
$env:PYTHONPATH="src"
D:\miniconda3\python.exe -m shorthaul_agent.cli tune-task-generation --config experiments/d_problem_performance.yaml --data-dir D_PROBLEM_DATA --output-dir outputs_task_generation_tuning --solver-time-limit 6 --cpsat-seeds 7 --tail-strategies saving_aware,cost_aware,duration_aware,fill_aware,min_count --candidate-strategies exhaustive,beam
```

The tuning command writes a grid summary. A later formal run can reuse the best strategy by setting `task_generation_portfolio_artifact` in an experiment config.

## W&B Tracking

Use the offline config when the machine has W&B installed but does not need to sync immediately:

```powershell
$env:PYTHONPATH="src"
D:\miniconda3\python.exe -m shorthaul_agent.cli run-experiment --config experiments/d_problem_wandb.yaml --data-dir D_PROBLEM_DATA --output-dir outputs_performance_stage
```

The tracked metrics include:

- `problem2/total_cost`
- `problem2/own_vehicle_turnover`
- `problem2/external_task_count`
- `problem3/total_cost`
- `problem3/own_vehicle_turnover`
- `problem3/external_task_count`
- `constraint_audit/violation_count`
- `constraint_audit/warning_count`
- `sensitivity/worst_on_time_rate`
- `sensitivity/max_stranded_volume`
- `agent_trace/step_count`

Core output files are added as a W&B artifact when available. If `wandb` is not installed, the run continues and records a skipped tracking status in `experiment_summary.json`.

For authenticated online logging, switch the config path to `experiments/d_problem_wandb_online.yaml`.

## Latest Known KPI Baseline

| Scenario | Problem 2 Cost | Problem 2 Turnover | Problem 2 External Tasks | Problem 3 Cost | Problem 3 Turnover | Problem 3 External Tasks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Current multi-agent | 67701 | 3.1727 | 227 | 67537 | 3.1818 | 226 |
| Heuristic-only | 69577 | 3.0545 | 240 | 69577 | 3.0545 | 240 |
| Legacy pipeline | 71806 | 3.1636 | 228 | 71806 | 3.1636 | 228 |
| Paper reference | 56776 | 2.49 | n/a | 47106 | 2.62 | n/a |

The paper rows are reference targets. The current project remains an engineering baseline and should be improved through benchmarked iterations.
