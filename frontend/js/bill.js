const BILL_MAX_SIDE = 1800;
let billFile = null;

function billMsg(id, text, bad) {
  const el = document.getElementById(id);
  el.textContent = text || '';
  el.className = 'set-msg' + (text ? (bad ? ' bad' : ' ok') : '');
}

function billMoney(x) {
  return x === null || x === undefined ? 'Not found' : '$' + Number(x).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function billNum(x) {
  return x === null || x === undefined ? 'Not found' : Number(x).toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function billCard(label, value) {
  return `<div class="bill-stat"><span>${esc(label)}</span><b>${esc(value)}</b></div>`;
}

function shrinkImage(file) {
  return new Promise((resolve) => {
    if (!file.type.startsWith('image/')) return resolve(file);
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, BILL_MAX_SIDE / Math.max(img.width, img.height));
      if (scale === 1 && file.size < 1.5 * 1024 * 1024) { URL.revokeObjectURL(url); return resolve(file); }
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      canvas.toBlob(b => resolve(b || file), 'image/jpeg', 0.88);
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(null); };
    img.src = url;
  });
}

function billLock() {
  const signedIn = isSignedIn();
  document.getElementById('bill-main').hidden = !signedIn;
  document.getElementById('bill-locked').hidden = signedIn;
}

document.getElementById('bill-locked-btn').addEventListener('click', () => openAuthForm('register'));

document.querySelector('.rail-btn[data-tab="bill"]').addEventListener('click', billLock);
document.querySelectorAll('.rail-btn[data-tab]').forEach(b => { if (b.dataset.tab !== 'bill') b.addEventListener('click', stopBillCamera); });

let billStream = null;

function stopBillCamera() {
  if (billStream) billStream.getTracks().forEach(t => t.stop());
  billStream = null;
  document.getElementById('bill-camera-panel').hidden = true;
}

document.getElementById('bill-camera-btn').addEventListener('click', async () => {
  const fallback = () => document.getElementById('bill-camera').click();
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return fallback();
  stopBillCamera();
  try {
    billStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 } }, audio: false });
  } catch (err) {
    const denied = err && (err.name === 'NotAllowedError' || err.name === 'SecurityError');
    billMsg('bill-msg', denied
      ? 'Camera access was blocked. Allow the camera for this site in your browser, or choose a file instead.'
      : 'No camera was found. Choose a file instead.', true);
    return;
  }
  const video = document.getElementById('bill-video');
  video.srcObject = billStream;
  document.getElementById('bill-camera-panel').hidden = false;
  billMsg('bill-msg', 'Hold the bill flat, fill the frame, then press Capture.');
});

document.getElementById('bill-capture').addEventListener('click', () => {
  const video = document.getElementById('bill-video');
  if (!video.videoWidth) return billMsg('bill-msg', 'The camera is still starting. Try again in a second.', true);
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  canvas.toBlob(blob => {
    if (!blob) return billMsg('bill-msg', 'Could not take the photo. Try again.', true);
    stopBillCamera();
    document.getElementById('bill-file').value = '';
    chooseBill(new File([blob], 'bill.jpg', { type: 'image/jpeg' }));
  }, 'image/jpeg', 0.9);
});

document.getElementById('bill-camera-cancel').addEventListener('click', () => {
  stopBillCamera();
  billMsg('bill-msg', '');
});

document.getElementById('bill-camera').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  document.getElementById('bill-file').value = '';
  chooseBill(file);
  e.target.value = '';
});

document.getElementById('bill-file').addEventListener('change', (e) => chooseBill(e.target.files[0]));

function chooseBill(file) {
  billFile = null;
  document.getElementById('bill-scan').disabled = true;
  document.getElementById('bill-result').hidden = true;
  const preview = document.getElementById('bill-preview');
  preview.hidden = true;
  if (!file) return billMsg('bill-msg', '');
  if (file.size > 25 * 1024 * 1024) return billMsg('bill-msg', 'That file is too large. Keep it under 25 MB.', true);
  if (!/^(image\/(jpeg|png|webp)|application\/pdf)$/.test(file.type)) {
    return billMsg('bill-msg', 'Use a JPG, PNG, WebP or PDF file. iPhone HEIC photos need to be saved as JPG first.', true);
  }
  billFile = file;
  if (file.type.startsWith('image/')) {
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
  }
  document.getElementById('bill-scan').disabled = false;
  billMsg('bill-msg', 'Ready. Press Scan bill.');
}

