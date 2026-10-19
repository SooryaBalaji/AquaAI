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

document.getElementById('bill-camera-btn').addEventListener('click', () => document.getElementById('bill-camera').click());

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