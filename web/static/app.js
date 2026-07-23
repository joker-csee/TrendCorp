// ── Dashboard ──
let navChart = null;

document.addEventListener('DOMContentLoaded', () => {
  fetchDashboard();
  fetchNavHistory();
});

document.body.addEventListener('htmx:afterRequest', (e) => {
  if (e.detail.target.id === 'snapshot-table' || e.detail.target.id === 'scan-result') {
    try {
      const d = JSON.parse(e.detail.xhr.responseText);
      if (d.success) renderScanner(d.data, e.detail.target.id);
      else e.detail.target.innerHTML = '<p class="neg">' + d.message + '</p>';
    } catch(_) {}
  }
  if (e.detail.target.id === 'pos-table') {
    try {
      const d = JSON.parse(e.detail.xhr.responseText);
      if (d.success) renderPositions(d.data);
      else document.getElementById('pos-table').innerHTML = '<p class="neg">' + d.message + '</p>';
    } catch(_) {}
  }
  if (e.detail.target.id === 'risk-events') {
    try {
      const d = JSON.parse(e.detail.xhr.responseText);
      if (d.success) renderRisk(d.data);
      else document.getElementById('risk-events').innerHTML = '<p class="neg">' + d.message + '</p>';
    } catch(_) {}
  }
  if (e.detail.target.id === 'report-content') {
    try {
      const d = JSON.parse(e.detail.xhr.responseText);
      if (d.success) renderReport(d.data);
      else document.getElementById('report-content').innerHTML = '<p class="neg">' + d.message + '</p>';
    } catch(_) {}
  }
  if (e.detail.target.id === 'log-result') {
    try {
      const d = JSON.parse(e.detail.xhr.responseText);
      if (d.success) {
        e.detail.target.innerHTML = '<p class="pos">已录入: ' + d.data.trade_no + '</p>';
        fetchDashboard();
      } else {
        e.detail.target.innerHTML = '<p class="neg">' + d.message + '</p>';
      }
    } catch(_) {}
  }
});

// ── Rendering helpers ──

function renderScanner(data, targetId) {
  if (!data || !data.length) {
    document.getElementById(targetId).innerHTML = '<p>暂无扫描数据</p>';
    return;
  }
  let h = '<table class="data-table"><thead><tr><th>板块</th><th>总分</th><th>趋势</th><th>相对</th><th>资金</th><th>梯队</th><th>状态</th></tr></thead><tbody>';
  for (const r of data) {
    const status = r.is_confirmed === 2 ? '确认' : r.is_confirmed === 1 ? '观察' : '排除';
    h += `<tr><td>${r.sector_name||'-'}</td><td>${(r.total_score||0).toFixed(2)}</td><td>${(r.trend_score||0).toFixed(2)}</td><td>${(r.rel_strength||0).toFixed(2)}</td><td>${(r.fund_score||0).toFixed(2)}</td><td>${(r.echelon_score||0).toFixed(2)}</td><td>${status}</td></tr>`;
  }
  h += '</tbody></table>';
  document.getElementById(targetId).innerHTML = h;
}

function renderPositions(data) {
  let h = '';
  if (!data || !data.length) {
    h = '<tr><td colspan="7">暂无持仓</td></tr>';
  } else {
    h += '<thead><tr><th>ID</th><th>代码</th><th>成本</th><th>占比</th><th>浮盈</th><th>MA10</th><th>预警</th></tr></thead><tbody>';
    for (const p of data) {
      const pnl = p.unrealized_pnl ? (p.unrealized_pnl > 0 ? '<span class="pos">+' + p.unrealized_pnl.toFixed(2) + '</span>' : '<span class="neg">' + p.unrealized_pnl.toFixed(2) + '</span>') : '-';
      h += `<tr><td>${p.stock_id||'-'}</td><td>${p.stock_code||'-'}</td><td>${(p.avg_cost||0).toFixed(2)}</td><td>${((p.position_pct||0)*100).toFixed(0)}%</td><td>${pnl}</td><td>${p.ma10_status||'-'}</td><td>${p.sector_alert?'预警':'-'}</td></tr>`;
    }
    h += '</tbody>';
  }
  document.getElementById('pos-table').innerHTML = h;

  // P0-2: Also populate holdings-table on dashboard
  const ht = document.querySelector('#holdings-table tbody');
  if (ht && data.length) {
    let hh = '';
    for (const p of data) {
      const pnl = p.unrealized_pnl ? (p.unrealized_pnl > 0 ? '<span class="pos">+' + (p.unrealized_pnl*100).toFixed(1) + '%</span>' : '<span class="neg">' + (p.unrealized_pnl*100).toFixed(1) + '%</span>') : '-';
      hh += `<tr><td>${p.stock_code||'-'}</td><td>${p.stock_name||'-'}</td><td>${'-'}</td><td>${pnl}</td><td>${p.ma10_status||'-'}</td><td>${p.sector_alert?'预警':'-'}</td></tr>`;
    }
    ht.innerHTML = hh;
  }
}

