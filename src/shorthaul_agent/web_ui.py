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
    .chart-toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 14px;
      border-top: 1px solid var(--line);
    }
    .chart-toolbar select { width: 180px; }
    .chart-summary { color: var(--muted); font-size: 12px; }
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
    .file-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 12px;
    }
    .file-row {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfcfe;
    }
    .file-row input { padding: 6px; background: #fff; }
    .link-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
    }
    .link-row a {
      color: var(--accent-2);
      text-decoration: none;
      font-weight: 640;
      font-size: 12px;
    }
    .guide-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      margin: 12px 0;
    }
    .guide-step {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
      padding: 10px;
      min-height: 86px;
    }
    .guide-step strong { display: block; margin-bottom: 4px; }
    .guide-step span { color: var(--muted); font-size: 12px; }
    .template-summary {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      margin-top: 10px;
      overflow: hidden;
    }
    .template-summary strong {
      display: block;
      padding: 10px;
      background: #fafbfc;
      border-bottom: 1px solid var(--line);
    }
    .template-summary table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    .template-summary th,
    .template-summary td {
      text-align: left;
      vertical-align: top;
      border-top: 1px solid #eef1f5;
      padding: 8px;
    }
    .template-summary code {
      background: #f1f5f9;
      border-radius: 4px;
      padding: 1px 4px;
    }
    .template-shot {
      width: 100%;
      max-height: 150px;
      object-fit: cover;
      object-position: top;
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-top: 10px;
    }
    details {
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
      padding: 10px;
    }
    summary { cursor: pointer; font-weight: 650; }
    .hint-list {
      margin: 0 0 10px 18px;
      padding: 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.65;
    }
    .code-sample {
      white-space: pre-wrap;
      word-break: break-word;
      max-height: none;
      font-size: 12px;
      margin-top: 8px;
    }
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
        <h2 data-i18n="uploadTitle">智能接入并运行</h2>
        <div class="body">
          <div class="hint" data-i18n="uploadIntro">上传业务系统导出的一个或多个 Excel、CSV、JSON，或直接粘贴表格文本。数据接入 Agent 会自动识别字段、对齐调度模型输入，再调用优化器。</div>
          <div style="margin-top:12px">
            <label for="request" data-i18n="requestLabel">调度需求</label>
            <textarea id="request">请基于上传数据生成短途运输调度方案，目标是在满足约束前提下降低成本并提升自有车周转效率。</textarea>
          </div>
          <div class="guide-grid">
            <div class="guide-step"><strong data-i18n="guideStep1Title">1 上传数据</strong><span data-i18n="guideStep1Body">直接选择一批业务系统导出的表，或把表格内容粘贴到文本框。</span></div>
            <div class="guide-step"><strong data-i18n="guideStep2Title">2 Agent 对齐</strong><span data-i18n="guideStep2Body">Agent 自动识别车队、线路、货量、时间窗和约束字段。</span></div>
            <div class="guide-step"><strong data-i18n="guideStep3Title">3 优化求解</strong><span data-i18n="guideStep3Body">结构化输入通过校验后交给 CP-SAT / 启发式求解器。</span></div>
            <div class="guide-step"><strong data-i18n="guideStep4Title">4 查看结果</strong><span data-i18n="guideStep4Body">右侧展示 KPI、甘特图、外部承运和原始响应。</span></div>
          </div>
          <div class="file-grid">
            <div class="file-row">
              <label for="dataFile" data-i18n="dataFile">业务数据文件（可多选）</label>
              <input id="dataFile" type="file" multiple accept=".xlsx,.xlsm,.xls,.csv,.tsv,.txt,.json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" />
            </div>
          </div>
          <div style="margin-top:12px">
            <label for="rawDataText" data-i18n="rawDataText">粘贴数据（可选）</label>
            <textarea id="rawDataText" data-i18n-placeholder="rawDataPlaceholder" placeholder="可粘贴 Excel 复制出来的表格、CSV 文本、JSON 或业务系统导出片段。"></textarea>
          </div>
          <div class="grid-2" style="margin-top:12px">
            <div><label for="uploadInstanceId" data-i18n="uploadInstanceId">场景 ID</label><input id="uploadInstanceId" value="uploaded-instance" /></div>
            <div><label for="uploadDate" data-i18n="uploadDate">计划日期</label><input id="uploadDate" value="2024-12-16" /></div>
          </div>
          <details>
            <summary data-i18n="agentConfigTitle">数据接入 Agent LLM 接入配置</summary>
            <div class="hint" data-i18n="agentConfigHint">已规整的数据会优先本地解析；只有字段无法自动识别时，才调用这里配置的第三方兼容 Chat Completions 接口。可接 OpenAI 官方，也可接 DeepSeek、通义千问、智谱、月之暗面、OpenRouter 等提供 OpenAI-compatible endpoint 的供应方。</div>
            <div class="grid-2" style="margin-top:10px">
              <div><label for="agentProvider" data-i18n="agentProvider">API 供应方</label><select id="agentProvider">
                <option value="openai_compatible" data-i18n="providerCompatible">第三方兼容 / 自定义</option>
                <option value="openai" data-i18n="providerOpenAI">OpenAI 官方</option>
              </select></div>
              <div><label for="agentModel" data-i18n="agentModel">模型名</label><input id="agentModel" data-i18n-placeholder="agentModelPlaceholder" placeholder="例如 deepseek-chat / qwen-plus / 自定义模型名" /></div>
              <div><label for="agentBaseUrl" data-i18n="agentBaseUrl">API Base URL</label><input id="agentBaseUrl" data-i18n-placeholder="agentBaseUrlPlaceholder" placeholder="https://your-provider.example/v1" /></div>
              <div>
                <label for="agentApiKey" data-i18n="agentApiKey">API Key（可选，留空则使用环境变量）</label>
                <input id="agentApiKey" type="password" autocomplete="off" />
              </div>
            </div>
            <div class="hint" data-i18n="agentEnvHint">服务端环境变量同样支持：SHORT_HAUL_INGESTION_PROVIDER、SHORT_HAUL_INGESTION_API_KEY、SHORT_HAUL_INGESTION_BASE_URL、SHORT_HAUL_INGESTION_MODEL。</div>
          </details>
          <div class="toolbar" style="margin-top:12px">
            <button id="runUpload" class="primary" data-i18n="runUpload">上传并运行</button>
            <button id="clearUpload" data-i18n="clearUpload">清空上传文件</button>
          </div>
          <details>
            <summary data-i18n="advancedUpload">高级：绕过 Agent 的标准接口</summary>
            <div class="hint" data-i18n="advancedUploadIntro">开发调试时可直接上传标准 payload.json 或标准 CSV 文件组。</div>
            <div class="file-grid">
              <div class="file-row">
                <label for="payloadFile" data-i18n="payloadFile">完整 payload.json（可选）</label>
                <input id="payloadFile" type="file" accept=".json,application/json" />
              </div>
              <div class="file-row"><label for="fleetsFile">fleets.csv</label><input id="fleetsFile" type="file" accept=".csv,text/csv" /></div>
              <div class="file-row"><label for="routesFile">routes.csv</label><input id="routesFile" type="file" accept=".csv,text/csv" /></div>
              <div class="file-row"><label for="forecastFile">forecast.csv</label><input id="forecastFile" type="file" accept=".csv,text/csv" /></div>
              <div class="file-row"><label for="milkRunFile">milk_run_pairs.csv</label><input id="milkRunFile" type="file" accept=".csv,text/csv" /></div>
              <div class="file-row"><label for="configFile">config_overrides.json</label><input id="configFile" type="file" accept=".json,application/json" /></div>
            </div>
          </details>
        </div>
      </section>
      <section>
        <h2 data-i18n="constraintsTitle">约束与优化目标</h2>
        <div class="body">
          <div class="hint" data-i18n="constraintsHint">这里的显式参数会随上传请求提交，优先级高于自然语言描述和工作簿 settings 表。</div>
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
    </div>
    <div class="right">
      <section>
        <h2 data-i18n="kpiTitle">方案指标</h2>
        <div class="body">
          <div class="metrics" id="metrics"></div>
          <div class="pill-row" id="warnings" style="margin-top:12px"></div>
        </div>
        <div id="status" class="status" data-status-key="statusInitial">上传文件或粘贴数据后即可运行调度器。</div>
      </section>
      <section>
        <h2 data-i18n="ganttTitle">调度甘特图</h2>
        <div class="chart-toolbar">
          <div class="chart-summary" id="ganttSummary"></div>
          <select id="ganttFilter" aria-label="Gantt filter">
            <option value="all" data-i18n="ganttAll">全部任务</option>
            <option value="owned" data-i18n="ganttOwned">仅自有车</option>
            <option value="external" data-i18n="ganttExternal">仅外部承运</option>
            <option value="container" data-i18n="ganttContainer">仅容器任务</option>
          </select>
        </div>
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
        scenarioTitle: "高级编辑",
        loadSample: "加载内置数据",
        validateData: "校验当前数据",
        runOptimization: "运行内部 JSON",
        requestLabel: "调度需求",
        scenarioHint: "普通用户可直接上传 Excel；高级入口用于调试 API payload 或做二次开发。",
        uploadTitle: "智能接入并运行",
        uploadIntro: "上传业务系统导出的一个或多个 Excel、CSV、JSON，或直接粘贴表格文本。数据接入 Agent 会自动识别字段、对齐调度模型输入，再调用优化器。",
        guideStep1Title: "1 上传数据",
        guideStep1Body: "直接选择一批业务系统导出的表，或把表格内容粘贴到文本框。",
        guideStep2Title: "2 Agent 对齐",
        guideStep2Body: "Agent 自动识别车队、线路、货量、时间窗和约束字段。",
        guideStep3Title: "3 优化求解",
        guideStep3Body: "结构化输入通过校验后交给 CP-SAT / 启发式求解器。",
        guideStep4Title: "4 查看结果",
        guideStep4Body: "右侧展示 KPI、甘特图、外部承运和原始响应。",
        dataFile: "业务数据文件（可多选）",
        rawDataText: "粘贴数据（可选）",
        rawDataPlaceholder: "可粘贴 Excel 复制出来的表格、CSV 文本、JSON 或业务系统导出片段。",
        agentConfigTitle: "数据接入 Agent LLM 接入配置",
        agentConfigHint: "已规整的数据会优先本地解析；只有字段无法自动识别时，才调用这里配置的第三方兼容 Chat Completions 接口。可接 OpenAI 官方，也可接提供 OpenAI-compatible endpoint 的第三方供应方。",
        agentProvider: "API 供应方",
        providerCompatible: "第三方兼容 / 自定义",
        providerOpenAI: "OpenAI 官方",
        agentModel: "模型名",
        agentModelPlaceholder: "例如 deepseek-chat / qwen-plus / 自定义模型名",
        agentBaseUrl: "API Base URL",
        agentBaseUrlPlaceholder: "https://your-provider.example/v1",
        agentApiKey: "API Key（可选，留空则使用环境变量）",
        agentEnvHint: "服务端环境变量同样支持：SHORT_HAUL_INGESTION_PROVIDER、SHORT_HAUL_INGESTION_API_KEY、SHORT_HAUL_INGESTION_BASE_URL、SHORT_HAUL_INGESTION_MODEL。",
        payloadFile: "完整 payload.json（可选）",
        uploadInstanceId: "场景 ID",
        uploadDate: "计划日期",
        runUpload: "上传并运行",
        clearUpload: "清空上传文件",
        advancedUpload: "高级：绕过 Agent 的标准接口",
        advancedUploadIntro: "开发调试时可直接上传标准 payload.json 或标准 CSV 文件组。",
        constraintsTitle: "约束与优化目标",
        constraintsHint: "这里的显式参数会随上传请求提交，优先级高于自然语言描述和工作簿 settings 表。",
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
        instanceTitle: "高级：内部 JSON",
        instanceHint: "这是系统内部 payload 结构。外部业务人员通常不需要手写它，上传 Excel 后系统会自动转换。",
        kpiTitle: "方案指标",
        ganttTitle: "调度甘特图",
        ganttAll: "全部任务",
        ganttOwned: "仅自有车",
        ganttExternal: "仅外部承运",
        ganttContainer: "仅容器任务",
        ganttSummary: "显示任务 {shown}/{total}；车辆 {vehicles}；外部承运 {external}",
        rawTitle: "原始结果",
        statusInitial: "上传文件或粘贴数据后即可运行调度器。",
        statusLoaded: "内置数据已加载。可修改约束或目标权重后运行优化。",
        statusValidating: "正在校验数据...",
        statusValid: "数据校验通过",
        statusInvalid: "数据校验未通过",
        statusSolving: "正在求解...",
        statusUploading: "正在上传并求解...",
        statusUploadMissing: "缺少必需上传文件",
        statusWorkbookMissing: "请上传业务数据文件、粘贴数据，或在高级入口上传标准 JSON/CSV",
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
        scenarioTitle: "Advanced editing",
        loadSample: "Load built-in data",
        validateData: "Validate data",
        runOptimization: "Run internal JSON",
        requestLabel: "Scheduling request",
        scenarioHint: "Most users can upload Excel directly. Advanced input is for API payload debugging or custom development.",
        uploadTitle: "Smart ingest and run",
        uploadIntro: "Upload one or more Excel, CSV, or JSON exports, or paste table text. The Data Ingestion Agent aligns fields to the scheduling model before optimization.",
        guideStep1Title: "1 Add data",
        guideStep1Body: "Select a batch of business exports, or paste table contents into the text box.",
        guideStep2Title: "2 Agent aligns",
        guideStep2Body: "The agent detects fleets, routes, demand, time windows, and constraints.",
        guideStep3Title: "3 Optimize",
        guideStep3Body: "Validated structured input is sent to CP-SAT / heuristic solvers.",
        guideStep4Title: "4 Inspect result",
        guideStep4Body: "KPIs, Gantt chart, external carriers, and raw response appear on the right.",
        dataFile: "Business data files",
        rawDataText: "Paste data (optional)",
        rawDataPlaceholder: "Paste copied Excel tables, CSV text, JSON, or business-system export snippets.",
        agentConfigTitle: "Data Ingestion Agent LLM API",
        agentConfigHint: "Aligned files are parsed locally first. When fields cannot be recognized automatically, the agent calls the configured Chat Completions-compatible API. It can be the official OpenAI API or any third-party OpenAI-compatible endpoint.",
        agentProvider: "API provider",
        providerCompatible: "Third-party compatible / custom",
        providerOpenAI: "Official OpenAI",
        agentModel: "Model name",
        agentModelPlaceholder: "e.g. deepseek-chat / qwen-plus / custom model",
        agentBaseUrl: "API Base URL",
        agentBaseUrlPlaceholder: "https://your-provider.example/v1",
        agentApiKey: "API Key (optional; env is used when blank)",
        agentEnvHint: "Server environment variables are also supported: SHORT_HAUL_INGESTION_PROVIDER, SHORT_HAUL_INGESTION_API_KEY, SHORT_HAUL_INGESTION_BASE_URL, SHORT_HAUL_INGESTION_MODEL.",
        payloadFile: "Complete payload.json (optional)",
        uploadInstanceId: "Instance ID",
        uploadDate: "Planning date",
        runUpload: "Upload and run",
        clearUpload: "Clear uploaded files",
        advancedUpload: "Advanced: bypass Agent",
        advancedUploadIntro: "For development/debugging, upload a standard payload.json or standard CSV set directly.",
        constraintsTitle: "Constraints and objective",
        constraintsHint: "These explicit controls are submitted with the upload request and take precedence over natural language text and workbook settings.",
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
        instanceTitle: "Advanced: internal JSON",
        instanceHint: "This is the internal payload structure. Business users usually do not need to write it; Excel uploads are converted automatically.",
        kpiTitle: "Solution KPIs",
        ganttTitle: "Dispatch Gantt",
        ganttAll: "All tasks",
        ganttOwned: "Owned vehicles",
        ganttExternal: "External carrier",
        ganttContainer: "Container tasks",
        ganttSummary: "Showing {shown}/{total} tasks; vehicles {vehicles}; external {external}",
        rawTitle: "Raw solution",
        statusInitial: "Upload a file or paste data to run the scheduler.",
        statusLoaded: "Built-in data loaded. Change constraints or objective weights, then run optimization.",
        statusValidating: "Validating data...",
        statusValid: "Data validation passed",
        statusInvalid: "Data validation failed",
        statusSolving: "Solving...",
        statusUploading: "Uploading and solving...",
        statusUploadMissing: "Missing required upload files",
        statusWorkbookMissing: "Upload a business data file, paste data, or upload standard JSON/CSV in the advanced section",
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
      document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
        node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
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
      applyConfig(payload.config_overrides || {}, payload.prefer_cpsat !== false);
      setStatusKey("statusLoaded");
    }

    function applyConfig(cfg = {}, preferCpsat = $("preferCpsat").checked) {
      $("vehicleCapacity").value = cfg.vehicle_capacity || 1000;
      $("containerCapacity").value = cfg.container_capacity || 800;
      $("maxStops").value = cfg.max_stops || 3;
      $("tailStrategy").value = cfg.tail_cover_strategy || "cost_aware";
      $("allowContainer").checked = cfg.allow_container !== false;
      $("allowExternal").checked = cfg.allow_external !== false;
      $("preferCpsat").checked = preferCpsat;
      const weights = cfg.objective_weights || {};
      $("costWeight").value = weights.cost || 1;
      $("turnoverWeight").value = weights.turnover || 0.5;
      $("fillWeight").value = weights.fill_rate || 0.2;
    }

    function applyAgentProviderPreset() {
      const provider = $("agentProvider").value;
      const baseUrl = $("agentBaseUrl");
      const model = $("agentModel");
      if (provider === "openai") {
        if (!baseUrl.value.trim()) {
          baseUrl.value = "https://api.openai.com/v1";
        }
        if (!model.value.trim()) {
          model.value = "gpt-4.1-mini";
        }
      } else if (baseUrl.value.trim() === "https://api.openai.com/v1") {
        baseUrl.value = "";
      }
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

    async function runUploadedSchedule() {
      $("runUpload").disabled = true;
      setStatusKey("statusUploading");
      try {
        const dataFiles = Array.from($("dataFile").files || []);
        const payloadFile = $("payloadFile").files[0];
        const rawDataText = $("rawDataText").value.trim();
        const formData = new FormData();
        formData.append("use_data_agent", "true");
        formData.append("prefer_cpsat", $("preferCpsat").checked ? "true" : "false");
        formData.append("config_overrides_json", JSON.stringify(configOverrides()));
        formData.append("data_agent_provider", $("agentProvider").value || "openai_compatible");
        formData.append("data_agent_model", $("agentModel").value || "");
        formData.append("data_agent_base_url", $("agentBaseUrl").value || "");
        formData.append("data_agent_api_key", $("agentApiKey").value || "");

        if (dataFiles.length) {
          formData.append("request", $("request").value || "请根据上传数据生成短途运输调度方案。");
          formData.append("instance_id", $("uploadInstanceId").value || "uploaded-instance");
          formData.append("date", $("uploadDate").value || "");
          dataFiles.forEach((file) => formData.append("data_file", file));
        } else if (rawDataText) {
          formData.append("request", $("request").value || "请根据上传数据生成短途运输调度方案。");
          formData.append("instance_id", $("uploadInstanceId").value || "uploaded-instance");
          formData.append("date", $("uploadDate").value || "");
          formData.append("raw_data_text", rawDataText);
        } else if (payloadFile) {
          const payloadText = await payloadFile.text();
          const uploadedPayload = JSON.parse(payloadText);
          if (uploadedPayload.request) {
            $("request").value = uploadedPayload.request;
          }
          if ($("instance") && uploadedPayload.instance) {
            $("instance").value = JSON.stringify(uploadedPayload.instance, null, 2);
          }
          applyConfig(uploadedPayload.config_overrides || configOverrides(), uploadedPayload.prefer_cpsat !== false);
          formData.set("prefer_cpsat", $("preferCpsat").checked ? "true" : "false");
          formData.set("config_overrides_json", JSON.stringify(configOverrides()));
          formData.append("payload_json", payloadFile);
        } else {
          const anyAdvancedFile = ["fleetsFile", "routesFile", "forecastFile", "milkRunFile", "configFile"].some((id) => $(id).files[0]);
          if (!anyAdvancedFile) {
            throw new Error(t("statusWorkbookMissing"));
          }
          const required = [
            ["fleetsFile", "fleets"],
            ["routesFile", "routes"],
            ["forecastFile", "forecast"]
          ];
          const missing = required.filter(([id]) => !$(id).files[0]).map(([, name]) => `${name}.csv`);
          if (missing.length) {
            throw new Error(`${t("statusUploadMissing")}: ${missing.join(", ")}`);
          }
          formData.append("request", $("request").value || "请根据上传数据生成短途运输调度方案。");
          formData.append("instance_id", $("uploadInstanceId").value || "uploaded-instance");
          formData.append("date", $("uploadDate").value || "");
          formData.append("fleets", $("fleetsFile").files[0]);
          formData.append("routes", $("routesFile").files[0]);
          formData.append("forecast", $("forecastFile").files[0]);
          if ($("milkRunFile").files[0]) {
            formData.append("milk_run_pairs", $("milkRunFile").files[0]);
          }
          if ($("configFile").files[0]) {
            formData.append("config_overrides", $("configFile").files[0]);
          }
        }

        const response = await fetch("/schedule/upload", {method: "POST", body: formData});
        const solution = await response.json();
        if (!response.ok || solution.error) {
          throw new Error(solution.detail || JSON.stringify(solution));
        }
        renderSolution(solution);
        setStatusKey("statusSolved", false, `${solution.solution.solver}: ${solution.solution.status}`);
      } catch (error) {
        setStatusKey("statusFailed", true, error.message);
      } finally {
        $("runUpload").disabled = false;
      }
    }

    function clearUploadedFiles() {
      ["dataFile", "payloadFile", "fleetsFile", "routesFile", "forecastFile", "milkRunFile", "configFile"].forEach((id) => {
        $(id).value = "";
      });
      $("rawDataText").value = "";
      setStatusKey("statusInitial");
    }

    async function validateCurrentData() {
      $("validateData").disabled = true;
      setStatusKey("statusValidating");
      try {
        const payload = {
          request: $("request").value || "validate instance",
          instance: JSON.parse($("instance").value),
          prefer_cpsat: $("preferCpsat").checked,
          config_overrides: configOverrides()
        };
        const response = await fetch("/validate-instance", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload)
        });
        const report = await response.json();
        if (!response.ok || report.status !== "ok") {
          throw new Error((report.errors || []).join("; ") || JSON.stringify(report));
        }
        const warningText = (report.warnings || []).slice(0, 3).join("; ");
        setStatusKey("statusValid", false, warningText);
      } catch (error) {
        setStatusKey("statusInvalid", true, error.message);
      } finally {
        $("validateData").disabled = false;
      }
    }

    function renderSolution(result) {
      lastResult = result;
      const solution = result.solution || {};
      const k = solution.kpis || {};
      const metrics = [
        [t("totalCost"), k.total_cost, "number"],
        [t("ownTurnover"), k.own_vehicle_turnover, "number"],
        [t("externalTasks"), k.external_task_count, "number"],
        [t("fillRate"), k.fill_rate, "percent"],
        [t("tasks"), k.task_count, "number"]
      ];
      $("metrics").innerHTML = metrics.map(([label, value, format]) => {
        const display = typeof value === "number"
          ? (format === "percent" ? `${(value * 100).toFixed(1)}%` : value.toFixed(value % 1 ? 2 : 0))
          : "-";
        return `<div class="metric"><span>${label}</span><strong>${display}</strong></div>`;
      }).join("");
      $("warnings").innerHTML = (solution.warnings || []).slice(0, 6).map(item => `<span class="pill">${escapeHtml(item)}</span>`).join("");
      $("raw").textContent = JSON.stringify(result, null, 2);
      drawGantt(solution.assignments || []);
    }

    function drawGantt(assignments) {
      const svg = $("gantt");
      const mode = $("ganttFilter").value || "all";
      const filtered = assignments.filter((item) => {
        if (mode === "owned") {
          return !item.is_external;
        }
        if (mode === "external") {
          return item.is_external;
        }
        if (mode === "container") {
          return item.use_container;
        }
        return true;
      });
      const sorted = filtered.slice().sort((a, b) => (a.dispatch_minute ?? a.start_minute) - (b.dispatch_minute ?? b.start_minute));
      const vehicles = [...new Set(sorted.map(a => a.vehicle_id))];
      $("ganttSummary").textContent = t("ganttSummary")
        .replace("{shown}", filtered.length)
        .replace("{total}", assignments.length)
        .replace("{vehicles}", vehicles.length)
        .replace("{external}", assignments.filter(a => a.is_external).length);
      if (!sorted.length) {
        svg.setAttribute("height", 180);
        svg.innerHTML = `<text x="24" y="64" font-size="13" fill="#667085">${escapeHtml(t("ganttSummary").replace("{shown}", 0).replace("{total}", assignments.length).replace("{vehicles}", 0).replace("{external}", assignments.filter(a => a.is_external).length))}</text>`;
        return;
      }
      const minMinute = Math.min(...sorted.map(a => a.start_minute), 1320);
      const maxMinute = Math.max(...sorted.map(a => a.end_minute), 2360);
      const width = 1080;
      const left = 250;
      const rowHeight = 28;
      const top = 38;
      const height = Math.max(420, top + vehicles.length * rowHeight + 36);
      svg.setAttribute("height", height);
      const scale = (minute) => left + ((minute - minMinute) / Math.max(maxMinute - minMinute, 1)) * (width - left - 28);
      const rows = vehicles.map((vehicle, idx) => {
        const y = top + idx * rowHeight;
        return `<text x="14" y="${y + 18}" font-size="12" fill="#475467">${escapeHtml(vehicleLabel(vehicle))}</text>
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

    function vehicleLabel(vehicleId) {
      const value = String(vehicleId);
      if (value.startsWith("External_")) {
        return value.length > 30 ? `${value.slice(0, 27)}...` : value;
      }
      return value;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
    }

    $("runUpload").addEventListener("click", runUploadedSchedule);
    $("clearUpload").addEventListener("click", clearUploadedFiles);
    $("ganttFilter").addEventListener("change", () => {
      if (lastResult) {
        drawGantt((lastResult.solution || {}).assignments || []);
      }
    });
    $("language").addEventListener("change", (event) => {
      currentLang = event.target.value;
      applyLanguage();
    });
    $("agentProvider").addEventListener("change", applyAgentProviderPreset);
    applyLanguage();
  </script>
</body>
</html>
"""
