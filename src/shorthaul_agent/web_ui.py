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

DEMO_REQUEST = (
    "Schedule the 2024-12-16 short-haul dispatch plan. Minimize total cost, "
    "increase owned-vehicle turnover, allow containers, and focus on Site-3 - Stop-83 routes."
)

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
    <div class="meta">LLM-ready constraints + CP-SAT scheduler + visual dispatch plan</div>
  </header>
  <main>
    <div class="left">
      <section>
        <h2>Scenario</h2>
        <div class="body">
          <div class="toolbar">
            <button id="loadDemo">Load D-problem demo</button>
            <button id="run" class="primary">Run optimization</button>
          </div>
          <div style="margin-top:12px">
            <label for="request">Scheduling request</label>
            <textarea id="request"></textarea>
          </div>
          <div class="hint">Replace the instance JSON with your own routes, fleets, and forecast buckets for similar dispatch problems.</div>
        </div>
      </section>
      <section>
        <h2>Constraints and objective</h2>
        <div class="body">
          <div class="grid-2">
            <div><label>Vehicle capacity</label><input id="vehicleCapacity" type="number" value="1000" /></div>
            <div><label>Container capacity</label><input id="containerCapacity" type="number" value="800" /></div>
            <div><label>Max milk-run stops</label><input id="maxStops" type="number" value="3" /></div>
            <div><label>Tail strategy</label><select id="tailStrategy">
              <option value="cost_aware">cost_aware</option>
              <option value="duration_aware">duration_aware</option>
              <option value="saving_aware">saving_aware</option>
              <option value="fill_aware">fill_aware</option>
              <option value="min_count">min_count</option>
            </select></div>
            <div class="toggle"><input id="allowContainer" type="checkbox" checked /><label for="allowContainer">Allow containers</label></div>
            <div class="toggle"><input id="allowExternal" type="checkbox" checked /><label for="allowExternal">Allow external carrier</label></div>
          </div>
          <div style="margin-top:12px" class="grid-2">
            <div><label>Cost weight</label><input id="costWeight" type="range" min="0" max="2" step="0.1" value="1" /></div>
            <div><label>Turnover weight</label><input id="turnoverWeight" type="range" min="0" max="2" step="0.1" value="0.5" /></div>
            <div><label>Fill-rate weight</label><input id="fillWeight" type="range" min="0" max="2" step="0.1" value="0.2" /></div>
            <div class="toggle"><input id="preferCpsat" type="checkbox" checked /><label for="preferCpsat">Prefer CP-SAT</label></div>
          </div>
        </div>
      </section>
      <section>
        <h2>Instance JSON</h2>
        <div class="body">
          <textarea id="instance" class="json-editor"></textarea>
        </div>
      </section>
    </div>
    <div class="right">
      <section>
        <h2>Solution KPIs</h2>
        <div class="body">
          <div class="metrics" id="metrics"></div>
          <div class="pill-row" id="warnings" style="margin-top:12px"></div>
        </div>
        <div id="status" class="status">Load the demo and run the scheduler.</div>
      </section>
      <section>
        <h2>Dispatch Gantt</h2>
        <div class="chart-shell"><svg id="gantt" width="1080" height="420"></svg></div>
      </section>
      <section>
        <h2>Raw solution</h2>
        <div class="body"><pre id="raw">{}</pre></div>
      </section>
    </div>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const status = $("status");

    function setStatus(text, isError = false) {
      status.textContent = text;
      status.className = isError ? "status error" : "status";
    }

    async function loadDemo() {
      const response = await fetch("/demo");
      const payload = await response.json();
      $("request").value = payload.request;
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
      setStatus("Demo loaded. Change constraints or objective weights, then run optimization.");
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
      setStatus("Solving...");
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
        setStatus(`Solved with ${solution.solution.solver}: ${solution.solution.status}`);
      } catch (error) {
        setStatus(`Run failed: ${error.message}`, true);
      } finally {
        $("run").disabled = false;
      }
    }

    function renderSolution(result) {
      const solution = result.solution || {};
      const k = solution.kpis || {};
      const metrics = [
        ["Total cost", k.total_cost],
        ["Own turnover", k.own_vehicle_turnover],
        ["External tasks", k.external_task_count],
        ["Fill rate", k.fill_rate],
        ["Tasks", k.task_count]
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
        <text x="32" y="${height - 18}" font-size="12" fill="#667085">owned</text>
        <rect x="92" y="${height - 28}" width="12" height="12" fill="var(--container)" rx="3" />
        <text x="110" y="${height - 18}" font-size="12" fill="#667085">container</text>
        <rect x="194" y="${height - 28}" width="12" height="12" fill="var(--external)" rx="3" />
        <text x="212" y="${height - 18}" font-size="12" fill="#667085">external</text>`;
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
    loadDemo();
  </script>
</body>
</html>
"""
