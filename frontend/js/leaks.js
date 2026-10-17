let weeklyChart;

function formatHour(decimalHour) {
  const h = Math.floor(decimalHour);
  const m = Math.round((decimalHour - h) * 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

async function loadLeaks() {
  let path = '/api/anomalies';
  const params = [];
  if (activeFilters.days) params.push('days=' + activeFilters.days);
  if (activeFilters.confirmedOnly) params.push('confirmed_only=true');
  if (params.length) path += '?' + params.join('&');

  const a = await getJSON(path);
  if (a.error) {
    document.getElementById('anomaly-rows').innerHTML = `<tr><td colspan="4">Could not load leak results. ${esc(a.error)}</td></tr>`;
    return;
  }
  if (a.source === 'manual') {
    document.getElementById('anomaly-rows').innerHTML = '<tr><td colspan="4">The Leak Detective needs hourly or 15 minute readings. This household only has daily totals, so there is nothing to check yet.</td></tr>';
    document.getElementById('model-note').textContent = '';
    if (weeklyChart) { weeklyChart.destroy(); weeklyChart = null; }
    document.getElementById('weeklyChart-wrap').innerHTML = '';
    return;
  }
  const rows = a.anomalies.map(x => `
    <tr>
      <td>Day ${x.day}</td>
      <td>${formatHour(x.hour)}</td>
      <td>${x.gallons} gal</td>
      <td>${x.anomaly_score}${x.was_injected_leak ? ' <span class="tag high">confirmed leak</span>' : ''}</td>
    </tr>`).join('');
  document.getElementById('anomaly-rows').innerHTML = rows || '<tr><td colspan="4">No anomalies match the current filters.</td></tr>';
  document.getElementById('model-note').textContent =
    `Model: ${a.model}. Trained on ${a.trained_on_readings.toLocaleString()} readings, 60 days of 15 minute intervals. ${a.anomalies_found} match the current filters.`;

  try {
    if (weeklyChart) weeklyChart.destroy();
    const ctx = freshCanvas('weeklyChart');
    weeklyChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: a.weekly_counts.map((_, i) => 'Week ' + (i + 1)),
        datasets: [{ data: a.weekly_counts, backgroundColor: CHART_COLORS.coral, borderRadius: 8, borderColor: CHART_COLORS.outline, borderWidth: 2, borderSkipped: false }]
      },
      options: {
        plugins: { legend: { display: false } },
        scales: { x: { grid: { display: false } }, y: { grid: { color: GRID }, ticks: { precision: 0 } } }
      }
    });
  } catch {
    document.getElementById('weeklyChart-wrap').textContent = 'Chart library did not load. Weekly counts: ' + a.weekly_counts.join(', ');
  }
}