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
  const head = document.getElementById('anomaly-head');
  const intro = document.getElementById('leaks-intro');
  let rows, note;
  if (a.source === 'manual') {
    intro.textContent = 'This household has daily totals, so the Leak Detective checks for unusually high days compared with its own recent normal. A steady leak often shows up as a run of high days. Hourly or 15 minute readings would let it find leaks within a day.';
    head.innerHTML = '<tr><th>Date</th><th>Gallons</th><th>Typical day</th><th>Score</th></tr>';
    if (a.days_checked < a.min_days) {
      document.getElementById('anomaly-rows').innerHTML = `<tr><td colspan="4">Add at least ${a.min_days} days of data to check for unusual days. This household has ${a.days_checked} in the last 60 days.</td></tr>`;
      document.getElementById('model-note').textContent = '';
      if (weeklyChart) { weeklyChart.destroy(); weeklyChart = null; }
      document.getElementById('weeklyChart-wrap').innerHTML = '';
      return;
    }
    rows = a.unusual_days.map(x => `
    <tr>
      <td>${esc(x.date)}</td>
      <td>${esc(x.gallons)} gal</td>
      <td>${esc(x.typical)} gal</td>
      <td>${esc(x.score)}</td>
    </tr>`).join('');
    rows = rows || '<tr><td colspan="4">No unusual days found. Usage looks steady.</td></tr>';
    note = `Method: ${a.model}. Checked ${a.days_checked} days. A day is flagged when its score is above 3.5, a common cutoff for this method.`;
  } else {
    intro.textContent = "An Isolation Forest model, trained on 60 days of this household's own 15 minute usage history, flags intervals that don't fit its learned normal. No fixed gallons per minute threshold involved.";
    head.innerHTML = '<tr><th>Day</th><th>Hour</th><th>Gallons, 15 min</th><th>Anomaly score</th></tr>';
    rows = a.anomalies.map(x => `
    <tr>
      <td>Day ${x.day}</td>
      <td>${formatHour(x.hour)}</td>
      <td>${x.gallons} gal</td>
      <td>${x.anomaly_score}${x.was_injected_leak ? ' <span class="tag high">confirmed leak</span>' : ''}</td>
    </tr>`).join('');
    rows = rows || '<tr><td colspan="4">No anomalies match the current filters.</td></tr>';
    note = `Model: ${a.model}. Trained on ${a.trained_on_readings.toLocaleString()} readings, 60 days of 15 minute intervals. ${a.anomalies_found} match the current filters.`;
  }
  document.getElementById('anomaly-rows').innerHTML = rows;
  document.getElementById('model-note').textContent = note;

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