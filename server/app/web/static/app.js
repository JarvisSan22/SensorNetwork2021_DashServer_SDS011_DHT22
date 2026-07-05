"use strict";

const METRIC_META = {
  temperature_c: { label: "Temp", unit: "°C", fixed: 1 },
  humidity_pct:  { label: "Humidity", unit: "%", fixed: 0 },
  pm25:          { label: "PM2.5", unit: "µg/m³", fixed: 0 },
  pm10:          { label: "PM10", unit: "µg/m³", fixed: 0 },
  pressure_hpa:  { label: "Pressure", unit: "hPa", fixed: 0 },
};

// Stable per-node colour so a node is the same colour in BOTH live charts
// (and stays put across refreshes). Assigned on first sighting, by node id.
const NODE_PALETTE = [
  "#4aa8ff", "#ff7a59", "#5ad19a", "#f7c948", "#b388ff",
  "#ff6b9d", "#4dd0e1", "#a3e635", "#f49f4b", "#e879f9",
];
const _nodeColor = {};
function colorFor(nodeId) {
  if (!(nodeId in _nodeColor)) {
    _nodeColor[nodeId] = NODE_PALETTE[Object.keys(_nodeColor).length % NODE_PALETTE.length];
  }
  return _nodeColor[nodeId];
}

// The stored outdoor-weather series is a togglable reference line, drawn dashed
// in a neutral grey so it reads as "context" rather than another node.
const WEATHER_ID = "__weather__";
const WEATHER_COLOR = "#9aa7b3";

// A dashed Plotly trace of the saved location's hourly weather for `metric`,
// or null if nothing is stored (e.g. a metric we don't record, or no history).
async function weatherTrace(metric, since, until) {
  let url = `/api/weather/history?metric=${encodeURIComponent(metric)}&since=${encodeURIComponent(since)}`;
  if (until) url += `&until=${encodeURIComponent(until)}`;
  let data;
  try {
    data = await (await fetch(url)).json();
  } catch (e) { return null; }
  if (!data.points || !data.points.length) return null;
  return {
    x: data.points.map((p) => toLocalTs(p.ts)),
    y: data.points.map((p) => p.value),
    mode: "lines",
    name: "☁️ Weather",
    line: { color: WEATHER_COLOR, width: 2, dash: "dot" },
  };
}

// Backend timestamps are naive UTC (no offset). Plotly plots datetime values
// literally (no timezone conversion), so convert each to local wall-clock before
// charting — otherwise points render offset by the browser's UTC offset
// (e.g. 06:55 instead of 15:55 in JST).
function toLocalTs(iso) {
  if (!iso) return iso;
  const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString().slice(0, 19).replace("T", " ");
}

function timeAgo(iso) {
  if (!iso) return "never";
  const secs = Math.round((Date.now() - new Date(iso + "Z").getTime()) / 1000);
  if (secs < 60) return secs + "s ago";
  if (secs < 3600) return Math.round(secs / 60) + "m ago";
  if (secs < 86400) return Math.round(secs / 3600) + "h ago";
  return Math.round(secs / 86400) + "d ago";
}

function metricCell(m) {
  const meta = METRIC_META[m.metric] || { label: m.metric, unit: "", fixed: 1 };
  return `<div class="metric">
    <div class="val">${Number(m.value).toFixed(meta.fixed)}<span class="lbl"> ${meta.unit}</span></div>
    <div class="lbl">${meta.label}</div>
  </div>`;
}

function nodeCard(n) {
  const metrics = n.latest.length
    ? `<div class="metrics">${n.latest.map(metricCell).join("")}</div>`
    : `<div class="empty">no readings yet</div>`;
  return `<div class="card">
    <div class="card-head">
      <span class="name">${n.name}</span>
      <span class="card-meta">
        <span class="muted"><span class="dot ${n.online ? "online" : "offline"}"></span>${timeAgo(n.last_seen)}</span>
        <button class="icon-btn" title="Edit" data-act="edit"
          data-id="${n.id}" data-name="${n.name}" data-place="${n.placement}">⚙️</button>
        <button class="icon-btn danger" title="Delete" data-act="del"
          data-id="${n.id}" data-name="${n.name}">🗑️</button>
      </span>
    </div>
    ${metrics}
  </div>`;
}

async function refreshCards() {
  let nodes;
  try {
    nodes = await (await fetch("/api/summary")).json();
  } catch (e) { return; }

  const groups = { indoor: [], outdoor: [] };
  for (const n of nodes) (groups[n.placement] || groups.indoor).push(n);

  for (const place of ["indoor", "outdoor"]) {
    const el = document.getElementById(place);
    el.innerHTML = groups[place].length
      ? groups[place].map(nodeCard).join("")
      : `<div class="empty">no ${place} nodes yet</div>`;
  }

  renderHistoryNodes(nodes);
}

