let hourlyChart;

async function loadDashboard() {
  const d = await getJSON('/api/dashboard');
  document.getElementById('dash-total').textContent = d.today_total_gallons;
  document.getElementById('dash-limit').textContent = d.daily_limit_gallons;
  const pct = Math.min(100, Math.round((d.today_total_gallons / d.daily_limit_gallons) * 100));
  document.getElementById('dash-gauge').style.width = pct + '%';
  document.getElementById('dash-sub').textContent = `${pct}% of daily budget used`;

  const ctx = document.getElementById('hourlyChart');
  if (hourlyChart) hourlyChart.destroy();
  hourlyChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: [...Array(24).keys()].map(h => h + ':00'),
      datasets: [{ data: d.hourly_breakdown, backgroundColor: '#2E8FA6', borderRadius: 2 }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
        y: { grid: { color: '#EEF2F1' } }
      }
    }
  });

  const s = await getJSON('/api/score');
  document.getElementById('score-val').textContent = s.score;
  document.getElementById('score-ring').style.setProperty('--pct', s.score);

  const a = await getJSON('/api/anomalies');
  const banner = document.getElementById('dash-banner');
  if (a.anomalies_found > 0) {
    banner.innerHTML = `<div class="banner"><div class="dot"></div><p><b>${a.anomalies_found} unusual intervals</b> detected in the last 60 days by the Leak Detective model. <a href="#" onclick="document.querySelector('[data-tab=leaks]').click();return false;">Review them →</a></p></div>`;
  }
}
