// ============================================================
//  Smart Resource Monitor — Web Dashboard
//  app.js  (all client-side logic)
// ============================================================

'use strict';

// ── Constants ─────────────────────────────────────────────────────────────────
const WS_URL   = `ws://${location.host}/ws`;
const API_BASE = `http://${location.host}`;

const COLORS = {
  cyan:   '#00D4FF',
  purple: '#7B61FF',
  green:  '#00FF88',
  amber:  '#FFB700',
  orange: '#FF8C00',
  red:    '#FF4757',
  muted:  '#4A5568',
  track:  '#1E2A3A',
};

// ── State ─────────────────────────────────────────────────────────────────────
let ws             = null;
let autoRefresh    = true;
let killPid        = null;
let killName       = '';
let sortCol        = 'cpu';
let sortDir        = -1;           // -1 = descending
let processData    = [];
let cpuHist        = new Array(60).fill(0);
let memHist        = new Array(60).fill(0);
let diskHist       = new Array(60).fill(0);

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const qsa = sel => document.querySelectorAll(sel);

// ── Clock ─────────────────────────────────────────────────────────────────────
function tickClock() {
  const now = new Date();
  $('clock').textContent = now.toTimeString().slice(0, 8);
}
setInterval(tickClock, 1000);
tickClock();

// ── System info (one-shot) ────────────────────────────────────────────────────
async function loadSysinfo() {
  try {
    const r = await fetch(`${API_BASE}/api/sysinfo`);
    const d = await r.json();
    $('sysinfo').textContent =
      `${d.hostname}  •  ${d.os}  •  ${d.cores_p}C / ${d.cores_l}T  •  ${d.total_ram} GB RAM`;
  } catch { /* offline */ }
}
loadSysinfo();

// ════════════════════════════════════════════════════════════════════════════════
//  ARC GAUGE
// ════════════════════════════════════════════════════════════════════════════════
class ArcGauge {
  constructor(id, label, unit) {
    this.id       = id;
    this.label    = label;
    this.unit     = unit;
    this.current  = 0;
    this.target   = 0;
    this.animating = false;

    this.R  = 55;
    this.CX = 80;
    this.CY = 80;
    this.C  = 2 * Math.PI * this.R;          // circumference ≈ 345.6
    this.ARC = this.C * 0.75;                // 270° arc ≈ 259.2

    this._build();
  }

  _build() {
    const { CX, CY, R, C, ARC, label, unit, id } = this;
    const gap = C - ARC;

    document.getElementById(id).innerHTML = `
      <svg viewBox="0 0 160 160" width="158" height="158">
        <!-- outer shadow track -->
        <circle cx="${CX}" cy="${CY}" r="${R + 1}"
          fill="none" stroke="#151E30" stroke-width="14"
          stroke-dasharray="${ARC} ${gap}"
          transform="rotate(135 ${CX} ${CY})"
          stroke-linecap="round"/>
        <!-- background track -->
        <circle cx="${CX}" cy="${CY}" r="${R}"
          fill="none" stroke="${COLORS.track}" stroke-width="10"
          stroke-dasharray="${ARC} ${gap}"
          transform="rotate(135 ${CX} ${CY})"
          stroke-linecap="round"/>
        <!-- glow arc -->
        <circle cx="${CX}" cy="${CY}" r="${R + 1}"
          fill="none" stroke="${COLORS.cyan}" stroke-width="14"
          stroke-dasharray="0 ${C}"
          transform="rotate(135 ${CX} ${CY})"
          stroke-linecap="round" opacity="0.35"
          id="${id}-glow"/>
        <!-- value arc -->
        <circle cx="${CX}" cy="${CY}" r="${R}"
          fill="none" stroke="${COLORS.cyan}" stroke-width="9"
          stroke-dasharray="0 ${C}"
          transform="rotate(135 ${CX} ${CY})"
          stroke-linecap="round"
          id="${id}-arc"/>
        <!-- value number -->
        <text x="${CX}" y="${CY - 10}"
          text-anchor="middle" dominant-baseline="middle"
          font-family="Inter,sans-serif" font-size="19" font-weight="800"
          fill="#E8EAF0" id="${id}-val">0.0</text>
        <!-- unit -->
        <text x="${CX}" y="${CY + 16}"
          text-anchor="middle" dominant-baseline="middle"
          font-family="Inter,sans-serif" font-size="10" font-weight="600"
          fill="${COLORS.cyan}" id="${id}-unit">${unit}</text>
        <!-- label -->
        <text x="${CX}" y="152"
          text-anchor="middle" dominant-baseline="middle"
          font-family="Inter,sans-serif" font-size="9" font-weight="700"
          fill="${COLORS.muted}" letter-spacing="1">${label}</text>
      </svg>`;

    this._arcEl  = document.getElementById(`${id}-arc`);
    this._glowEl = document.getElementById(`${id}-glow`);
    this._valEl  = document.getElementById(`${id}-val`);
    this._unitEl = document.getElementById(`${id}-unit`);
  }

