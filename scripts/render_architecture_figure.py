"""Render the README architecture framework figure.

The figure is intentionally generated from code so README visuals stay
reproducible when the system architecture evolves.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import fill

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets"

PALETTE = {
    "ink": "#1f2937",
    "muted": "#667085",
    "line": "#cbd5e1",
    "bg": "#f8fafc",
    "input": "#e8f1f2",
    "ingest": "#edf2fb",
    "agent": "#f5f0e6",
    "solver": "#eaf4ec",
    "output": "#f4eef7",
    "accent": "#2f6f73",
    "agent_line": "#9a7b4f",
    "solver_line": "#4d7c5b",
    "output_line": "#8b5a92",
}


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(13.8, 7.2), dpi=180)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.955,
        "ShortHaul Dispatch Agent: LLM + Constraint Programming Framework",
        ha="center",
        va="center",
        fontsize=14.5,
        fontweight="semibold",
        color=PALETTE["ink"],
    )
    ax.text(
        0.5,
        0.915,
        "Natural-language requirements and heterogeneous business files are aligned into a verifiable optimization pipeline.",
        ha="center",
        va="center",
        fontsize=8.8,
        color=PALETTE["muted"],
    )

    # Top row: external inputs and interfaces.
    box(ax, 0.045, 0.745, 0.145, 0.12, "External\nInterfaces", "Web UI | REST API\nCLI | Python SDK", PALETTE["input"], title_size=8.2, body_size=6.8)
    box(ax, 0.225, 0.745, 0.145, 0.12, "Business\nArtifacts", "Excel | CSV | JSON\nTXT notes", PALETTE["input"], title_size=8.2, body_size=6.8)
    box(ax, 0.405, 0.745, 0.145, 0.12, "Dispatch\nIntent", "natural language\nconstraints & goals", PALETTE["input"], title_size=8.2, body_size=6.8)
    box(ax, 0.585, 0.745, 0.145, 0.12, "Policy\nControls", "capacity | container\nweights | fallback", PALETTE["input"], title_size=8.2, body_size=6.8)

    # Data ingestion layer.
    box(
        ax,
        0.13,
        0.56,
        0.30,
        0.13,
        "Data Ingestion Router",
        "payload JSON | templates\nraw attachments | LLM-required files",
        PALETTE["ingest"],
        edge=PALETTE["accent"],
    )
    box(
        ax,
        0.50,
        0.56,
        0.30,
        0.13,
        "LLM Alignment and Schema Guard",
        "OpenAI-compatible models\nnormalized payload | dataclass validation",
        PALETTE["ingest"],
        edge=PALETTE["accent"],
    )

    # Multi-agent orchestration container.
    container(ax, 0.055, 0.295, 0.89, 0.205, "Multi-Agent Orchestration Layer", PALETTE["agent"], PALETTE["agent_line"])
    agent_specs = [
        ("Demand\nParser", "NL -> request"),
        ("Forecast\nAgent", "statistical\nbaseline"),
        ("Task\nGenerator", "full-load\nand tail tasks"),
        ("Constraint\nAudit", "capacity | time\ncompatibility"),
        ("Solver\nAgent", "CP-SAT\nportfolio"),
        ("Repair\nAgent", "fallback and\nnon-regression"),
        ("Explanation\nAgent", "KPI and route\nrationale"),
    ]
    start_x = 0.085
    step = 0.122
    for idx, (title, subtitle) in enumerate(agent_specs):
        box(ax, start_x + idx * step, 0.345, 0.095, 0.095, title, subtitle, "#fffaf0", edge=PALETTE["agent_line"], title_size=7.1, body_size=5.9)

    # Optimization and output layers.
    box(
        ax,
        0.16,
        0.105,
        0.30,
        0.12,
        "Verifiable Optimization Core",
        "OR-Tools CP-SAT | heuristic fallback\nconstraint audit",
        PALETTE["solver"],
        edge=PALETTE["solver_line"],
    )
    box(
        ax,
        0.56,
        0.105,
        0.30,
        0.12,
        "Auditable Dispatch Outputs",
        "schedule JSON | Gantt | KPI\nexport ZIP | W&B benchmark",
        PALETTE["output"],
        edge=PALETTE["output_line"],
    )

    # Arrows.
    for x0 in [0.118, 0.298, 0.478, 0.658]:
        arrow(ax, x0, 0.742, 0.28, 0.695)
    arrow(ax, 0.43, 0.62, 0.50, 0.62)
    arrow(ax, 0.65, 0.56, 0.50, 0.50)
    arrow(ax, 0.50, 0.29, 0.31, 0.225)
    arrow(ax, 0.46, 0.165, 0.56, 0.165)
    arrow(ax, 0.86, 0.165, 0.925, 0.34, connectionstyle="arc3,rad=-0.25", color=PALETTE["output_line"])
    arrow(ax, 0.61, 0.335, 0.46, 0.225, connectionstyle="arc3,rad=0.18", color=PALETTE["solver_line"])
    arrow(ax, 0.68, 0.225, 0.68, 0.29, connectionstyle="arc3,rad=0.08", color=PALETTE["solver_line"])

    ax.text(0.93, 0.405, "feedback", ha="center", va="center", fontsize=7.5, color=PALETTE["output_line"], rotation=69)
    ax.text(0.53, 0.245, "repair loop", ha="center", va="center", fontsize=7.5, color=PALETTE["solver_line"], rotation=-26)

    ax.text(
        0.5,
        0.035,
        "Design principle: LLMs interpret and align operational data; solvers produce constraint-checkable schedules.",
        ha="center",
        va="center",
        fontsize=8.7,
        color=PALETTE["muted"],
    )

    png_path = ASSET_DIR / "shorthaul_agent_framework.png"
    svg_path = ASSET_DIR / "shorthaul_agent_framework.svg"
    fig.savefig(png_path, bbox_inches="tight", pad_inches=0.06)
    fig.savefig(svg_path, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(png_path)
    print(svg_path)


def box(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    body: str,
    face: str,
    *,
    edge: str = PALETTE["line"],
    title_size: float = 9.1,
    body_size: float = 7.4,
) -> None:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        linewidth=1.05,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(patch)
    wrapped_body = "\n".join(fill(part, width=34) for part in body.split("\n"))
    ax.text(
        x + w / 2,
        y + h * 0.69,
        title,
        ha="center",
        va="center",
        fontsize=title_size,
        fontweight="semibold",
        color=PALETTE["ink"],
        linespacing=1.05,
    )
    ax.text(
        x + w / 2,
        y + h * 0.30,
        wrapped_body,
        ha="center",
        va="center",
        fontsize=body_size,
        color=PALETTE["muted"],
        linespacing=1.12,
    )


def container(ax, x: float, y: float, w: float, h: float, title: str, face: str, edge: str) -> None:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.015,rounding_size=0.014",
        linewidth=1.15,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(patch)
    ax.text(x + 0.018, y + h - 0.035, title, ha="left", va="center", fontsize=9.4, fontweight="semibold", color=PALETTE["ink"])


def arrow(
    ax,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    color: str = PALETTE["accent"],
    connectionstyle: str = "arc3,rad=0.0",
) -> None:
    patch = FancyArrowPatch(
        (x0, y0),
        (x1, y1),
        arrowstyle="-|>",
        mutation_scale=11,
        linewidth=1.0,
        color=color,
        shrinkA=3,
        shrinkB=3,
        connectionstyle=connectionstyle,
    )
    ax.add_patch(patch)


if __name__ == "__main__":
    main()