document.getElementById('bill-scan').addEventListener('click', async () => {
  if (!billFile) return;
  const btn = document.getElementById('bill-scan');
  btn.disabled = true;
  document.getElementById('bill-result').hidden = true;
  billMsg('bill-msg', 'Reading your bill. This can take up to a minute.');
  const upload = await shrinkImage(billFile);
  if (!upload) {
    btn.disabled = false;
    return billMsg('bill-msg', 'That image could not be opened. Try a JPG or PNG.', true);
  }
  if (upload.size > 8 * 1024 * 1024) {
    btn.disabled = false;
    return billMsg('bill-msg', 'That file is too large after resizing. Use a smaller PDF or a photo.', true);
  }
  const form = new FormData();
  form.append('file', upload, upload.type === 'application/pdf' ? 'bill.pdf' : 'bill.jpg');
  const res = await getJSON('/api/bill', { method: 'POST', body: form });
  btn.disabled = false;
  if (res.error) return billMsg('bill-msg', res.error, true);
  billMsg('bill-msg', '');
  showBill(res.bill);
});

let scannedBill = null;

function showBill(b) {
  scannedBill = b;
  const period = b.billing_period_start && b.billing_period_end ? `${b.billing_period_start} to ${b.billing_period_end}` : 'Not found';
  document.getElementById('bill-stats').innerHTML =
    billCard('Total due', billMoney(b.total_amount_due)) +
    billCard('Water used', b.usage_gallons === null ? 'Not found' : billNum(b.usage_gallons) + ' gal') +
    billCard('Billing period', period) +
    billCard('Due date', b.due_date || 'Not found') +
    (b.gallons_per_day === null ? '' : billCard('Per day', billNum(b.gallons_per_day) + ' gal'));
  document.getElementById('bill-explain').textContent = b.explanation;

  const warn = document.getElementById('bill-warn');
  warn.hidden = !b.warnings.length;
  warn.textContent = b.warnings.join(' ');

  const unit = b.usage_unit_name ? ' ' + b.usage_unit_name : '';
  const rows = b.tiers.map(t => `<tr><td>${esc(t.name)}</td><td>${t.usage_amount === null ? '' : esc(billNum(t.usage_amount)) + esc(unit)}</td><td>${t.rate_per_unit === null ? '' : esc(billMoney(t.rate_per_unit))}</td><td>${t.charge === null ? '' : esc(billMoney(t.charge))}</td></tr>`)
    .concat(b.other_charges.map(c => `<tr><td>${esc(c.name)}</td><td></td><td></td><td>${esc(billMoney(c.amount))}</td></tr>`));
  document.getElementById('bill-tier-table').hidden = !rows.length;
  document.getElementById('bill-rows').innerHTML = rows.join('');

  document.getElementById('bill-save').hidden = false;
  billMsg('bill-save-msg', '');
  document.getElementById('bill-save-btn').disabled = false;
  const logBox = document.getElementById('bill-log');
  logBox.hidden = !b.can_log;
  billMsg('bill-log-msg', '');
  if (b.can_log) {
    document.getElementById('bill-log-note').textContent =
      `This adds ${b.days} days, ${b.billing_period_start} to ${b.billing_period_end}, at about ${billNum(b.gallons_per_day)} gallons a day. A bill only shows the total for the period, so each day is an estimate. It replaces any days you already entered for these dates.`;
  }
  document.getElementById('bill-result').hidden = false;
}

function billDays(start, end) {
  const out = [];
  const d = new Date(start + 'T12:00:00');
  const stop = new Date(end + 'T12:00:00');
  while (d <= stop) { out.push(localDate(d)); d.setDate(d.getDate() + 1); }
  return out;
}

