let mobilenetModel = null;
let classifiedCategory = null;
let userLat = null, userLon = null;

async function ensureModel() {
  if (!mobilenetModel) {
    document.getElementById('cnn-result').innerHTML = '<span class="loading">Loading MobileNetV2 in the browser</span>';
    mobilenetModel = await mobilenet.load();
  }
}

function severityTagClass(severity) {
  if (severity === 'critical') return 'crit';
  if (severity === 'high') return 'high';
  return 'med';
}

document.getElementById('drop-zone').addEventListener('click', () => document.getElementById('file-input').click());

document.getElementById('file-input').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const img = new Image();
  img.src = URL.createObjectURL(file);
  await img.decode();

  await ensureModel();
  const predictions = await mobilenetModel.classify(img);

  const labels = await getJSON('/api/cnn-labels');
  const match = predictions.find(p => Object.keys(labels).some(k => p.className.toLowerCase().includes(k)));
  const key = match ? Object.keys(labels).find(k => match.className.toLowerCase().includes(k)) : null;
  classifiedCategory = key;

  const top = predictions[0];
  let html = `<p><b>Top match:</b> ${top.className} (${Math.round(top.probability * 100)}% confidence)</p>`;
  if (key) {
    const info = labels[key];
    html += `<p><b>Classified as:</b> ${info.label} <span class="tag ${severityTagClass(info.severity)}">${info.severity}</span>, est. ${info.est_gal_per_min} gal/min</p>`;
  } else {
    html += `<p>No specific water waste category matched. You can still submit a general report.</p>`;
  }
  document.getElementById('cnn-result').innerHTML = html;
  maybeEnableSubmit();
});

document.getElementById('loc-btn').addEventListener('click', () => {
  if (!navigator.geolocation) {
    document.getElementById('loc-result').textContent = 'Geolocation not available in this browser.';
    return;
  }
  navigator.geolocation.getCurrentPosition(pos => {
    userLat = pos.coords.latitude.toFixed(5);
    userLon = pos.coords.longitude.toFixed(5);
    document.getElementById('loc-result').textContent = `Location captured: ${userLat}, ${userLon}`;
    maybeEnableSubmit();
  }, () => {
    document.getElementById('loc-result').textContent = 'Could not get location. You can still submit without it.';
  });
});

function maybeEnableSubmit() {
  document.getElementById('submit-btn').disabled = false;
}

document.getElementById('submit-btn').addEventListener('click', async () => {
  const res = await getJSON('/api/civic-report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ category: classifiedCategory || 'unclassified', lat: userLat, lon: userLon })
  });
  document.getElementById('report-result').innerHTML =
    `<div class="model-note"><b>Report ${res.report_id} generated.</b><br><br>${res.email_draft.replace(/\n/g, '<br>')}</div>`;
});
