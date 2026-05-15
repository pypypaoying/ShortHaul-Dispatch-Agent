"""Browser UI assets for the short-haul dispatch API."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


DEMO_INSTANCE: Dict[str, Any] = {
    "id": "shorthaul-demo",
    "date": "2024-12-16",
    "fleets": [
        {
            "id": "Fleet-3",
            "vehicle_count": 3,
            "fixed_cost": 520,
            "variable_cost_per_trip": 80,
            "normal_load_minutes": 45,
            "normal_unload_minutes": 45,
            "container_load_minutes": 20,
            "container_unload_minutes": 20,
        },
        {
            "id": "Fleet-1",
            "vehicle_count": 2,
            "fixed_cost": 480,
            "variable_cost_per_trip": 70,
            "normal_load_minutes": 45,
            "normal_unload_minutes": 45,
            "container_load_minutes": 20,
            "container_unload_minutes": 20,
        },
    ],
    "routes": [
        {
            "id": "Site-3 - Stop-83 - 0600",
            "origin": "Site-3",
            "destination": "Stop-83",
            "wave": "0600",
            "latest_dispatch_minute": 1800,
            "travel_minutes": 35,
            "fleet_id": "Fleet-3",
            "variable_cost": 150,
            "external_cost_multiplier": 1.35,
        },
        {
            "id": "Site-3 - Stop-83 - 1400",
            "origin": "Site-3",
            "destination": "Stop-83",
            "wave": "1400",
            "latest_dispatch_minute": 2280,
            "travel_minutes": 35,
            "fleet_id": "Fleet-3",
            "variable_cost": 150,
            "external_cost_multiplier": 1.35,
        },
        {
            "id": "Site-3 - Stop-12 - 0600",
            "origin": "Site-3",
            "destination": "Stop-12",
            "wave": "0600",
            "latest_dispatch_minute": 1800,
            "travel_minutes": 25,
            "fleet_id": "Fleet-3",
            "variable_cost": 120,
            "external_cost_multiplier": 1.35,
        },
        {
            "id": "Site-3 - Stop-27 - 0600",
            "origin": "Site-3",
            "destination": "Stop-27",
            "wave": "0600",
            "latest_dispatch_minute": 1800,
            "travel_minutes": 30,
            "fleet_id": "Fleet-3",
            "variable_cost": 130,
            "external_cost_multiplier": 1.35,
        },
        {
            "id": "Site-1 - Stop-9 - 0600",
            "origin": "Site-1",
            "destination": "Stop-9",
            "wave": "0600",
            "latest_dispatch_minute": 1800,
            "travel_minutes": 28,
            "fleet_id": "Fleet-1",
            "variable_cost": 110,
            "external_cost_multiplier": 1.35,
        },
    ],
    "forecast": [
        {"route_id": "Site-3 - Stop-83 - 0600", "minute": 1380, "volume": 600},
        {"route_id": "Site-3 - Stop-83 - 0600", "minute": 1460, "volume": 500},
        {"route_id": "Site-3 - Stop-83 - 0600", "minute": 1540, "volume": 700},
        {"route_id": "Site-3 - Stop-83 - 0600", "minute": 1680, "volume": 450},
        {"route_id": "Site-3 - Stop-83 - 1400", "minute": 2100, "volume": 750},
        {"route_id": "Site-3 - Stop-83 - 1400", "minute": 2190, "volume": 500},
        {"route_id": "Site-3 - Stop-83 - 1400", "minute": 2250, "volume": 300},
        {"route_id": "Site-3 - Stop-12 - 0600", "minute": 1430, "volume": 400},
        {"route_id": "Site-3 - Stop-12 - 0600", "minute": 1600, "volume": 500},
        {"route_id": "Site-3 - Stop-27 - 0600", "minute": 1500, "volume": 300},
        {"route_id": "Site-3 - Stop-27 - 0600", "minute": 1650, "volume": 500},
        {"route_id": "Site-1 - Stop-9 - 0600", "minute": 1440, "volume": 900},
        {"route_id": "Site-1 - Stop-9 - 0600", "minute": 1710, "volume": 450},
    ],
}

DEMO_REQUEST_ZH = (
    "请为 2024-12-16 的短途运输任务生成调度方案。目标是降低总成本、提升自有车周转率，"
    "允许使用容器，并重点关注 Site-3 - Stop-83 线路。"
)

DEMO_REQUEST_EN = (
    "Schedule the 2024-12-16 short-haul dispatch plan. Minimize total cost, "
    "increase owned-vehicle turnover, allow containers, and focus on Site-3 - Stop-83 routes."
)

DEMO_REQUEST = DEMO_REQUEST_ZH

DEMO_CONFIG_OVERRIDES: Dict[str, Any] = {
    "vehicle_capacity": 1000,
    "container_capacity": 800,
    "max_stops": 3,
    "allow_container": True,
    "allow_external": True,
    "tail_cover_strategy": "cost_aware",
    "tail_candidate_strategy": "exhaustive",
    "objective_weights": {"cost": 1.0, "turnover": 0.5, "fill_rate": 0.2},
}


def demo_payload() -> Dict[str, Any]:
    return {
        "request": DEMO_REQUEST,
        "request_i18n": {"zh": DEMO_REQUEST_ZH, "en": DEMO_REQUEST_EN},
        "instance": deepcopy(DEMO_INSTANCE),
        "prefer_cpsat": True,
        "config_overrides": deepcopy(DEMO_CONFIG_OVERRIDES),
    }


def render_dashboard_html() -> str:
    return DASHBOARD_HTML


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ShortHaul Dispatch Agent</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #667085;
      --line: #d7dce3;
      --accent: #0f766e;
      --accent-2: #1d4ed8;
      --danger: #b42318;
      --own: #0f766e;
      --external: #c2410c;
      --container: #4f46e5;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
    }
    header {
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 28px;
      background: #111827;
      color: #fff;
      border-bottom: 1px solid #020617;
    }
    header h1 { margin: 0; font-size: 18px; font-weight: 680; }
    header .meta { color: #cbd5e1; font-size: 13px; }
    .header-actions { display: flex; align-items: center; gap: 14px; }
    .language-select {
      width: auto;
      min-width: 112px;
      border-color: #334155;
      background: #1f2937;
      color: #fff;
      padding: 6px 8px;
    }
    main {
      display: grid;
      grid-template-columns: 420px minmax(0, 1fr);
      gap: 16px;
      padding: 16px;
      max-width: 1500px;
      margin: 0 auto;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    section h2 {
      margin: 0;
      padding: 12px 14px;
      font-size: 14px;
      border-bottom: 1px solid var(--line);
      background: #fafbfc;
    }
    .left, .right { display: flex; flex-direction: column; gap: 16px; }
    .body { padding: 14px; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    label { display: block; color: var(--muted); font-size: 12px; margin-bottom: 5px; }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 8px 9px;
      font: inherit;
    }
    textarea { resize: vertical; min-height: 96px; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
    .json-editor { min-height: 260px; font-size: 12px; line-height: 1.5; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; }
    button {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 8px 10px;
      font-weight: 640;
      cursor: pointer;
    }
    button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
    button:disabled { opacity: 0.55; cursor: wait; }
    .toggle { display: flex; align-items: center; gap: 8px; }
    .toggle input { width: auto; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(5, minmax(130px, 1fr));
      gap: 10px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fff;
    }
    .metric span { color: var(--muted); display: block; font-size: 12px; margin-bottom: 6px; }
    .metric strong { font-size: 20px; }
    .chart-shell { height: 470px; overflow: auto; border-top: 1px solid var(--line); }
    svg { display: block; min-width: 860px; }
    .status { color: var(--muted); padding: 10px 14px; border-top: 1px solid var(--line); }
    .status.error { color: var(--danger); }
    .pill-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .pill {
      border: 1px solid var(--line);
      background: #f9fafb;
      border-radius: 999px;
      padding: 5px 8px;
      color: var(--muted);
      font-size: 12px;
    }
    pre {
      margin: 0;
      max-height: 260px;
      overflow: auto;
      background: #0f172a;
      color: #dbeafe;
      border-radius: 8px;
      padding: 12px;
      font-size: 12px;
      line-height: 1.5;
    }
    .hint { color: var(--muted); font-size: 12px; margin-top: 8px; }
    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; }
      .metrics { grid-template-columns: repeat(2, minmax(130px, 1fr)); }
    }
  </style>
</head>
<body>
  <header>
    <h1>ShortHaul Dispatch Agent</h1>
    <div class="header-actions">
      <div class="meta" data-i18n="tagline">自然语言约束 + CP-SAT 调度器 + 可视化方案</div>
      <select id="language" class="language-select" aria-label="Language">
        <option value="zh">中文</option>
        <option value="en">English</option>
      </select>
    </div>
  </header>
  <main>
    <div class="left">
      <section>
        <h2 data-i18n="scenarioTitle">场景设置</h2>
        <div class="body">
          <div class="toolbar">
            <button id="loadDemo" data-i18n="loadSample">加载示例场景</button>
            <button id="run" class="primary" data-i18n="runOptimization">运行优化</button>
          </div>
          <div style="margin-top:12px">
            <label for="request" data-i18n="requestLabel">调度需求</label>
            <textarea id="request"></textarea>
          </div>
          <div class="hint" data-i18n="scenarioHint">可替换下方 JSON 中的线路、车队和预测货量，用于同类调度问题。</div>
        </div>
      </section>
      <section>
        <h2 data-i18n="constraintsTitle">约束与优化目标</h2>
        <div class="body">
          <div class="grid-2">
            <div><label data-i18n="vehicleCapacity">车辆容量</label><input id="vehicleCapacity" type="number" value="1000" /></div>
            <div><label data-i18n="containerCapacity">容器容量</label><input id="containerCapacity" type="number" value="800" /></div>
            <div><label data-i18n="maxStops">最大串点数</label><input id="maxStops" type="number" value="3" /></div>
            <div><label data-i18n="tailStrategy">尾货策略</label><select id="tailStrategy">
              <option value="cost_aware" data-i18n="strategyCost">成本优先</option>
              <option value="duration_aware" data-i18n="strategyDuration">时长优先</option>
              <option value="saving_aware" data-i18n="strategySaving">节省优先</option>
              <option value="fill_aware" data-i18n="strategyFill">装载率优先</option>
              <option value="min_count" data-i18n="strategyCount">任务数优先</option>
            </select></div>
            <div class="toggle"><input id="allowContainer" type="checkbox" checked /><label for="allowContainer" data-i18n="allowContainer">允许使用容器</label></div>
            <div class="toggle"><input id="allowExternal" type="checkbox" checked /><label for="allowExternal" data-i18n="allowExternal">允许外部承运</label></div>
          </div>
          <div style="margin-top:12px" class="grid-2">
            <div><label data-i18n="costWeight">成本权重</label><input id="costWeight" type="range" min="0" max="2" step="0.1" value="1" /></div>
            <div><label data-i18n="turnoverWeight">周转权重</label><input id="turnoverWeight" type="range" min="0" max="2" step="0.1" value="0.5" /></div>
            <div><label data-i18n="fillWeight">装载率权重</label><input id="fillWeight" type="range" min="0" max="2" step="0.1" value="0.2" /></div>
            <div class="toggle"><input id="preferCpsat" type="checkbox" checked /><label for="preferCpsat" data-i18n="preferCpsat">优先使用 CP-SAT</label></div>
          </div>
        </div>
      </section>
      <section>
        <h2 data-i18n="instanceTitle">场景 JSON</h2>
        <div class="body">
          <textarea id="instance" class="json-editor"></textarea>
        </div>
      </section>
    </div>
    <div class="right">
      <section>
        <h2 data-i18n="kpiTitle">方案指标</h2>
        <div class="body">
          <div class="metrics" id="metrics"></div>
          <div class="pill-row" id="warnings" style="margin-top:12px"></div>
        </div>
        <div id="status" class="status" data-status-key="statusInitial">加载示例场景后即可运行调度器。</div>
      </section>
      <section>
        <h2 data-i18n="ganttTitle">调度甘特图</h2>
        <div class="chart-shell"><svg id="gantt" width="1080" height="420"></svg></div>
      </section>
      <section>
        <h2 data-i18n="rawTitle">原始结果</h2>
        <div class="body"><pre id="raw">{}</pre></div>
      </section>
    </div>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const status = $("status");
    let currentLang = "zh";
    let lastDemoPayload = null;
    let lastResult = null;
    let statusSuffix = "";

    const i18n = {
      zh: {
        tagline: "自然语言约束 + CP-SAT 调度器 + 可视化方案",
        scenarioTitle: "场景设置",
        loadSample: "加载示例场景",
        runOptimization: "运行优化",
        requestLabel: "调度需求",
        scenarioHint: "可替换下方 JSON 中的线路、车队和预测货量，用于同类调度问题。",
        constraintsTitle: "约束与优化目标",
        vehicleCapacity: "车辆容量",
        containerCapacity: "容器容量",
        maxStops: "最大串点数",
        tailStrategy: "尾货策略",
        strategyCost: "成本优先",
        strategyDuration: "时长优先",
        strategySaving: "节省优先",
        strategyFill: "装载率优先",
        strategyCount: "任务数优先",
        allowContainer: "允许使用容器",
        allowExternal: "允许外部承运",
        costWeight: "成本权重",
        turnoverWeight: "周转权重",
        fillWeight: "装载率权重",
        preferCpsat: "优先使用 CP-SAT",
        instanceTitle: "场景 JSON",
        kpiTitle: "方案指标",
        ganttTitle: "调度甘特图",
        rawTitle: "原始结果",
        statusInitial: "加载示例场景后即可运行调度器。",
        statusLoaded: "示例场景已加载。可修改约束或目标权重后运行优化。",
        statusSolving: "正在求解...",
        statusSolved: "求解完成",
        statusFailed: "运行失败",
        totalCost: "总成本",
        ownTurnover: "自有车周转率",
        externalTasks: "外部承运任务",
        fillRate: "装载率",
        tasks: "任务数",
        owned: "自有车",
        container: "容器",
        external: "外部承运"
      },
      en: {
        tagline: "LLM-ready constraints + CP-SAT scheduler + visual dispatch plan",
        scenarioTitle: "Scenario",
        loadSample: "Load sample scenario",
        runOptimization: "Run optimization",
        requestLabel: "Scheduling request",
        scenarioHint: "Replace the instance JSON with your own routes, fleets, and forecast buckets for similar dispatch problems.",
        constraintsTitle: "Constraints and objective",
        vehicleCapacity: "Vehicle capacity",
        containerCapacity: "Container capacity",
        maxStops: "Max milk-run stops",
        tailStrategy: "Tail strategy",
        strategyCost: "cost_aware",
        strategyDuration: "duration_aware",
        strategySaving: "saving_aware",
        strategyFill: "fill_aware",
        strategyCount: "min_count",
        allowContainer: "Allow containers",
        allowExternal: "Allow external carrier",
        costWeight: "Cost weight",
        turnoverWeight: "Turnover weight",
        fillWeight: "Fill-rate weight",
        preferCpsat: "Prefer CP-SAT",
        instanceTitle: "Instance JSON",
        kpiTitle: "Solution KPIs",
        ganttTitle: "Dispatch Gantt",
        rawTitle: "Raw solution",
        statusInitial: "Load the sample scenario and run the scheduler.",
        statusLoaded: "Sample scenario loaded. Change constraints or objective weights, then run optimization.",
        statusSolving: "Solving...",
        statusSolved: "Solved",
        statusFailed: "Run failed",
        totalCost: "Total cost",
        ownTurnover: "Own turnover",
        externalTasks: "External tasks",
        fillRate: "Fill rate",
        tasks: "Tasks",
        owned: "owned",
        container: "container",
        external: "external"
      }
    };

    function t(key) {
      return (i18n[currentLang] && i18n[currentLang][key]) || i18n.en[key] || key;
    }

    function applyLanguage() {
      document.documentElement.lang = currentLang === "zh" ? "zh-CN" : "en";
      document.querySelectorAll("[data-i18n]").forEach((node) => {
        node.textContent = t(node.dataset.i18n);
      });
      const statusKey = status.dataset.statusKey || "statusInitial";
      status.textContent = statusSuffix ? `${t(statusKey)}：${statusSuffix}` : t(statusKey);
      if (lastDemoPayload) {
        maybeUpdateSampleRequest();
      }
      if (lastResult) {
        renderSolution(lastResult);
      }
    }

    function setStatusKey(key, isError = false, suffix = "") {
      status.dataset.statusKey = key;
      statusSuffix = suffix;
      status.textContent = statusSuffix ? `${t(key)}：${statusSuffix}` : t(key);
      status.className = isError ? "status error" : "status";
    }

    function setStatusText(text, isError = false) {
      status.dataset.statusKey = "";
      statusSuffix = "";
      status.textContent = text;
      status.className = isError ? "status error" : "status";
    }

    function sampleRequestForLanguage(payload = lastDemoPayload) {
      if (!payload) {
        return "";
      }
      return (payload.request_i18n && payload.request_i18n[currentLang]) || payload.request || "";
    }

    function maybeUpdateSampleRequest() {
      const translations = Object.values(lastDemoPayload.request_i18n || {});
      if (!translations.length || translations.includes($("request").value.trim())) {
        $("request").value = sampleRequestForLanguage();
      }
    }

    async function loadDemo() {
      const response = await fetch("/demo");
      const payload = await response.json();
      lastDemoPayload = payload;
      $("request").value = sampleRequestForLanguage(payload);
      $("instance").value = JSON.stringify(payload.instance, null, 2);
      const cfg = payload.config_overrides || {};
      $("vehicleCapacity").value = cfg.vehicle_capacity || 1000;
      $("containerCapacity").value = cfg.container_capacity || 800;
      $("maxStops").value = cfg.max_stops || 3;
      $("tailStrategy").value = cfg.tail_cover_strategy || "cost_aware";
      $("allowContainer").checked = cfg.allow_container !== false;
      $("allowExternal").checked = cfg.allow_external !== false;
      $("preferCpsat").checked = payload.prefer_cpsat !== false;
      const weights = cfg.objective_weights || {};
      $("costWeight").value = weights.cost || 1;
      $("turnoverWeight").value = weights.turnover || 0.5;
      $("fillWeight").value = weights.fill_rate || 0.2;
      setStatusKey("statusLoaded");
    }

    function configOverrides() {
      return {
        vehicle_capacity: Number($("vehicleCapacity").value),
        container_capacity: Number($("containerCapacity").value),
        max_stops: Number($("maxStops").value),
        allow_container: $("allowContainer").checked,
        allow_external: $("allowExternal").checked,
        tail_cover_strategy: $("tailStrategy").value,
        objective_weights: {
          cost: Number($("costWeight").value),
          turnover: Number($("turnoverWeight").value),
          fill_rate: Number($("fillWeight").value)
        }
      };
    }

    async function runSchedule() {
      $("run").disabled = true;
      setStatusKey("statusSolving");
      try {
        const payload = {
          request: $("request").value,
          instance: JSON.parse($("instance").value),
          prefer_cpsat: $("preferCpsat").checked,
          config_overrides: configOverrides()
        };
        const response = await fetch("/schedule", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload)
        });
        const solution = await response.json();
        if (!response.ok || solution.error) {
          throw new Error(JSON.stringify(solution));
        }
        renderSolution(solution);
        setStatusKey("statusSolved", false, `${solution.solution.solver}: ${solution.solution.status}`);
      } catch (error) {
        setStatusKey("statusFailed", true, error.message);
      } finally {
        $("run").disabled = false;
      }
    }

    function renderSolution(result) {
      lastResult = result;
      const solution = result.solution || {};
      const k = solution.kpis || {};
      const metrics = [
        [t("totalCost"), k.total_cost],
        [t("ownTurnover"), k.own_vehicle_turnover],
        [t("externalTasks"), k.external_task_count],
        [t("fillRate"), k.fill_rate],
        [t("tasks"), k.task_count]
      ];
      $("metrics").innerHTML = metrics.map(([label, value]) => {
        const display = typeof value === "number" ? (label.includes("rate") ? `${(value * 100).toFixed(1)}%` : value.toFixed(value % 1 ? 2 : 0)) : "-";
        return `<div class="metric"><span>${label}</span><strong>${display}</strong></div>`;
      }).join("");
      $("warnings").innerHTML = (solution.warnings || []).slice(0, 6).map(item => `<span class="pill">${escapeHtml(item)}</span>`).join("");
      $("raw").textContent = JSON.stringify(result, null, 2);
      drawGantt(solution.assignments || []);
    }

    function drawGantt(assignments) {
      const svg = $("gantt");
      const sorted = assignments.slice().sort((a, b) => (a.dispatch_minute ?? a.start_minute) - (b.dispatch_minute ?? b.start_minute));
      const vehicles = [...new Set(sorted.map(a => a.vehicle_id))].slice(0, 18);
      const minMinute = Math.min(...sorted.map(a => a.start_minute), 1320);
      const maxMinute = Math.max(...sorted.map(a => a.end_minute), 2360);
      const width = 1080;
      const left = 190;
      const rowHeight = 28;
      const top = 38;
      const height = Math.max(420, top + vehicles.length * rowHeight + 36);
      svg.setAttribute("height", height);
      const scale = (minute) => left + ((minute - minMinute) / Math.max(maxMinute - minMinute, 1)) * (width - left - 28);
      const rows = vehicles.map((vehicle, idx) => {
        const y = top + idx * rowHeight;
        return `<text x="14" y="${y + 18}" font-size="12" fill="#475467">${escapeHtml(vehicle)}</text>
          <line x1="${left}" y1="${y + 23}" x2="${width - 20}" y2="${y + 23}" stroke="#eef1f5" />`;
      }).join("");
      const bars = sorted.filter(a => vehicles.includes(a.vehicle_id)).map(a => {
        const y = top + vehicles.indexOf(a.vehicle_id) * rowHeight + 5;
        const x = scale(a.start_minute);
        const w = Math.max(scale(a.end_minute) - x, 6);
        const color = a.is_external ? "var(--external)" : (a.use_container ? "var(--container)" : "var(--own)");
        return `<rect x="${x}" y="${y}" width="${w}" height="17" rx="4" fill="${color}" opacity="0.88">
          <title>${escapeHtml(a.task_id)} | ${a.volume}</title></rect>`;
      }).join("");
      const ticks = [];
      for (let minute = Math.ceil(minMinute / 120) * 120; minute <= maxMinute; minute += 120) {
        const x = scale(minute);
        ticks.push(`<line x1="${x}" y1="26" x2="${x}" y2="${height - 18}" stroke="#e5e7eb" />
          <text x="${x - 18}" y="18" font-size="11" fill="#667085">${timeLabel(minute)}</text>`);
      }
      const legend = `<rect x="14" y="${height - 28}" width="12" height="12" fill="var(--own)" rx="3" />
        <text x="32" y="${height - 18}" font-size="12" fill="#667085">${t("owned")}</text>
        <rect x="92" y="${height - 28}" width="12" height="12" fill="var(--container)" rx="3" />
        <text x="110" y="${height - 18}" font-size="12" fill="#667085">${t("container")}</text>
        <rect x="194" y="${height - 28}" width="12" height="12" fill="var(--external)" rx="3" />
        <text x="212" y="${height - 18}" font-size="12" fill="#667085">${t("external")}</text>`;
      svg.innerHTML = `${ticks.join("")}${rows}${bars}${legend}`;
    }

    function timeLabel(minute) {
      const day = Math.floor(minute / 1440);
      const mins = ((minute % 1440) + 1440) % 1440;
      const h = String(Math.floor(mins / 60)).padStart(2, "0");
      const m = String(mins % 60).padStart(2, "0");
      return `D+${day} ${h}:${m}`;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
    }

    $("loadDemo").addEventListener("click", loadDemo);
    $("run").addEventListener("click", runSchedule);
    $("language").addEventListener("change", (event) => {
      currentLang = event.target.value;
      applyLanguage();
    });
    applyLanguage();
    loadDemo();
  </script>
</body>
</html>
"""
