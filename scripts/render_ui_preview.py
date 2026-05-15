"""Render a static README preview image for the web scheduling UI."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "assets" / "dispatch_ui_demo.png"
W, H = 1440, 900


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
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
    label(draw, (1010, 25), "中文 / English  |  REST API + CP-SAT / Heuristic", FONT_13, "#cbd5e1")

    box(draw, (24, 86, 430, 812))
    draw.rectangle((25, 87, 429, 126), fill="#fafbfc")
    label(draw, (42, 101), "场景设置与约束", FONT_16)
    label(draw, (42, 148), "调度需求", FONT_12, "#667085")
    input_box(draw, (42, 170, 410, 250), "请为 2024-12-16 生成调度方案，降低成本...")

    draw.rounded_rectangle((42, 272, 188, 308), radius=6, fill="#ffffff", outline="#d7dce3")
    label(draw, (66, 282), "加载示例", FONT_13)
    draw.rounded_rectangle((198, 272, 410, 308), radius=6, fill="#0f766e", outline="#0f766e")
    label(draw, (260, 282), "运行优化", FONT_13, "#ffffff")

    label(draw, (42, 334), "车辆容量", FONT_12, "#667085")
    input_box(draw, (42, 354, 210, 392), "1000")
    label(draw, (232, 334), "容器容量", FONT_12, "#667085")
    input_box(draw, (232, 354, 410, 392), "800")

    label(draw, (42, 414), "最大串点数", FONT_12, "#667085")
    input_box(draw, (42, 434, 210, 472), "3")
    label(draw, (232, 414), "尾货策略", FONT_12, "#667085")
    input_box(draw, (232, 434, 410, 472), "成本优先")

    label(draw, (42, 500), "优化目标权重", FONT_14)
    for idx, (name, value, color) in enumerate(
        [
            ("成本", 0.92, "#0f766e"),
            ("周转", 0.58, "#1d4ed8"),
            ("装载率", 0.36, "#4f46e5"),
        ]
    ):
        y = 532 + idx * 44
        label(draw, (42, y), name, FONT_12, "#667085")
        draw.rounded_rectangle((118, y + 3, 385, y + 13), radius=5, fill="#e5e7eb")
        draw.rounded_rectangle((118, y + 3, int(118 + 267 * value), y + 13), radius=5, fill=color)

    label(draw, (42, 676), "场景 JSON 编辑器", FONT_14)
    draw.rounded_rectangle((42, 704, 410, 792), radius=6, fill="#0f172a", outline="#0f172a")
    label(draw, (58, 722), '{ "routes": [...], "forecast": [...], "fleets": [...] }', FONT_13, "#dbeafe")

    box(draw, (454, 86, 1414, 812))
    draw.rectangle((455, 87, 1413, 126), fill="#fafbfc")
    label(draw, (474, 101), "优化结果", FONT_16)

    metrics = [
        ("状态", "FEASIBLE", "#0f766e"),
        ("总成本", "3,180", "#172033"),
        ("自有车任务", "6", "#172033"),
        ("外部承运", "1", "#c2410c"),
        ("装载率", "82%", "#172033"),
    ]
    x0 = 474
    for i, (title, value, color) in enumerate(metrics):
        metric(draw, (x0 + i * 180, 148, x0 + i * 180 + 166, 224), title, value, color)

    label(draw, (474, 262), "调度甘特图", FONT_18)
    draw.line((474, 300, 1378, 300), fill="#d7dce3", width=1)
    for i, tick in enumerate(["22:00", "23:00", "00:00", "01:00", "02:00", "03:00"]):
        x = 540 + i * 145
        label(draw, (x - 20, 276), tick, FONT_12, "#667085")
        draw.line((x, 300, x, 692), fill="#edf0f3", width=1)

    rows = [
        ("自有-1", 540, 300, 190, "#0f766e", "Site-3 / Stop-83 / 0600"),
        ("自有-2", 575, 354, 160, "#0f766e", "Site-3 / Stop-12 + Stop-27"),
        ("自有-3", 690, 408, 210, "#4f46e5", "容器 / Stop-83 / 1400"),
        ("自有-1", 820, 462, 160, "#0f766e", "Site-1 / Stop-9"),
        ("外部", 985, 516, 150, "#c2410c", "尾货兜底任务"),
        ("自有-2", 1045, 570, 190, "#4f46e5", "容器复用"),
    ]
    for name, x, y, width, color, task in rows:
        label(draw, (480, y + 8), name, FONT_13, "#667085")
        draw.rounded_rectangle((x, y, x + width, y + 34), radius=7, fill=color)
        label(draw, (x + 12, y + 9), task, FONT_12, "#ffffff")

    label(draw, (474, 724), "告警：无 | 求解器：CP-SAT / 启发式兜底 | 输出：JSON + KPI + 甘特图", FONT_13, "#667085")
    draw.rounded_rectangle((474, 756, 1378, 792), radius=6, fill="#eefaf6", outline="#b6e6d6")
    label(draw, (494, 766), "POST /schedule 返回调度任务、KPI、告警和可解释元数据。", FONT_13, "#0f766e")

    label(draw, (24, 842), "README preview asset generated by scripts/render_ui_preview.py", FONT_12, "#667085")
    img.save(OUTPUT)
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    render()