  _color(v) {
    if (v < 60) return COLORS.green;
    if (v < 80) return COLORS.amber;
    return COLORS.red;
  }

  setValue(value, subText) {
    this.target = Math.max(0, Math.min(100, value));
    if (!this.animating) this._tick();
    if (subText !== undefined) {
      const sub = document.getElementById(`${this.id}-sub`);
      if (sub) sub.textContent = subText;
    }
  }

  _tick() {
    const diff = this.target - this.current;
    if (Math.abs(diff) < 0.2) {
      this.current   = this.target;
      this.animating = false;
      this._paint();
      return;
    }
    this.animating = true;
    this.current  += diff * 0.22;
    this._paint();
    requestAnimationFrame(() => this._tick());
  }

  _paint() {
    const v      = this.current;
    const color  = this._color(v);
    const filled = this.ARC * (v / 100);
    const gap    = this.C - filled;
    const da     = `${filled} ${gap}`;

    this._arcEl.setAttribute('stroke-dasharray', da);
    this._arcEl.setAttribute('stroke', color);
    this._glowEl.setAttribute('stroke-dasharray', da);
    this._glowEl.setAttribute('stroke', color);
    this._valEl.textContent = v.toFixed(1);
    this._unitEl.setAttribute('fill', color);
  }
}

// ── Instantiate gauges ────────────────────────────────────────────────────────
const gauges = {
  cpu:  new ArcGauge('gauge-cpu',  'CPU',    '%'),
  mem:  new ArcGauge('gauge-mem',  'MEMORY', '%'),
  disk: new ArcGauge('gauge-disk', 'DISK',   '%'),
};