document.getElementById('bill-log-btn').addEventListener('click', async () => {
  const b = scannedBill;
  if (!b || !b.can_log) return;
  const list = await getJSON('/api/profiles');
  const cur = Array.isArray(list) ? list.find(p => p.id === currentProfileId) : null;
  if (!cur || cur.owner_id !== currentUser.id) {
    return billMsg('bill-log-msg', 'Choose one of your own households at the top of the page first. The Demo household cannot be changed.', true);
  }
  const btn = document.getElementById('bill-log-btn');
  btn.disabled = true;
  const entries = billDays(b.billing_period_start, b.billing_period_end).map(date => ({ date, gallons: b.gallons_per_day }));
  const res = await getJSON('/api/usage', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ entries }),
  });
  btn.disabled = false;
  if (res.error) return billMsg('bill-log-msg', res.error, true);
  billMsg('bill-log-msg', `Added ${res.saved} days to ${cur.name}.`);
  await reloadAllTabs();
});

billLock();

async function ownHousehold() {
  if (!isSignedIn()) return null;
  const list = await getJSON('/api/profiles');
  const cur = Array.isArray(list) ? list.find(p => p.id === currentProfileId) : null;
  return cur && cur.owner_id === currentUser.id ? cur : null;
}

async function loadBills() {
  const rows = document.getElementById('bill-history-rows');
  const own = await ownHousehold();
  document.getElementById('bill-history').hidden = !own;
  if (!own) return;
  const res = await getJSON('/api/bills');
  if (res.error) { rows.innerHTML = `<tr><td colspan="4">${esc(res.error)}</td></tr>`; return; }
  const bills = res.bills || [];
  document.getElementById('bill-count').textContent = bills.length ? `(${bills.length})` : '';
  rows.innerHTML = bills.length
    ? bills.map(b => {
        const d = b.data;
        const period = d.billing_period_start ? `${d.billing_period_start} to ${d.billing_period_end}` : 'Saved ' + b.created.slice(0, 10);
        return `<tr><td>${esc(period)}</td><td>${d.usage_gallons === null ? '' : esc(billNum(d.usage_gallons)) + ' gal'}</td><td>${esc(billMoney(d.total_amount_due))}</td>
          <td><button class="btn btn-quiet btn-sm" data-view="${esc(b.id)}" type="button">View</button>
          <button class="btn btn-quiet btn-sm btn-delete" data-del-bill="${esc(b.id)}" type="button">Delete</button></td></tr>`;
      }).join('')
    : '<tr><td colspan="4"><p class="empty-note">No saved bills yet. Scan a bill, then press Save to past bills.</p></td></tr>';
  rows.dataset.bills = JSON.stringify(bills);
}

document.getElementById('bill-save-btn').addEventListener('click', async () => {
  if (!scannedBill) return;
  const own = await ownHousehold();
  if (!own) return billMsg('bill-save-msg', 'Choose one of your own households at the top of the page first. The Demo household cannot save bills.', true);
  const btn = document.getElementById('bill-save-btn');
  btn.disabled = true;
  const res = await getJSON('/api/bills', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bill: scannedBill }),
  });
  if (res.error) { btn.disabled = false; return billMsg('bill-save-msg', res.error, true); }
  billMsg('bill-save-msg', res.replaced ? `Saved to ${own.name}. This replaced an earlier save for the same billing period.` : `Saved to ${own.name}.`);
  await loadBills();
});

document.getElementById('bill-history-rows').addEventListener('click', async (e) => {
  const view = e.target.dataset && e.target.dataset.view;
  const del = e.target.dataset && e.target.dataset.delBill;
  if (view) {
    const bills = JSON.parse(document.getElementById('bill-history-rows').dataset.bills || '[]');
    const found = bills.find(b => b.id === view);
    if (found) { showBill(found.data); document.getElementById('bill-result').scrollIntoView({ behavior: 'smooth' }); }
  } else if (del) {
    const res = await getJSON('/api/bills?id=' + encodeURIComponent(del), { method: 'DELETE' });
    if (res.error) return billMsg('bill-msg', res.error, true);
    await loadBills();
  }
});