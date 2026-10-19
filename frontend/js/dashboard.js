let hourlyChart;
let sevenDayChart;

function scoreDetailLine(label, value, max) {
  if (value === null || value === undefined) return `<span><b>n/a</b> ${label}</span>`;
  return `<span><b>${value}</b>/${max} ${label}</span>`;
}

function openTab(name) {
  document.querySelector(`.rail-btn[data-tab="${name}"]`).click();
}

function emptyBanner(html) {
  return `<div class="banner"><div class="mark"></div><p>${html}</p></div>`;
}

async function loadDashboard() {
  const d = await getJSON('/api/dashboard');
  if (d.error) {
    document.getElementById('dash-total').textContent = '–';
    document.getElementById('dash-sub').textContent = 'could not load usage';
    document.getElementById('dash-gauge').style.width = '0%';
    document.getElementById('dash-banner').innerHTML = emptyBanner('<b>Could not load this household.</b> ' + esc(d.error));
    document.getElementById('score-val').textContent = '–';
    return;
  }
  document.getElementById('dash-total').textContent = d.today_total_gallons;
  const pct = Math.min(100, Math.round((d.today_total_gallons / d.daily_limit_gallons) * 100));
  document.getElementById('dash-gauge').style.width = pct + '%';
  const manual = d.source === 'manual';
  document.getElementById('dash-sub').innerHTML = manual && !d.has_data
    ? `no usage added yet, daily budget is ${d.daily_limit_gallons} gal`
    : `used today, against a ${d.daily_limit_gallons} gal budget (${pct}%)`;

  const banner = document.getElementById('dash-banner');
  banner.innerHTML = '';
  if (manual && !d.has_data) {
    banner.innerHTML = emptyBanner('<b>No usage data yet.</b> Add your daily gallons and everything on this screen fills in. <button class="link-btn" id="add-data-link">Add data</button>');
    document.getElementById('add-data-link').addEventListener('click', () => openTab('usage'));
  } else if (manual && d.today_total_gallons === 0 && d.last_entry_date !== localDate()) {
    banner.innerHTML = emptyBanner(`<b>Nothing logged for today yet.</b> The last entry was ${esc(d.last_entry_date)}. <button class="link-btn" id="add-data-link">Add data</button>`);
    document.getElementById('add-data-link').addEventListener('click', () => openTab('usage'));
  }

  if (hourlyChart) { hourlyChart.destroy(); hourlyChart = null; }
  if (!d.hourly_breakdown) {
    document.getElementById('hourlyChart-wrap').innerHTML = '<p class="empty-note">Hourly detail needs hourly meter readings. Usage for this household is entered as daily totals.</p>';
  } else try {
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
  if (s.error) { document.getElementById('score-val').textContent = '–'; document.getElementById('score-detail').textContent = s.error; return; }
  document.getElementById('score-val').textContent = s.score === null ? '–' : s.score;
  document.getElementById('score-detail').innerHTML = s.needs_more_data
    ? `<span>Needs ${s.min_days} days of usage (${s.days_logged} logged)</span>`
    : [
        scoreDetailLine('leak free', s.breakdown.leak_free_usage, 40),
        scoreDetailLine('tier compliance', s.breakdown.tier_compliance, 30),
        scoreDetailLine('consistency', s.breakdown.usage_consistency, 30),
      ].join('');

  const a = await getJSON('/api/anomalies');
  if (a.error) return;
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
