async function loadLeaks() {
  const a = await getJSON('/api/anomalies');
  const rows = a.anomalies.map(x => `
    <tr>
      <td>Day ${x.day}</td>
      <td>${x.hour}:00</td>
      <td>${x.gallons} gal</td>
      <td>${x.anomaly_score}${x.was_injected_leak ? ' &nbsp;<span class="badge high">confirmed leak</span>' : ''}</td>
    </tr>`).join('');
  document.getElementById('anomaly-rows').innerHTML = rows || '<tr><td colspan="4">No anomalies found.</td></tr>';
  document.getElementById('model-note').textContent =
    `Model: ${a.model} — trained on ${a.trained_on_readings.toLocaleString()} readings (60 days × 15-minute intervals), ${a.anomalies_found} flagged as anomalous.`;
}