// History node picker: one toggle chip per node so several can be overlaid on
// the same plot. Re-rendered only when the node set changes, so user
// selections survive the 30s auto-refresh. First node is on by default.
function renderHistoryNodes(nodes) {
  const box = document.getElementById("h-nodes");
  const sig = nodes.map((n) => `${n.id}:${n.name}`).join(",");
  if (box.dataset.sig === sig) return;
  const firstTime = box.dataset.sig === undefined;
  const chosen = new Set(selectedHistoryNodes());
  const chips = nodes.map((n, i) => {
    const on = firstTime ? i === 0 : chosen.has(String(n.id));
    return `<label class="chip"><input type="checkbox" value="${n.id}" ${on ? "checked" : ""} />
      <span class="chip-dot" style="background:${colorFor(n.id)}"></span>${n.name}</label>`;
  });
  // A weather chip alongside the nodes — overlays the stored outdoor line.
  chips.push(`<label class="chip"><input type="checkbox" value="${WEATHER_ID}" ${chosen.has(WEATHER_ID) ? "checked" : ""} />
    <span class="chip-dot" style="background:${WEATHER_COLOR}"></span>☁️ Weather</label>`);
  box.innerHTML = chips.join("");
  box.dataset.sig = sig;
  refreshChart();
}

function selectedHistoryNodes() {
  return [...document.querySelectorAll("#h-nodes input:checked")].map((el) => el.value);
}

// From/To pickers → ISO range; blank falls back to the last 24h.
function historyRange() {
  const from = document.getElementById("h-from").value;
  const to = document.getElementById("h-to").value;
  const since = from ? new Date(from) : new Date(Date.now() - 24 * 3600 * 1000);
  const until = to ? new Date(to) : new Date();
  return { since: since.toISOString(), until: until.toISOString() };
}

