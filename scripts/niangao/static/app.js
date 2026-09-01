/* 年糕投资系统 — shared JS utilities */

// API base (same origin)
const API = '/api';

// Toast notification
function toast(msg, type = 'success') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// API helpers
async function apiGet(path) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function apiPost(path, body) {
  const r = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || `${r.status}`);
  return data;
}

async function apiPut(path, body) {
  const r = await fetch(`${API}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || `${r.status}`);
  return data;
}

async function apiDelete(path) {
  const r = await fetch(`${API}${path}`, { method: 'DELETE' });
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || `${r.status}`);
  return data;
}

// Format helpers
function fmtMoney(v) {
  if (v == null || isNaN(v)) return '—';
  const n = Number(v);
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + '亿';
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(2) + '万';
  return n.toFixed(2);
}

function fmtPct(v) {
  if (v == null || isNaN(v)) return '—';
  return Number(v).toFixed(2) + '%';
}

function fmtNum(v) {
  if (v == null || isNaN(v)) return '—';
  return Number(v).toLocaleString();
}

function colorClass(v, greenIsGood = true) {
  if (v == null) return '';
  if (v > 0) return greenIsGood ? 'stat-green' : 'stat-red';
  if (v < 0) return greenIsGood ? 'stat-red' : 'stat-green';
  return '';
}

// Modal helpers
function openModal(id) {
  document.getElementById(id).classList.add('active');
}
function closeModal(id) {
  document.getElementById(id).classList.remove('active');
}

// ── Table sorting ────────────────────────────────────────────────────
function makeSortable(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;
  table.querySelectorAll('th.sortable').forEach((th, i) => {
    th.style.cursor = 'pointer';
    th.style.userSelect = 'none';
    th.addEventListener('click', () => {
      const asc = th.dataset.sort !== 'asc';
      table.querySelectorAll('th.sortable').forEach(h => delete h.dataset.sort);
      th.dataset.sort = asc ? 'asc' : 'desc';
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const ci = Array.from(th.parentNode.children).indexOf(th);
      rows.sort((a, b) => {
        const av = a.children[ci]?.textContent?.trim() || '';
        const bv = b.children[ci]?.textContent?.trim() || '';
        const an = parseFloat(av.replace(/[^0-9.\-]/g, ''));
        const bn = parseFloat(bv.replace(/[^0-9.\-]/g, ''));
        if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      rows.forEach(r => tbody.appendChild(r));
      th.textContent = (asc ? '▲ ' : '▼ ') + th.textContent.replace(/^[▲▼] /, '');
    });
  });
}

// ── SVG chart utilities ──────────────────────────────────────────────

function sparkline(containerId, data, opts = {}) {
  const el = document.getElementById(containerId);
  if (!el || !data || data.length < 2) return;
  const w = opts.width || el.clientWidth || 300;
  const h = opts.height || 60;
  const mn = Math.min(...data), mx = Math.max(...data);
  const range = mx - mn || 1;
  const points = data.map((v, i) => `${(i/(data.length-1))*w},${h-((v-mn)/range)*h}`).join(' ');
  const color = opts.color || (data[data.length-1] >= data[0] ? 'var(--green)' : 'var(--red)');
  el.innerHTML = `<svg width="${w}" height="${h}" style="display:block"><polyline points="${points}" fill="none" stroke="${color}" stroke-width="1.5"/></svg>`;
}

function barChart(containerId, items, opts = {}) {
  const el = document.getElementById(containerId);
  if (!el || !items || !items.length) return;
  const w = opts.width || el.clientWidth || 400;
  const barH = opts.barHeight || 20;
  const gap = opts.gap || 4;
  const h = items.length * (barH + gap);
  const maxVal = Math.max(...items.map(i => i.value || 0)) || 1;
  const labelW = opts.labelWidth || 60;
  let html = `<svg width="${w}" height="${h}" style="display:block">`;
  items.forEach((item, i) => {
    const bw = ((item.value || 0) / maxVal) * (w - labelW - 50);
    const y = i * (barH + gap);
    html += `<text x="${labelW-4}" y="${y+barH-5}" text-anchor="end" font-size="11" fill="var(--text-light)">${item.label||''}</text>`;
    html += `<rect x="${labelW}" y="${y}" width="${Math.max(bw,1)}" height="${barH}" rx="2" fill="${item.color || 'var(--accent)'}" opacity="0.8"/>`;
    html += `<text x="${labelW+bw+4}" y="${y+barH-5}" font-size="10" fill="var(--text)">${item.valueText||''}</text>`;
  });
  html += '</svg>';
  el.innerHTML = html;
}

function pieChart(containerId, items, opts = {}) {
  const el = document.getElementById(containerId);
  if (!el || !items || !items.length) return;
  const r = opts.radius || 80, cx = r + 10, cy = r + 10;
  const colors = ['#2d7a3a','#2471a3','#b8860b','#c0392b','#8e44ad','#1abc9c','#e67e22','#95a5a6'];
  const total = items.reduce((s, i) => s + (i.value||0), 0) || 1;
  let html = `<svg width="${cx*2}" height="${cy*2}" style="display:block">`;
  let angle = -Math.PI / 2;
  items.forEach((item, i) => {
    const slice = (item.value || 0) / total * Math.PI * 2;
    if (slice < 0.01) return;
    const x1 = cx + r * Math.cos(angle), y1 = cy + r * Math.sin(angle);
    const x2 = cx + r * Math.cos(angle + slice), y2 = cy + r * Math.sin(angle + slice);
    const large = slice > Math.PI ? 1 : 0;
    html += `<path d="M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} Z" fill="${item.color||colors[i%colors.length]}" opacity="0.8" stroke="#fff" stroke-width="1"/>`;
    angle += slice;
  });
  html += '</svg>';
  // Legend
  html += '<div style="margin-top:6px">';
  items.forEach((item, i) => {
    html += `<span style="display:inline-block;margin:2px 8px;font-size:11px"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${item.color||colors[i%colors.length]};margin-right:4px"></span>${item.label} ${(item.value/total*100).toFixed(1)}%</span>`;
  });
  html += '</div>';
  el.innerHTML = html;
}