function renderRisk(data) {
  if (!data || !data.length) {
    document.getElementById('risk-events').innerHTML = '<p>暂无风控事件</p>';
    return;
  }
  let h = '<table class="data-table"><thead><tr><th>时间</th><th>类型</th><th>级别</th><th>详情</th></tr></thead><tbody>';
  for (const r of data) {
    h += `<tr><td>${(r.event_time||'').substring(0,19)}</td><td>${r.event_type}</td><td>${r.event_level}</td><td>${r.detail||''}</td></tr>`;
  }
  h += '</tbody></table>';
  document.getElementById('risk-events').innerHTML = h;
}

function renderReport(data) {
  let h = '<div class="cards" style="margin-bottom:16px">';
  h += `<div class="card"><span class="label">交易笔数</span><span class="value">${data.trade_count||0}</span></div>`;
  h += `<div class="card"><span class="label">胜率</span><span class="value">${data.win_rate||0}%</span></div>`;
  h += `<div class="card"><span class="label">月收益</span><span class="value">${(data.monthly_return||0).toFixed(1)}%</span></div>`;
  h += `<div class="card"><span class="label">盈亏比</span><span class="value">${data.avg_win_loss_ratio||0}</span></div>`;
  h += '</div>';
  h += `<p>最大单笔盈利: ${data.max_single_win_pct||0}% | 最大单笔亏损: ${data.max_single_loss_pct||0}% | 违规: ${data.violation_count||0}次</p>`;
  h += `<p style="color:#888">${data.summary||''}</p>`;

  if (data.by_signal && Object.keys(data.by_signal).length) {
    h += '<h2>按买点归因</h2><table class="data-table"><thead><tr><th>类型</th><th>笔数</th><th>胜率</th><th>均收益</th></tr></thead><tbody>';
    for (const [k, v] of Object.entries(data.by_signal)) {
      h += `<tr><td>${k}</td><td>${v.count}</td><td>${v.win_rate||0}%</td><td>${(v.avg_return||0).toFixed(1)}%</td></tr>`;
    }
    h += '</tbody></table>';
  }
  document.getElementById('report-content').innerHTML = h;
}

// ── Dashboard data fetch ──

async function fetchDashboard() {
  try {
    const res = await fetch('/api/dashboard');
    const body = await res.json();
    if (!body.success) { console.warn(body.message); return; }
    const d = body.data;
    document.getElementById('nav-total').innerText = '¥' + d.total_nav.toLocaleString();
    document.getElementById('nav-daily').innerText = (d.daily_return * 100).toFixed(2) + '%';
    document.getElementById('nav-weekly').innerText = (d.weekly_return * 100).toFixed(2) + '%';
    document.getElementById('nav-monthly').innerText = (d.monthly_return * 100).toFixed(2) + '%';
    document.getElementById('nav-pos').innerText = (d.position_pct * 100).toFixed(0) + '%';
    document.getElementById('nav-cash').innerText = '¥' + d.cash.toLocaleString();

    const fi = document.getElementById('fuse-indicator');
    const fl = d.fuse_level;
    fi.className = fl === 'NORMAL' ? 'fuse-normal' : (fl.includes('BAN') ? 'fuse-ban' : 'fuse-warn');
    fi.innerText = fl === 'NORMAL' ? '风控正常' : '风控: ' + fl;

    // P0-2: Fetch positions to fill holdings table
    try {
      const pr = await fetch('/api/positions');
      const pb = await pr.json();
      if (pb.success) renderPositions(pb.data);
    } catch(_) {}

    let sigHtml = '';
    for (const s of (d.signals || [])) {
      sigHtml += `<tr><td>${s.code||'-'}</td><td>${s.name||'-'}</td><td>${s.theme||''}</td><td>${(s.signal||'').replace('SignalType.','')}</td><td>${(s.score||0).toFixed(2)}</td><td>${s.ma_deviation ? (s.ma_deviation*100).toFixed(1)+'%' : '-'}</td></tr>`;
    }
    document.querySelector('#signals-table tbody').innerHTML = sigHtml || '<tr><td colspan="6">暂无信号</td></tr>';
  } catch(e) { console.error(e); }
}

// ── Nav chart ──

async function fetchNavHistory() {
  try {
    const res = await fetch('/api/nav/history?days=90');
    const body = await res.json();
    if (!body.success || !body.data.length) return;
    const dates = body.data.map(r => r.snap_date);
    const values = body.data.map(r => r.total_value);
    const canvas = document.getElementById('navChart');
    // P1-4: Destroy existing chart before creating new one
    const existing = Chart.getChart(canvas);
    if (existing) existing.destroy();
    navChart = new Chart(canvas, {
      type: 'line',
      data: { labels: dates, datasets: [{ label: '净值', data: values, borderColor: '#1a1a2e', backgroundColor: 'rgba(26,26,46,0.05)', tension: 0.2, pointRadius: 0, fill: true }] },
      options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: false } } }
    });
  } catch(e) { console.error(e); }
}