// ════════════════════════════════════════════════════════════════════════════════
//  HISTORY CHART (Chart.js)
// ════════════════════════════════════════════════════════════════════════════════
const chartCtx = $('history-chart').getContext('2d');
const histChart = new Chart(chartCtx, {
  type: 'line',
  data: {
    labels: new Array(60).fill(''),
    datasets: [
      {
        label: 'CPU',
        data: cpuHist,
        borderColor: COLORS.cyan,
        backgroundColor: 'rgba(0,212,255,0.06)',
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        tension: 0.4,
      },
      {
        label: 'Memory',
        data: memHist,
        borderColor: COLORS.purple,
        backgroundColor: 'rgba(123,97,255,0.06)',
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        tension: 0.4,
      },
      {
        label: 'Disk',
        data: diskHist,
        borderColor: COLORS.green,
        backgroundColor: 'rgba(0,255,136,0.04)',
        borderWidth: 1.5,
        pointRadius: 0,
        fill: true,
        tension: 0.4,
      },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(17,24,39,0.95)',
        borderColor: '#1E2A3A',
        borderWidth: 1,
        titleColor: '#8892A4',
        bodyColor: '#E8EAF0',
        callbacks: {
          label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%`,
        },
      },
    },
    scales: {
      x: { display: false },
      y: {
        min: 0,
        max: 100,
        grid: { color: 'rgba(30,42,58,0.7)', drawBorder: false },
        ticks: {
          color: '#4A5568',
          font: { family: 'JetBrains Mono', size: 9 },
          callback: v => v + '%',
          stepSize: 25,
        },
        border: { display: false },
      },
    },
  },
});

function pushChart(cpu, mem, disk) {
  cpuHist.push(cpu);   if (cpuHist.length  > 60) cpuHist.shift();
  memHist.push(mem);   if (memHist.length  > 60) memHist.shift();
  diskHist.push(disk); if (diskHist.length > 60) diskHist.shift();
  histChart.data.datasets[0].data = [...cpuHist];
  histChart.data.datasets[1].data = [...memHist];
  histChart.data.datasets[2].data = [...diskHist];
  histChart.update('none');
}

// ════════════════════════════════════════════════════════════════════════════════
//  HEALTH CARD
// ════════════════════════════════════════════════════════════════════════════════
function updateHealth(score) {
  let color, label;
  if (score >= 80)      { color = COLORS.green;  label = 'EXCELLENT'; }
  else if (score >= 60) { color = COLORS.amber;  label = 'GOOD'; }
  else if (score >= 40) { color = COLORS.orange; label = 'FAIR'; }
  else                  { color = COLORS.red;    label = 'POOR — ACTION NEEDED'; }

  const scoreEl = $('health-score');
  const labelEl = $('health-label');
  const fillEl  = $('health-bar-fill');

  scoreEl.textContent  = score;
  scoreEl.style.color  = color;
  labelEl.textContent  = label;
  labelEl.style.color  = color;
  fillEl.style.width   = score + '%';
  fillEl.style.background = color;
}

// ════════════════════════════════════════════════════════════════════════════════
//  NETWORK / MEMORY CARD
// ════════════════════════════════════════════════════════════════════════════════
function fmtNet(kbps) {
  return kbps >= 1024 ? (kbps / 1024).toFixed(1) + ' MB/s' : kbps.toFixed(1) + ' KB/s';
}

function updateNetCard(d) {
  $('net-up').textContent   = fmtNet(d.net_bytes_sent);
  $('net-dn').textContent   = fmtNet(d.net_bytes_recv);
  $('mem-detail').textContent = `${d.memory_used_gb} / ${d.memory_total_gb} GB`;
  $('swap-val').textContent  = d.swap_percent.toFixed(1) + '%';
  $('proc-cnt').textContent  = d.total_processes;
}

// ════════════════════════════════════════════════════════════════════════════════
//  PROCESS TABLE
// ════════════════════════════════════════════════════════════════════════════════
const COL_MAP = {
  '#':     (a, b) => a.idx  - b.idx,
  pid:     (a, b) => a.pid  - b.pid,
  name:    (a, b) => a.name.localeCompare(b.name),
  cpu:     (a, b) => a.cpu  - b.cpu,
  mem:     (a, b) => a.mem  - b.mem,
  status:  (a, b) => a.status.localeCompare(b.status),
  user:    (a, b) => a.user.localeCompare(b.user),
};

function updateProcessTable(procs) {
  processData = procs.map((p, i) => ({ ...p, idx: i + 1 }));
  renderTable();
  $('proc-count').textContent = `${procs.length} processes`;
}

function renderTable() {
  const sorted = [...processData].sort((a, b) => {
    const fn = COL_MAP[sortCol] || COL_MAP['cpu'];
    return fn(a, b) * sortDir;
  });

  const tbody = $('proc-tbody');
  const rows  = sorted.slice(0, 150);

  // Reuse existing rows if possible
  while (tbody.children.length > rows.length) tbody.removeChild(tbody.lastChild);
  while (tbody.children.length < rows.length) tbody.appendChild(document.createElement('tr'));

  rows.forEach((p, i) => {
    const tr  = tbody.children[i];
    const cls = p.cpu >= 50 ? 'row-crit' : p.cpu >= 15 ? 'row-high' : '';
    const cpuCls = p.cpu >= 50 ? 'cpu-crit' : p.cpu >= 15 ? 'cpu-high' : 'cpu-norm';

    tr.className = cls;
    tr.innerHTML = `
      <td style="color:var(--text-muted)">${p.idx}</td>
      <td style="font-family:'JetBrains Mono',monospace;font-size:11px">${p.pid}</td>
      <td title="${p.name}">${p.name.slice(0, 30)}</td>
      <td class="${cpuCls}">${p.cpu.toFixed(1)}</td>
      <td style="color:var(--text-secondary)">${p.mem.toFixed(0)}</td>
      <td style="color:var(--text-muted);font-size:11px">${p.status}</td>
      <td style="color:var(--text-muted);font-size:11px">${p.user}</td>
      <td><button class="kill-btn" data-pid="${p.pid}" data-name="${p.name}">🔴 Kill</button></td>`;
  });

  // Update sort indicators
  qsa('thead th[data-col]').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.col === sortCol) {
      th.classList.add(sortDir === -1 ? 'sort-desc' : 'sort-asc');
    }
  });
}

// Table header sort
$('proc-table').addEventListener('click', e => {
  const th = e.target.closest('th[data-col]');
  if (th) {
    const col = th.dataset.col;
    if (sortCol === col) sortDir *= -1;
    else { sortCol = col; sortDir = -1; }
    renderTable();
    return;
  }
  // Kill button
  const btn = e.target.closest('.kill-btn');
  if (btn) showKillModal(parseInt(btn.dataset.pid), btn.dataset.name);
});

// ════════════════════════════════════════════════════════════════════════════════
//  RECOMMENDATIONS
// ════════════════════════════════════════════════════════════════════════════════
function updateRecommendations(recs) {
  const list = $('rec-list');
  list.innerHTML = '';

  if (!recs.length) {
    list.innerHTML = '<div class="no-recs">✅  System looks healthy</div>';
    $('rec-badges').innerHTML = '';
    return;
  }

  const crits = recs.filter(r => r.severity === 'CRITICAL').length;
  const warns  = recs.filter(r => r.severity === 'WARNING').length;
  let badges = '';
  if (crits) badges += `<span class="badge badge-red">${crits} critical</span>`;
  if (warns)  badges += `<span class="badge badge-amber">${warns} warning</span>`;
  $('rec-badges').innerHTML = badges;

  recs.forEach(r => {
    const item = document.createElement('div');
    item.className = `rec-item sev-${r.severity}`;

    const killBtn = (r.pid && (r.severity === 'CRITICAL' || r.severity === 'WARNING'))
      ? `<button class="rec-kill-btn" data-pid="${r.pid}" data-name="${r.proc_name || 'Process'}">
           🔴 Kill PID ${r.pid}
         </button>`
      : '';

    item.innerHTML = `
      <div class="rec-header">
        <span class="rec-title">${r.title}</span>
        <span class="rec-badge">${r.severity}</span>
      </div>
      <div class="rec-category">📂 ${r.category}</div>
      <div class="rec-msg">${r.message}</div>
      <div class="rec-action">→ ${r.action}</div>
      ${killBtn}`;

    list.appendChild(item);
  });

  // Kill buttons in rec panel
  list.querySelectorAll('.rec-kill-btn').forEach(btn => {
    btn.addEventListener('click', () =>
      showKillModal(parseInt(btn.dataset.pid), btn.dataset.name));
  });
}

// ════════════════════════════════════════════════════════════════════════════════
//  KILL MODAL
// ════════════════════════════════════════════════════════════════════════════════
function showKillModal(pid, name) {
  killPid  = pid;
  killName = name;
  $('modal-proc-name').textContent = name;
  $('modal-proc-pid').textContent  = pid;
  $('kill-modal').classList.remove('hidden');
}

$('modal-cancel').addEventListener('click', () => {
  $('kill-modal').classList.add('hidden');
});

$('modal-confirm').addEventListener('click', async () => {
  $('kill-modal').classList.add('hidden');
  if (!killPid) return;
  try {
    const r = await fetch(`${API_BASE}/api/kill/${killPid}`, { method: 'POST' });
    const d = await r.json();
    if (d.success) toast(d.message, 'success', '✅');
    else           toast(d.message, 'error',   '❌');
  } catch (e) {
    toast('Failed to reach server.', 'error', '❌');
  }
  killPid = null;
});

// Close modal on overlay click
$('kill-modal').addEventListener('click', e => {
  if (e.target === $('kill-modal')) $('kill-modal').classList.add('hidden');
});

// ════════════════════════════════════════════════════════════════════════════════
//  REPORT GENERATION
// ════════════════════════════════════════════════════════════════════════════════
$('btn-report').addEventListener('click', async () => {
  const btn = $('btn-report');
  btn.disabled = true;
  btn.textContent = '⏳ Generating…';
  try {
    const r = await fetch(`${API_BASE}/api/report`, { method: 'POST' });
    const d = await r.json();
    if (d.success) toast(`Report saved:\n${d.path}`, 'success', '📄');
    else           toast(d.message, 'error', '❌');
  } catch (e) {
    toast('Server unreachable.', 'error', '❌');
  } finally {
    btn.disabled    = false;
    btn.textContent = '📄  Generate Report';
  }
});

// ════════════════════════════════════════════════════════════════════════════════
//  TOAST NOTIFICATIONS
// ════════════════════════════════════════════════════════════════════════════════
function toast(msg, type = 'info', icon = 'ℹ️', duration = 4000) {
  const container = $('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-msg">${msg}</span>`;
  container.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity 0.4s';
    setTimeout(() => t.remove(), 400); }, duration);
}

// ════════════════════════════════════════════════════════════════════════════════
//  AUTO REFRESH TOGGLE
// ════════════════════════════════════════════════════════════════════════════════
$('auto-toggle').addEventListener('change', e => {
  autoRefresh = e.target.checked;
});

// ════════════════════════════════════════════════════════════════════════════════
//  WEBSOCKET
// ════════════════════════════════════════════════════════════════════════════════
let wsRetryDelay = 1000;

function connectWS() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    wsRetryDelay = 1000;
    $('conn-banner').classList.remove('show');
    $('status-text').textContent = 'LIVE MONITORING';
  };

  ws.onmessage = e => {
    if (!autoRefresh) return;
    try {
      const d = JSON.parse(e.data);
      if (d.type !== 'snapshot') return;

      // Gauges
      gauges.cpu.setValue(d.cpu_percent);
      gauges.mem.setValue(d.memory_percent);
      gauges.disk.setValue(d.disk_percent);

      $('gauge-cpu-sub').textContent  = `${d.cpu_freq_mhz} MHz`;
      $('gauge-mem-sub').textContent  = `${d.memory_used_gb} / ${d.memory_total_gb} GB`;
      $('gauge-disk-sub').textContent = `${d.disk_free_gb} GB free`;

      // Health + network
      updateHealth(d.health_score);
      updateNetCard(d);

      // Chart
      pushChart(d.cpu_percent, d.memory_percent, d.disk_percent);

      // Process table + recommendations
      updateProcessTable(d.processes);
      updateRecommendations(d.recommendations);

      // Footer timestamp
      const now = new Date();
      $('last-update').textContent =
        'Last update: ' + now.toTimeString().slice(0, 8);

    } catch { /* ignore parse errors */ }
  };

  ws.onclose = () => {
    $('conn-banner').classList.add('show');
    $('status-text').textContent = 'RECONNECTING…';
    setTimeout(connectWS, wsRetryDelay);
    wsRetryDelay = Math.min(wsRetryDelay * 2, 10000);
  };

  ws.onerror = () => ws.close();
}

// ── Keepalive ping ────────────────────────────────────────────────────────────
setInterval(() => {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping');
}, 15000);

// ── Boot ──────────────────────────────────────────────────────────────────────
connectWS();
