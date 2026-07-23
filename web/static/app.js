// Dashboard data loader
document.addEventListener('DOMContentLoaded', () => {
  fetchDashboard();
  fetchNavHistory();
});

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

    // Fuse indicator
    const fi = document.getElementById('fuse-indicator');
    const fl = d.fuse_level;
    fi.className = fl === 'NORMAL' ? 'fuse-normal' : (fl.includes('BAN') ? 'fuse-ban' : 'fuse-warn');
    fi.innerText = fl === 'NORMAL' ? '风控正常' : '风控: ' + fl;

    // Signals
    let sigHtml = '';
    for (const s of (d.signals || [])) {
      sigHtml += `<tr><td>${s.code||'-'}</td><td>${s.name||'-'}</td><td>${s.theme||''}</td><td>${(s.signal||'').replace('SignalType.','')}</td><td>${(s.score||0).toFixed(2)}</td><td>${s.ma_deviation ? (s.ma_deviation*100).toFixed(1)+'%' : '-'}</td></tr>`;
    }
    document.querySelector('#signals-table tbody').innerHTML = sigHtml || '<tr><td colspan="6">暂无信号</td></tr>';
  } catch(e) { console.error(e); }
}

async function fetchNavHistory() {
  try {
    const res = await fetch('/api/nav/history?days=90');
    const body = await res.json();
    if (!body.success || !body.data.length) return;
    const dates = body.data.map(r => r.snap_date);
    const values = body.data.map(r => r.total_value);
    new Chart(document.getElementById('navChart'), {
      type: 'line',
      data: { labels: dates, datasets: [{ label: '净值', data: values, borderColor: '#1a1a2e', tension: 0.2, pointRadius: 0 }] },
      options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: false } } }
    });
  } catch(e) { console.error(e); }
}
