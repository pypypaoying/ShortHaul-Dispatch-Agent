"""Render a static README preview image for the web scheduling UI."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "assets" / "dispatch_ui_demo.png"
W, H = 1440, 900


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ["arialbd.ttf" if bold else "arial.ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_12 = load_font(12)
FONT_13 = load_font(13)
FONT_14 = load_font(14)
FONT_16 = load_font(16, bold=True)
FONT_18 = load_font(18, bold=True)
FONT_24 = load_font(24, bold=True)


def box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: str = "#ffffff", outline: str = "#d7dce3") -> None:
    draw.rounded_rectangle(xy, radius=8, fill=fill, outline=outline, width=1)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font=FONT_13, fill: str = "#172033") -> None:
    draw.text(xy, text, font=font, fill=fill)


def input_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], text: str) -> None:
    draw.rounded_rectangle(xy, radius=6, fill="#ffffff", outline="#d7dce3")
    draw.text((xy[0] + 10, xy[1] + 9), text, font=FONT_13, fill="#172033")


def metric(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], title: str, value: str, color: str = "#172033") -> None:
    box(draw, xy)
    draw.text((xy[0] + 14, xy[1] + 12), title, font=FONT_12, fill="#667085")
    draw.text((xy[0] + 14, xy[1] + 36), value, font=FONT_24, fill=color)


def render() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (W, H), "#f6f7f9")
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, W, 66), fill="#111827")
    label(draw, (30, 19), "ShortHaul Dispatch Agent", FONT_24, "#ffffff")
    label(draw, (1100, 25), "UI + REST API + CP-SAT / Heuristic", FONT_13, "#cbd5e1")

    box(draw, (24, 86, 430, 812))
    draw.rectangle((25, 87, 429, 126), fill="#fafbfc")
    label(draw, (42, 101), "Scenario & Constraints", FONT_16)
    label(draw, (42, 148), "Natural-language request", FONT_12, "#667085")
    input_box(draw, (42, 170, 410, 250), "Schedule 2024-12-16, minimize cost, allow containers...")

    draw.rounded_rectangle((42, 272, 188, 308), radius=6, fill="#ffffff", outline="#d7dce3")
    label(draw, (58, 282), "Load sample", FONT_13)
    draw.rounded_rectangle((198, 272, 410, 308), radius=6, fill="#0f766e", outline="#0f766e")
    label(draw, (232, 282), "Run optimization", FONT_13, "#ffffff")

    label(draw, (42, 334), "Vehicle capacity", FONT_12, "#667085")
    input_box(draw, (42, 354, 210, 392), "1000")
    label(draw, (232, 334), "Container capacity", FONT_12, "#667085")
    input_box(draw, (232, 354, 410, 392), "800")

    label(draw, (42, 414), "Max stops", FONT_12, "#667085")
    input_box(draw, (42, 434, 210, 472), "3")
    label(draw, (232, 414), "Tail strategy", FONT_12, "#667085")
    input_box(draw, (232, 434, 410, 472), "cost_aware")

    label(draw, (42, 500), "Objective weights", FONT_14)
    for idx, (name, value, color) in enumerate(
        [
            ("cost", 0.92, "#0f766e"),
            ("turnover", 0.58, "#1d4ed8"),
            ("fill rate", 0.36, "#4f46e5"),
        ]
    ):
        y = 532 + idx * 44
        label(draw, (42, y), name, FONT_12, "#667085")
        draw.rounded_rectangle((118, y + 3, 385, y + 13), radius=5, fill="#e5e7eb")
        draw.rounded_rectangle((118, y + 3, int(118 + 267 * value), y + 13), radius=5, fill=color)

    label(draw, (42, 676), "Instance JSON editor", FONT_14)
    draw.rounded_rectangle((42, 704, 410, 792), radius=6, fill="#0f172a", outline="#0f172a")
    label(draw, (58, 722), '{ "routes": [...], "forecast": [...], "fleets": [...] }', FONT_13, "#dbeafe")

    box(draw, (454, 86, 1414, 812))
    draw.rectangle((455, 87, 1413, 126), fill="#fafbfc")
    label(draw, (474, 101), "Optimization Result", FONT_16)

    metrics = [
        ("Status", "FEASIBLE", "#0f766e"),
        ("Total cost", "3,180", "#172033"),
        ("Own trips", "6", "#172033"),
        ("External trips", "1", "#c2410c"),
        ("Avg load", "82%", "#172033"),
    ]
    x0 = 474
    for i, (title, value, color) in enumerate(metrics):
        metric(draw, (x0 + i * 180, 148, x0 + i * 180 + 166, 224), title, value, color)

    label(draw, (474, 262), "Dispatch Gantt", FONT_18)
    draw.line((474, 300, 1378, 300), fill="#d7dce3", width=1)
    for i, tick in enumerate(["22:00", "23:00", "00:00", "01:00", "02:00", "03:00"]):
        x = 540 + i * 145
        label(draw, (x - 20, 276), tick, FONT_12, "#667085")
        draw.line((x, 300, x, 692), fill="#edf0f3", width=1)

    rows = [
        ("Owned-1", 540, 300, 190, "#0f766e", "Site-3 / Stop-83 / 0600"),
        ("Owned-2", 575, 354, 160, "#0f766e", "Site-3 / Stop-12 + Stop-27"),
        ("Owned-3", 690, 408, 210, "#4f46e5", "Container / Stop-83 / 1400"),
        ("Owned-1", 820, 462, 160, "#0f766e", "Site-1 / Stop-9"),
        ("External", 985, 516, 150, "#c2410c", "Overflow tail task"),
        ("Owned-2", 1045, 570, 190, "#4f46e5", "Container reuse"),
    ]
    for name, x, y, width, color, task in rows:
        label(draw, (480, y + 8), name, FONT_13, "#667085")
        draw.rounded_rectangle((x, y, x + width, y + 34), radius=7, fill=color)
        label(draw, (x + 12, y + 9), task, FONT_12, "#ffffff")

    label(draw, (474, 724), "Warnings: none | Solver: heuristic fallback available | Output: JSON + KPI + Gantt", FONT_13, "#667085")
    draw.rounded_rectangle((474, 756, 1378, 792), radius=6, fill="#eefaf6", outline="#b6e6d6")
    label(draw, (494, 766), "POST /schedule returns assignments, KPIs, warnings, and explanation-ready metadata.", FONT_13, "#0f766e")

    label(draw, (24, 842), "README preview asset generated by scripts/render_ui_preview.py", FONT_12, "#667085")
    img.save(OUTPUT)
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    render()