// ── Tab navigation with URL hash ─────────────────────────────────────
function initTabNav(tabNames, loadFn) {
  const hash = location.hash.replace('#', '');
  const active = tabNames.includes(hash) ? hash : tabNames[0];
  tabNames.forEach(name => {
    const btn = document.getElementById('tab-' + name);
    if (!btn || btn.dataset.tabBound === '1') return;
    btn.dataset.tabBound = '1';
    btn.addEventListener('click', () => switchTab(name, tabNames, loadFn));
  });
  switchTab(active, tabNames, loadFn);
  window.addEventListener('hashchange', () => {
    const h = location.hash.replace('#', '');
    if (tabNames.includes(h)) switchTab(h, tabNames, loadFn);
  });
}
function switchTab(name, tabNames, loadFn) {
  location.hash = name;
  tabNames.forEach(t => {
    const content = document.getElementById('tab-content-' + t);
    const btn = document.getElementById('tab-' + t);
    if (content) content.style.display = t === name ? '' : 'none';
    if (btn) btn.classList.toggle('active', t === name);
  });
  if (loadFn) loadFn(name);
}

// ── Date formatting ──────────────────────────────────────────────────
function fmtDate(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleDateString('zh-CN');
}
function fmtDateTime(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString('zh-CN');
}

// Check API health on page load
(async function() {
  try {
    const r = await fetch(`${API}/health`);
    if (r.ok) {
      const el = document.getElementById('api-status');
      if (el) el.innerHTML = '🟢 API 在线';
    }
  } catch (e) {
    const el = document.getElementById('api-status');
    if (el) el.innerHTML = '🔴 API 离线';
  }
})();
