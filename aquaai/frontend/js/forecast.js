let forecastChart;
let tierChart;

function forecastBannerHTML(f) {
  if (f.has_data === false) {
    return `
      <div class="banner">
        <div class="mark"></div>
        <p><b>No usage data yet.</b> Projections start once you add your daily gallons.
        <button class="link-btn" id="forecast-add-data">Add data</button></p>
      </div>`;
  }
  if (f.tier_breach_day_of_month) {
    return `
      <div class="banner">
        <div class="mark"></div>
        <p>Based on the <b>${f.weather_source}</b> forecast, usage is projected to cross into
        <b>Tier 2 pricing around day ${f.tier_breach_day_of_month}</b> of the month, adding roughly
        <b>$${f.bill_estimate_dollars}</b> to the bill.</p>
      </div>`;
  }
  return `
    <div class="banner ok">
      <div class="mark"></div>
      <p>On track to stay within Tier 1 this month. Weather source: <b>${f.weather_source}</b>.</p>
    </div>`;
}

async function loadForecast() {
  const f = await getJSON('/api/forecast');
  document.getElementById('forecast-banner').innerHTML = forecastBannerHTML(f);
  const addLink = document.getElementById('forecast-add-data');
  if (addLink) addLink.addEventListener('click', () => openTab('usage'));

  document.getElementById('fc-used').textContent = f.month_used_so_far.toLocaleString();
  document.getElementById('fc-remaining').textContent = Math.round(f.gallons_to_tier2).toLocaleString();
  document.getElementById('fc-bill').textContent = '$' + f.bill_estimate_dollars;

  try {
    if (forecastChart) forecastChart.destroy();
    const ctx = freshCanvas('forecastChart');
    forecastChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: f.projected_daily.map(d => `+${d.day_offset}d, ${d.high_f}°F`),
        datasets: [{ data: f.projected_daily.map(d => d.gallons), borderColor: CHART_COLORS.water, backgroundColor: CHART_COLORS.waterFill, pointBackgroundColor: CHART_COLORS.violet, borderWidth: 3, fill: true, tension: .25 }]
      },
      options: { plugins: { legend: { display: false } }, scales: { y: { grid: { color: GRID } }, x: { grid: { display: false } } } }
    });
  } catch {
    document.getElementById('forecastChart-wrap').textContent = 'Chart library did not load.';
  }

  try {
    if (tierChart) tierChart.destroy();
    const usedShare = Math.min(f.month_used_so_far, f.tier1_limit_gallons);
    const remainingShare = Math.max(0, f.tier1_limit_gallons - f.month_used_so_far);
    const ctxT = freshCanvas('tierChart');
    tierChart = new Chart(ctxT, {
      type: 'doughnut',
      data: {
        labels: ['Used', 'Remaining'],
        datasets: [{ data: [usedShare, remainingShare], backgroundColor: [CHART_COLORS.sand, CHART_COLORS.track], borderWidth: 2, borderColor: CHART_COLORS.outline }]
      },
      options: { plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } } }, cutout: '65%' }
    });
  } catch {
    document.getElementById('tierChart-wrap').textContent = 'Chart library did not load.';
  }

  document.getElementById('tips-list').innerHTML = f.savings_tips.map(t => `<li>${esc(t)}</li>`).join('');

  const sv = await getJSON('/api/savings');
  document.getElementById('sv-month').textContent = sv.gallons_saved_this_month.toLocaleString();
  document.getElementById('sv-year').textContent = sv.gallons_saved_projected_year.toLocaleString();
  document.getElementById('sv-dollars').textContent = '$' + sv.dollars_saved_projected_year.toLocaleString();
  document.getElementById('badges-row').innerHTML = sv.badges.map(b => `<span class="earned">${esc(b)}</span>`).join('');
}
