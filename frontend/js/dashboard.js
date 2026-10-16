let hourlyChart;
let sevenDayChart;

function scoreDetailLine(label, value, max) {
  return `<span><b>${value}</b>/${max} ${label}</span>`;
}

async function loadDashboard() {
  const d = await getJSON('/api/dashboard');
  document.getElementById('dash-total').textContent = d.today_total_gallons;
  const pct = Math.min(100, Math.round((d.today_total_gallons / d.daily_limit_gallons) * 100));
  document.getElementById('dash-gauge').style.width = pct + '%';
  document.getElementById('dash-sub').innerHTML = `used today, against a ${d.daily_limit_gallons} gal budget (${pct}%)`;

  try {
    if (hourlyChart) hourlyChart.destroy();
    const ctx = freshCanvas('hourlyChart');
    hourlyChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: [...Array(24).keys()].map(h => h + ':00'),
        datasets: [{ data: d.hourly_breakdown, backgroundColor: CHART_COLORS.water, borderRadius: 8, borderColor: CHART_COLORS.outline, borderWidth: 2, borderSkipped: false }]
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
          y: { grid: { color: GRID } }
        }
      }
    });
  } catch {
    document.getElementById('hourlyChart-wrap').textContent = 'Chart library did not load. Hourly data: ' + d.hourly_breakdown.join(', ');
  }

  try {
    if (sevenDayChart) sevenDayChart.destroy();
    const ctx7 = freshCanvas('sevenDayChart');
    const dayLabels = ['6 days ago', '5 days ago', '4 days ago', '3 days ago', '2 days ago', 'Yesterday', 'Today'];
    sevenDayChart = new Chart(ctx7, {
      type: 'bar',
      data: {
        labels: dayLabels,
        datasets: [{ data: d.last_7_days_gallons, backgroundColor: CHART_COLORS.sand, borderRadius: 8, borderColor: CHART_COLORS.outline, borderWidth: 2, borderSkipped: false }]
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { maxRotation: 0 }, grid: { display: false } },
          y: { grid: { color: GRID } }
        }
      }
    });
  } catch {
    document.getElementById('sevenDayChart-wrap').textContent = 'Chart library did not load. Last 7 days: ' + d.last_7_days_gallons.join(', ');
  }

  const tankEl = document.getElementById('day-tank');
  if (tankEl) renderTank(tankEl, d.today_total_gallons, d.daily_limit_gallons);

  const s = await getJSON('/api/score');
  document.getElementById('score-val').textContent = s.score;
  document.getElementById('score-detail').innerHTML = [
    scoreDetailLine('leak free', s.breakdown.leak_free_usage, 40),
    scoreDetailLine('tier compliance', s.breakdown.tier_compliance, 30),
    scoreDetailLine('consistency', s.breakdown.usage_consistency, 30),
  ].join('');

  const a = await getJSON('/api/anomalies');
  const banner = document.getElementById('dash-banner');
  if (a.anomalies_found > 0) {
    banner.innerHTML = `
      <div class="banner">
        <div class="mark"></div>
        <p><b>${a.anomalies_found} unusual intervals</b> were found in the last 60 days by the Leak Detective model.
        <button class="link-btn" id="review-leaks-btn">Review them</button></p>
      </div>`;
    document.getElementById('review-leaks-btn').addEventListener('click', () => document.querySelector('[data-tab=leaks]').click());
  }
}