// Format a Date for a datetime-local input (local time, no timezone suffix).
function toLocalInput(d) {
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function fmt(v, unit, fixed = 0) {
  return v === null || v === undefined ? "–" : `${Number(v).toFixed(fixed)}${unit}`;
}

async function refreshWeather() {
  const el = document.getElementById("weather");
  let w;
  try {
    const res = await fetch("/api/weather");
    if (res.status === 404) {
      el.innerHTML = `<div class="weather-card empty-weather">🌍 Set your location in ⚙️ Settings to see local weather.</div>`;
      return;
    }
    w = await res.json();
  } catch (e) { return; }

  const c = w.current, t = w.today;
  el.innerHTML = `<div class="weather-card">
    <div class="wx-main">
      <span class="wx-emoji">${c.emoji}</span>
      <div>
        <div class="wx-temp">${fmt(c.temperature_c, "°C", 1)}</div>
        <div class="muted">${c.text} · feels ${fmt(c.apparent_c, "°C", 0)}</div>
      </div>
    </div>
    <div class="wx-meta">
      <div><span class="lbl">Location</span> ${w.location.location_name || "—"}</div>
      <div><span class="lbl">Today</span> ${t.emoji} ${fmt(t.high_c, "°", 0)} / ${fmt(t.low_c, "°", 0)}</div>
      <div><span class="lbl">Rain</span> ${fmt(t.precip_prob_pct, "%", 0)} · ${fmt(t.precip_mm, " mm", 1)}</div>
      <div><span class="lbl">Humidity</span> ${fmt(c.humidity_pct, "%", 0)} · 💨 ${fmt(c.wind_kmh, " km/h", 0)}</div>
    </div>
  </div>`;
}

async function refreshChart() {
  const metric = document.getElementById("h-metric").value;
  const selected = selectedHistoryNodes();
  const nodeIds = selected.filter((v) => v !== WEATHER_ID);
  const showWeather = selected.includes(WEATHER_ID);
  const tier = document.getElementById("h-tier");
  if (!selected.length) { Plotly.purge("chart"); tier.textContent = "pick a node"; return; }

  const { since, until } = historyRange();

  // Node series (skip the fetch entirely if only weather is selected).
  let series = [];
  let tierName = "";
  if (nodeIds.length) {
    const url = `/api/readings/all?metric=${metric}` +
      `&since=${encodeURIComponent(since)}&until=${encodeURIComponent(until)}`;
    try {
      const data = await (await fetch(url)).json();
      const chosen = new Set(nodeIds);
      series = (data.series || []).filter((s) => chosen.has(String(s.node_id)));
      tierName = data.tier;
    } catch (e) { return; }
  }

  const meta = METRIC_META[metric] || { label: metric, unit: "" };
  const traces = series.map((s) => ({
    x: s.points.map((p) => toLocalTs(p.ts)),
    y: s.points.map((p) => p.value),
    mode: "lines",
    name: s.name,
    line: { color: colorFor(s.node_id), width: 2 },
  }));

  if (showWeather) {
    const wt = await weatherTrace(metric, since, until);
    if (wt) traces.push(wt);
  }

  const total = traces.reduce((n, t) => n + t.x.length, 0);
  tier.textContent = total
    ? `${total} pts${tierName ? ` · ${tierName}` : ""}`
    : "no data in range";

  Plotly.react("chart", traces, {
    margin: { l: 50, r: 20, t: 20, b: 40 },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { color: "#8b98a5" },
    xaxis: { gridcolor: "#2b3540" },
    yaxis: { title: `${meta.label} (${meta.unit})`, gridcolor: "#2b3540" },
    showlegend: traces.length > 1,
    legend: { orientation: "h", y: 1.12, font: { size: 11 } },
  }, { responsive: true, displayModeBar: false });
}

// One overlaid live chart: every node's series for a single metric, over the
// range chosen in the live-range picker.
async function liveChart(divId, metric, title, unit, since, showWeather) {
  let data;
  try {
    data = await (await fetch(`/api/readings/all?metric=${encodeURIComponent(metric)}&since=${encodeURIComponent(since)}`)).json();
  } catch (e) { return; }

  const traces = (data.series || []).map((s) => ({
    x: s.points.map((p) => toLocalTs(p.ts)),
    y: s.points.map((p) => p.value),
    mode: "lines",
    name: s.name,
    line: { color: colorFor(s.node_id), width: 2 },
  }));

  if (showWeather) {
    const wt = await weatherTrace(metric, since);
    if (wt) traces.push(wt);
  }

  Plotly.react(divId, traces, {
    margin: { l: 48, r: 16, t: 34, b: 40 },
    title: { text: title, font: { size: 13, color: "#c8d2dc" }, x: 0, xanchor: "left" },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { color: "#8b98a5" },
    xaxis: { gridcolor: "#2b3540" },
    yaxis: { title: unit, gridcolor: "#2b3540" },
    showlegend: false,   // a single shared legend covers both plots instead
  }, { responsive: true, displayModeBar: false });

  return data.series || [];
}

async function refreshLiveCharts() {
  const hours = Number(document.getElementById("live-range").value) || 24;
  const showWeather = document.getElementById("live-weather").checked;
  const since = new Date(Date.now() - hours * 3600 * 1000).toISOString();
  const temp = await liveChart("chart-temp", "temperature_c", "Temperature — all nodes", "°C", since, showWeather);
  const hum = await liveChart("chart-humidity", "humidity_pct", "Humidity — all nodes", "%", since, showWeather);

  // Shared legend: union of nodes across both plots, same colour as the lines.
  const names = {};
  for (const s of [...temp, ...hum]) names[s.node_id] = s.name;
  let html = Object.keys(names).sort().map((id) =>
    `<span class="legend-item"><span class="legend-swatch" style="background:${colorFor(id)}"></span>${names[id]}</span>`
  ).join("");
  if (showWeather) {
    html += `<span class="legend-item"><span class="legend-swatch dashed" style="background:${WEATHER_COLOR}"></span>☁️ Weather</span>`;
  }
  document.getElementById("live-legend").innerHTML = html;
}

function tick() {
  document.getElementById("clock").textContent = new Date().toLocaleString();
}

// History controls → redraw. Node toggles use event delegation so the listener
// survives re-rendering the chip list on refresh.
for (const id of ["h-metric", "h-from", "h-to"]) {
  document.getElementById(id).addEventListener("change", refreshChart);
}
document.getElementById("h-nodes").addEventListener("change", refreshChart);
document.getElementById("live-range").addEventListener("change", refreshLiveCharts);
document.getElementById("live-weather").addEventListener("change", refreshLiveCharts);

// Seed the From/To pickers with the last 24h so the range starts populated.
document.getElementById("h-to").value = toLocalInput(new Date());
document.getElementById("h-from").value = toLocalInput(new Date(Date.now() - 24 * 3600 * 1000));

// --- Node edit / delete -----------------------------------------------------
// One delegated listener covers every card's buttons, so it survives the cards
// being re-rendered on each 30s refresh.
let _editingNode = null;

document.addEventListener("click", (e) => {
  const btn = e.target.closest(".icon-btn");
  if (!btn) return;
  if (btn.dataset.act === "edit") openEditModal(btn.dataset);
  else if (btn.dataset.act === "del") deleteNode(btn.dataset.id, btn.dataset.name);
});

function openEditModal({ id, name, place }) {
  _editingNode = id;
  document.getElementById("edit-name").value = name;
  document.getElementById("edit-place").value = place;
  document.getElementById("edit-status").textContent = "";
  document.getElementById("edit-modal").classList.remove("hidden");
}

function closeEditModal() {
  _editingNode = null;
  document.getElementById("edit-modal").classList.add("hidden");
}

document.getElementById("edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!_editingNode) return;
  const status = document.getElementById("edit-status");
  status.textContent = "Saving…";
  try {
    const res = await fetch(`/api/nodes/${encodeURIComponent(_editingNode)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.getElementById("edit-name").value.trim(),
        placement: document.getElementById("edit-place").value,
      }),
    });
    if (!res.ok) { status.textContent = "Failed"; return; }
    closeEditModal();
    refreshCards();
  } catch (err) { status.textContent = "Error"; }
});

async function deleteNode(id, name) {
  if (!confirm(`Delete node "${name}"?\nThis removes it and all of its stored readings.`)) return;
  try {
    const res = await fetch(`/api/nodes/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (!res.ok) { alert("Delete failed"); return; }
    refreshCards();
  } catch (err) { alert("Error deleting node"); }
}

document.getElementById("edit-close").addEventListener("click", closeEditModal);
document.getElementById("edit-modal").addEventListener("click", (e) => {
  if (e.target.id === "edit-modal") closeEditModal();
});

// --- Settings panel ---------------------------------------------------------
document.getElementById("settings-toggle").addEventListener("click", async () => {
  const panel = document.getElementById("settings-panel");
  panel.classList.toggle("hidden");
  if (!panel.classList.contains("hidden")) {
    try {
      const s = await (await fetch("/api/settings")).json();
      document.getElementById("loc-input").value = s.location_name || "";
    } catch (e) { /* ignore */ }
  }
});

document.getElementById("location-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("loc-status");
  const name = document.getElementById("loc-input").value.trim();
  if (!name) return;
  status.textContent = "Saving…";
  try {
    const res = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ location_name: name }),
    });
    if (!res.ok) {
      status.textContent = (await res.json()).detail || "Failed";
      return;
    }
    const saved = await res.json();
    status.textContent = `✓ ${saved.location_name}`;
    refreshWeather();
  } catch (err) {
    status.textContent = "Error";
  }
});

