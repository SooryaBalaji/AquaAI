let forecastChart;

async function loadForecast() {
  const f = await getJSON('/api/forecast');
  const banner = document.getElementById('forecast-banner');
  if (f.tier_breach_day_of_month) {
    banner.innerHTML = `<div class="banner"><div class="dot"></div><p>Based on the <b>${f.weather_source}</b> forecast, usage is projected to cross into <b>Tier 2 pricing around day ${f.tier_breach_day_of_month}</b> of the month, adding roughly <b>$${f.bill_estimate_dollars}</b> to the bill.</p></div>`;
  } else {
    banner.innerHTML = `<div class="banner" style="background:#E4EEEA;border-color:#C7DFCD"><div class="dot" style="background:var(--leaf)"></div><p>On track to stay within Tier 1 this month. Weather source: <b>${f.weather_source}</b>.</p></div>`;
  }

  document.getElementById('fc-used').textContent = f.month_used_so_far.toLocaleString();
  document.getElementById('fc-remaining').textContent = Math.round(f.gallons_to_tier2).toLocaleString();
  document.getElementById('fc-bill').textContent = '$' + f.bill_estimate_dollars;

  const ctx = document.getElementById('forecastChart');
  if (forecastChart) forecastChart.destroy();
  forecastChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: f.projected_daily.map(d => `+${d.day_offset}d (${d.high_f}°F)`),
      datasets: [{ data: f.projected_daily.map(d => d.gallons), borderColor: '#0F5257', backgroundColor: 'rgba(15,82,87,.08)', fill: true, tension: .3 }]
    },
    options: { plugins: { legend: { display: false } }, scales: { y: { grid: { color: '#EEF2F1' } }, x: { grid: { display: false } } } }
  });

  document.getElementById('tips-list').innerHTML = f.savings_tips.map(t => `<li>${t}</li>`).join('');

  const sv = await getJSON('/api/savings');
  document.getElementById('sv-month').textContent = sv.gallons_saved_this_month.toLocaleString();
  document.getElementById('sv-year').textContent = sv.gallons_saved_projected_year.toLocaleString();
  document.getElementById('sv-dollars').textContent = '$' + sv.dollars_saved_projected_year.toLocaleString();
  document.getElementById('badges-row').innerHTML = sv.badges.map(b => `<span class="earned">✓ ${b}</span>`).join('') || '<span class="hero-sub">No badges yet this month.</span>';
}
