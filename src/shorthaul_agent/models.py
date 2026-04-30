"""Data contracts shared by agents and solvers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from shorthaul_agent.time_utils import normalize_minute


@dataclass
class ObjectiveWeights:
    cost: float = 1.0
    turnover: float = 0.5
    fill_rate: float = 0.2


@dataclass
class ProblemConfig:
    vehicle_capacity: int = 1000
    container_capacity: int = 800
    max_stops: int = 3
    allow_container: bool = True
    allow_external: bool = True
    prefer_cpsat: bool = True
    set_cover_tail_threshold: int = 80
    solver_time_limit_seconds: float = 10.0
    cpsat_search_seed: int = 0
    cpsat_search_seeds: tuple[int, ...] = (0,)
    cpsat_num_workers: int = 8
    objective_weights: ObjectiveWeights = field(default_factory=ObjectiveWeights)
    milk_run_pairs: set = field(default_factory=set)

    def merged(self, overrides: Optional[dict[str, Any]]) -> "ProblemConfig":
        if not overrides:
            return self
        data = asdict(self)
        for key, value in overrides.items():
            if key == "objective_weights" and isinstance(value, dict):
                data["objective_weights"].update(value)
            elif key in data:
                data[key] = value
        if isinstance(data["objective_weights"], dict):
            data["objective_weights"] = ObjectiveWeights(**data["objective_weights"])
        if isinstance(data.get("cpsat_search_seeds"), list):
            data["cpsat_search_seeds"] = tuple(int(item) for item in data["cpsat_search_seeds"])
        return ProblemConfig(**data)


@dataclass
class Route:
    id: str
    origin: str
    destination: str
    wave: str
    latest_dispatch_minute: int
    travel_minutes: int
    fleet_id: str
    variable_cost: int = 120
    external_cost: int = 0
    external_cost_multiplier: float = 1.35

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Route":
        normalized = dict(data)
        normalized["latest_dispatch_minute"] = normalize_minute(normalized["latest_dispatch_minute"])
        return cls(**normalized)

    @property
    def tail_group_key(self) -> tuple[str, str]:
        return (self.origin, self.wave)


@dataclass
class Fleet:
    id: str
    vehicle_count: int
    fixed_cost: int = 600
    variable_cost_per_trip: int = 80
    normal_load_minutes: int = 45
    normal_unload_minutes: int = 45
    container_load_minutes: int = 20
    container_unload_minutes: int = 20

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Fleet":
        return cls(**data)


@dataclass
class ForecastBucket:
    route_id: str
    minute: int
    volume: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ForecastBucket":
        normalized = dict(data)
        normalized["minute"] = normalize_minute(normalized["minute"])
        normalized["volume"] = int(round(float(normalized["volume"])))
        return cls(**normalized)


@dataclass
class Instance:
    id: str
    date: str
    routes: list[Route]
    fleets: list[Fleet]
    forecast: list[ForecastBucket]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Instance":
        return cls(
            id=data.get("id", "shorthaul-instance"),
            date=data.get("date", ""),
            routes=[Route.from_dict(item) for item in data.get("routes", [])],
            fleets=[Fleet.from_dict(item) for item in data.get("fleets", [])],
            forecast=[ForecastBucket.from_dict(item) for item in data.get("forecast", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedRequirement:
    raw_text: str
    target_date: Optional[str] = None
    route_focus: list[str] = field(default_factory=list)
    config_overrides: dict[str, Any] = field(default_factory=dict)
    hard_constraints: list[str] = field(default_factory=list)
    soft_preferences: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        return not self.errors


@dataclass
class DispatchTask:
    id: str
    route_ids: list[str]
    origin: str
    destinations: list[str]
    wave: str
    volume: int
    earliest_minute: int
    latest_minute: int
    travel_minutes: int
    fleet_id: str
    variable_cost: int
    external_cost: int
    source: str

    @property
    def stop_count(self) -> int:
        return len(self.destinations)


@dataclass
class Vehicle:
    id: str
    fleet_id: str
    fixed_cost: int
    variable_cost_per_trip: int
    is_external: bool = False
    normal_load_minutes: int = 45
    normal_unload_minutes: int = 45
    container_load_minutes: int = 20
    container_unload_minutes: int = 20


@dataclass
class Assignment:
    task_id: str
    route_ids: list[str]
    vehicle_id: str
    fleet_id: str
    start_minute: int
    end_minute: int
    volume: int
    use_container: bool
    is_external: bool


@dataclass
class ScheduleSolution:
    status: str
    objective: float
    assignments: list[Assignment]
    kpis: dict[str, float]
    warnings: list[str] = field(default_factory=list)
    solver: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentRunResult:
    requirement: ParsedRequirement
    validation: ValidationReport
    tasks: list[DispatchTask]
    solution: ScheduleSolution
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
