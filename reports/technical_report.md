# Technical Report: LLM + Constraint Programming Multi-Agent Scheduler

## 1. Project Goal

This project upgrades a mathematical modeling solution into a runnable short-haul dispatch system. The system uses an LLM-oriented multi-agent layer to understand scheduling requirements, generate structured tasks, audit constraints, call a verifiable optimizer, repair weak solutions, and explain final plans.

The design principle is simple: language models handle ambiguity and workflow orchestration, while OR-Tools CP-SAT and deterministic heuristics handle the parts that must be checked, repeated, and benchmarked.

## 2. Problem Setting

The D-problem data contains:

- Route metadata.
- Historical 10-minute package volumes.
- Known daily volume estimates.
- Milk-run compatible station pairs.
- Self-owned fleet counts.
- Result table templates.

The current experiment targets:

- Result table 1: daily forecast.
- Result table 2: 10-minute forecast.
- Result table 3: problem-2 dispatch plan.
- Result table 4: problem-3 dispatch plan with container decisions.
- Problem 4: sensitivity analysis over volume bias and arrival-time shifts.

## 3. System Architecture

```mermaid
flowchart LR
    A["Scheduling request or D-problem data"] --> B["Data and demand parsing"]
    B --> C["ForecastAgent"]
    C --> D["DemandGenerationAgent"]
    D --> E["ConstraintAuditAgent"]
    E --> F["SolverAgent"]
    F --> G["RepairAgent"]
    G --> H["ConstraintAuditAgent"]
    H --> I["ExplanationAgent"]
    I --> J["Tables, KPI JSON, reports, plots, W&B"]
```

### Agent Roles

| Agent | Responsibility | Output |
| --- | --- | --- |
| `DemandParserAgent` | Convert natural-language requirements into structured scheduling requests. | structured request |
| `ForecastAgent` | Produce daily and 10-minute forecasts from historical and known volume data. | forecast tables |
| `DemandGenerationAgent` | Generate full-load tasks, tail-load tasks, and milk-run candidates. | dispatch tasks |
| `ConstraintAuditAgent` | Check capacity, time windows, station compatibility, container rules, and vehicle overlap. | audit report |
| `SolverAgent` | Run CP-SAT, heuristic fallback, and portfolio selection. | schedule solution |
| `RepairAgent` | Reduce external carriers and protect problem-3 non-regression behavior. | repaired solution |
| `ExplanationAgent` | Generate KPI comparisons, focus-route notes, reports, and summary JSON. | explanation artifacts |

## 4. Forecasting Baseline

The current forecast is a statistical baseline:

1. Start from the known daily volume.
2. Correct it with historical route-level factors.
3. Split daily demand into 10-minute buckets using historical proportions.

This baseline is intentionally lightweight. It keeps the full experiment runnable while leaving a clean plugin path for an LSTM-MLP or external forecasting model.

## 5. Task Generation

Dispatch tasks are generated in two layers:

- Full-load tasks for large route-volume chunks.
- Tail-load tasks for remaining volume.

Tail tasks can be consolidated with milk-run constraints. The generator supports several set-cover scoring strategies:

- `min_count`
- `saving_aware`
- `cost_aware`
- `duration_aware`
- `fill_aware`

The current performance configuration uses `cost_aware` with exhaustive candidates. A beam candidate mode is available for controlled search when the candidate space grows.

## 6. Solver and Repair

The solver backend has three fallback levels:

1. CP-SAT portfolio over deterministic seeds.
2. Deterministic heuristic fallback.
3. Post-solve external-carrier repair.

The CP-SAT model assigns each generated task to either a self-owned vehicle or an external carrier. It respects:

- Dispatch time windows.
- Vehicle non-overlap.
- Vehicle capacity.
- Milk-run stop limits and compatibility.
- Container capacity and handling time in problem 3.
- No-container rule for external carriers.

The repair pass searches for cheaper feasible schedules by:

- Converting external tasks into self-owned vehicle gaps.
- Swapping high-saving external tasks with lower-saving self-owned tasks.
- Relocating blocker tasks when a high-saving external task can use the released self-owned slot.

## 7. Experiment Outputs

Each full D-problem experiment writes:

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

The summary JSON is the main machine-readable artifact. It includes experiment settings, data statistics, KPIs, paper benchmark gaps, agent trace, audit status, sensitivity results, repair warnings, and optional W&B status.

## 8. Baseline Comparison

The project compares four kinds of rows:

- Paper reference KPIs.
- Current multi-agent CP-SAT portfolio run.
- Heuristic-only run.
- Optional legacy pipeline summary.

Latest validated benchmark:

| Scenario | Problem 2 Cost | Problem 2 Turnover | Problem 2 External Tasks | Problem 3 Cost | Problem 3 Turnover | Problem 3 External Tasks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Paper reference | 56776 | 2.49 | n/a | 47106 | 2.62 | n/a |
| Current multi-agent | 67701 | 3.1727 | 227 | 67547 | 3.1818 | 226 |
| Heuristic-only | 69577 | 3.0545 | 240 | 69577 | 3.0545 | 240 |
| Legacy pipeline | 71806 | 3.1636 | 228 | 71806 | 3.1636 | 228 |

The current multi-agent system is not yet an exact paper reproduction. It is a stronger engineering baseline than the legacy pipeline and provides a clearer optimization surface for future improvements.

## 9. W&B Tracking

W&B integration is optional. When enabled, the experiment logs:

- Problem 2 and problem 3 total cost.
- Self-owned vehicle turnover.
- External-carrier task count.
- Container task count.
- Constraint violation and warning counts.
- Sensitivity metrics.
- Agent trace length.
- Core output files as an artifact.

The config `experiments/d_problem_wandb.yaml` defaults to `wandb_mode: offline`, which is suitable for local reproducible runs. If `wandb` is missing or authentication fails, the experiment still completes and records the reason under `tracking` in `experiment_summary.json`.

## 10. Current Limitations

- Forecasting is still a statistical baseline, not the final LSTM-MLP model.
- The CP-SAT model is tuned for a reproducible engineering baseline, not paper-exact reconstruction.
- Current task generation still leaves a cost gap against the paper reference.
- W&B is optional and not part of CI because the repository should remain runnable without online credentials.

## 11. Next Research Directions

1. Add an LSTM-MLP forecast plugin and compare it against the statistical baseline.
2. Improve task-generation neighborhoods for tail-load consolidation.
3. Add stronger repair neighborhoods for multi-task exchanges.
4. Tune objective weights against paper reference and operational KPIs.
5. Extend API and report views for interactive demonstration.