// --- Add Node / flashing ----------------------------------------------------
let PIN_SETUP = {};

async function detectDevices() {
  const status = document.getElementById("flash-status");
  status.textContent = "Scanning…";
  let data;
  try {
    data = await (await fetch("/api/flash")).json();
  } catch (e) { status.textContent = "Scan failed"; return; }
  PIN_SETUP = data.pin_setup || {};

  const portSel = document.getElementById("flash-port");
  portSel.innerHTML = data.ports.length
    ? data.ports.map((p) =>
        `<option value="${p.device}">${p.device}${p.likely_esp ? " ★" : ""} — ${p.description}</option>`).join("")
    : `<option value="">no devices found</option>`;

  const varSel = document.getElementById("flash-variant");
  varSel.innerHTML = data.firmware.length
    ? data.firmware.map((f) => `<option value="${f}">${f}</option>`).join("")
    : `<option value="">no firmware built</option>`;

  const ready = data.ports.length && data.firmware.length;
  document.getElementById("flash-btn").disabled = !ready;
  status.textContent = ready
    ? `${data.ports.length} port(s), ${data.firmware.length} image(s)`
    : (data.firmware.length ? "no device detected" : "build firmware first (see firmware/prebuilt/README)");
}

function selectedSensors() {
  return {
    dht: document.getElementById("s-dht").checked,
    pms: document.getElementById("s-pms").checked,
    bmp: document.getElementById("s-bmp").checked,
  };
}

