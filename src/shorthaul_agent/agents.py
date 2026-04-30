"""Multi-agent orchestration for short-haul dispatch scheduling."""

from __future__ import annotations

from shorthaul_agent.models import AgentRunResult, Instance, ParsedRequirement, ProblemConfig, ScheduleSolution, ValidationReport
from shorthaul_agent.parsing import RequirementParser
from shorthaul_agent.solvers import CpSatScheduler, HeuristicScheduler, generate_dispatch_tasks
from shorthaul_agent.time_utils import format_minutes
from shorthaul_agent.validation import validate_instance, validate_tasks


class RequirementParserAgent:
    name = "需求解析 Agent"

    def __init__(self) -> None:
        self.parser = RequirementParser()

    def run(self, request_text: str) -> ParsedRequirement:
        return self.parser.parse(request_text)


class ConstraintCheckerAgent:
    name = "约束检查 Agent"

    def run_instance(self, instance: Instance, config: ProblemConfig) -> ValidationReport:
        return validate_instance(instance, config)

    def run_tasks(self, tasks, config: ProblemConfig) -> ValidationReport:
        return validate_tasks(tasks, config)


class SolverAgent:
    name = "求解器调用 Agent"

    def run(self, instance: Instance, config: ProblemConfig) -> tuple[list, ScheduleSolution]:
        tasks = generate_dispatch_tasks(instance, config)
        if config.prefer_cpsat and CpSatScheduler.available():
            solution = CpSatScheduler().solve(instance, tasks, config)
        else:
            solution = HeuristicScheduler().solve(instance, tasks, config)
            if config.prefer_cpsat:
                solution.warnings.append("OR-Tools is not installed; used heuristic fallback.")
        return tasks, solution


class RepairAgent:
    name = "异常修复 Agent"

    def run(self, validation: ValidationReport, config: ProblemConfig) -> tuple[ProblemConfig, list[str]]:
        actions: list[str] = []
        repaired = config
        if validation.errors:
            actions.append("发现硬错误，未自动放松约束；请修复实例数据。")
        if not config.allow_external:
            repaired = config.merged({"allow_external": True})
            actions.append("已启用外部承运兜底，避免车辆资源不足导致不可行。")
        return repaired, actions


class ExplanationAgent:
    name = "方案解释 Agent"

    def run(self, result: AgentRunResult) -> str:
        solution = result.solution
        kpis = solution.kpis
        lines = [
            f"求解状态：{solution.status}（{solution.solver}）",
            f"运输任务数：{int(kpis.get('task_count', 0))}，已分配：{int(kpis.get('assigned_task_count', 0))}",
            f"自有车任务：{int(kpis.get('own_task_count', 0))}，外部承运：{int(kpis.get('external_task_count', 0))}",
            f"总成本：{kpis.get('total_cost', 0):.0f}，自有车周转率：{kpis.get('own_vehicle_turnover', 0):.2f}，装载率：{kpis.get('fill_rate', 0):.2%}",
        ]
        if solution.warnings:
            lines.append("提示：" + "；".join(solution.warnings))

        focus = set(result.requirement.route_focus)
        shown = 0
        for assignment in sorted(solution.assignments, key=lambda item: item.start_minute):
            if focus and not (focus & set(assignment.route_ids)):
                continue
            container = "是" if assignment.use_container else "否"
            carrier = "外部" if assignment.is_external else "自有"
            lines.append(
                f"- {format_minutes(assignment.start_minute)} {assignment.task_id} "
                f"({','.join(assignment.route_ids)}) -> {assignment.vehicle_id} [{carrier}] "
                f"货量 {assignment.volume}, 容器 {container}"
            )
            shown += 1
            if shown >= 12:
                break
        return "\n".join(lines)


class DispatchOrchestrator:
    """Coordinate parser, checker, solver, explanation, and repair agents."""

    def __init__(self, base_config: ProblemConfig | None = None) -> None:
        self.base_config = base_config or ProblemConfig()
        self.parser_agent = RequirementParserAgent()
        self.checker_agent = ConstraintCheckerAgent()
        self.solver_agent = SolverAgent()
        self.repair_agent = RepairAgent()
        self.explanation_agent = ExplanationAgent()

    def run(self, request_text: str, instance: Instance) -> AgentRunResult:
        requirement = self.parser_agent.run(request_text)
        config = self.base_config.merged(requirement.config_overrides)
        validation = self.checker_agent.run_instance(instance, config)
        config, repair_actions = self.repair_agent.run(validation, config)

        if validation.errors:
            empty_solution = ScheduleSolution(
                status="INVALID_INPUT",
                objective=float("inf"),
                assignments=[],
                kpis={},
                warnings=validation.errors + repair_actions,
                solver="none",
            )
            result = AgentRunResult(requirement, validation, [], empty_solution, "")
            result.explanation = self.explanation_agent.run(result)
            return result

        tasks, solution = self.solver_agent.run(instance, config)
        task_validation = self.checker_agent.run_tasks(tasks, config)
        validation.errors.extend(task_validation.errors)
        validation.warnings.extend(task_validation.warnings)
        solution.warnings.extend(validation.warnings + repair_actions)

        result = AgentRunResult(requirement, validation, tasks, solution, "")
        result.explanation = self.explanation_agent.run(result)
        return result