async function flashDevice() {
  const port = document.getElementById("flash-port").value;
  const variant = document.getElementById("flash-variant").value;
  if (!port || !variant) return;
  const status = document.getElementById("flash-status");
  const log = document.getElementById("flash-log");
  const btn = document.getElementById("flash-btn");
  const s = selectedSensors();
  btn.disabled = true;
  status.textContent = "Flashing & configuring… (don't unplug)";
  log.classList.remove("hidden");
  log.textContent = "Writing firmware to " + port + " …";
  try {
    const res = await fetch("/api/flash", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        port, variant,
        node: document.getElementById("n-name").value.trim(),
        placement: document.getElementById("n-place").value,
        wifi_ssid: document.getElementById("n-ssid").value,
        wifi_pass: document.getElementById("n-pass").value,
        server_url: document.getElementById("n-server").value.trim(),
        sensors: { ...s, sds: false },
      }),
    });
    const data = await res.json();
    const f = data.flash || {};
    const p = data.provision || {};
    if (!f.ok) {
      status.textContent = "✗ Flash failed: " + (f.error || "");
    } else if (p && p.ok) {
      status.textContent = "✓ Flashed & configured — node will connect shortly";
    } else {
      status.textContent = "✓ Flashed. Config not pushed (" + (p.error || "n/a") + ") — use SensorNet-Setup WiFi";
    }
    log.textContent = [f.log, p && p.log].filter(Boolean).join("\n--- provisioning ---\n") || f.error || "";
  } catch (e) {
    status.textContent = "Error";
  } finally {
    btn.disabled = false;
  }
}

async function monitorSerial() {
  const portSel = document.getElementById("flash-port");
  const status = document.getElementById("flash-status");
  const log = document.getElementById("flash-log");
  const btn = document.getElementById("serial-btn");
  // No port chosen yet? Scan for any plugged-in device first.
  if (!portSel.value) await detectDevices();
  const port = portSel.value;
  if (!port) {
    log.classList.remove("hidden");
    log.textContent = "No serial device connected — plug an ESP32 in over USB and try again.";
    status.textContent = "No device";
    return;
  }
  const baud = parseInt(document.getElementById("serial-baud").value, 10) || 115200;
  btn.disabled = true;
  status.textContent = "Reading serial…";
  log.classList.remove("hidden");
  log.textContent = "Listening on " + port + " @ " + baud + " baud …";
  try {
    const res = await fetch("/api/flash/monitor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ port, seconds: 15, baud }),
    });
    const data = await res.json();
    log.textContent = data.log || data.error || "(no output)";
    status.textContent = data.ok ? "✓ Serial captured" : "✗ " + (data.error || "serial read failed");
  } catch (e) {
    status.textContent = "Error reading serial";
  } finally {
    btn.disabled = false;
  }
}

// --- Pin setup modal --------------------------------------------------------
async function showPins() {
  if (!Object.keys(PIN_SETUP).length) {
    try { PIN_SETUP = (await (await fetch("/api/flash")).json()).pin_setup || {}; } catch (e) {}
  }
  const s = selectedSensors();
  const body = document.getElementById("pin-body");
  const sections = Object.entries(PIN_SETUP)
    .filter(([key]) => s[key])
    .map(([key, info]) => `<div class="pin-sensor"><h4>${info.name}</h4><table>${
      info.pins.map((row) => `<tr><td>${row[0]}</td><td>${row[1]}</td></tr>`).join("")
    }</table></div>`);
  body.innerHTML = sections.length ? sections.join("") : `<p class="muted">Enable a sensor above to see its wiring.</p>`;
  document.getElementById("pin-modal").classList.remove("hidden");
}

document.getElementById("detect-btn").addEventListener("click", detectDevices);
document.getElementById("flash-btn").addEventListener("click", flashDevice);
document.getElementById("serial-btn").addEventListener("click", monitorSerial);
document.getElementById("pins-btn").addEventListener("click", showPins);
document.getElementById("pin-close").addEventListener("click", () =>
  document.getElementById("pin-modal").classList.add("hidden"));
document.getElementById("pin-modal").addEventListener("click", (e) => {
  if (e.target.id === "pin-modal") e.target.classList.add("hidden");
});

// The Add-a-node defaults are rendered server-side into the input values from
// server/.env. Here we only fill any field the .env left blank: WiFi from the
// API, and the server URL from how this dashboard was reached (the LAN IP).
async function prefillDefaults() {
  const ssid = document.getElementById("n-ssid");
  const pass = document.getElementById("n-pass");
  const srv = document.getElementById("n-server");
  if (!srv.value) srv.value = window.location.origin;
  if (ssid.value && pass.value) return;
  try {
    const d = (await (await fetch("/api/flash")).json()).defaults || {};
    if (!ssid.value && d.wifi_ssid) ssid.value = d.wifi_ssid;
    if (!pass.value && d.wifi_pass) pass.value = d.wifi_pass;
  } catch (e) {}
}
prefillDefaults();

async function loop() {
  await refreshCards();
  await refreshWeather();
  await refreshLiveCharts();
  await refreshChart();
}

tick();
setInterval(tick, 1000);
loop();
setInterval(loop, 30000);
