const USAGE_CCF_TO_GAL = 748.052;
let usageCsvRows = null;

function usageMsg(id, text, bad) {
  const el = document.getElementById(id);
  el.textContent = text || '';
  el.className = 'set-msg' + (text ? (bad ? ' bad' : ' ok') : '');
}

function parseUsageDate(raw) {
  const s = String(raw || '').trim().replace(/^"|"$/g, '');
  let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  let y, mo, d;
  if (m) { y = +m[1]; mo = +m[2]; d = +m[3]; }
  else {
    m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (!m) return null;
    mo = +m[1]; d = +m[2]; y = +m[3];
  }
  const dt = new Date(y, mo - 1, d);
  if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d) return null;
  return localDate(dt);
}

function parseUsageCsv(text) {
  const rows = [];
  let skipped = 0;
  text.replace(/^﻿/, '').split(/\r?\n/).forEach((line, i) => {
    if (!line.trim()) return;
    const parts = line.split(/[,;\t]/);
    const date = parseUsageDate(parts[0]);
    const gal = parseFloat(String(parts[1] || '').replace(/[",\s]/g, ''));
    if (!date || !isFinite(gal) || gal < 0) {
      if (i > 0) skipped++;          // first line is probably a header
      return;
    }
    rows.push({ date, gallons: gal });
  });
  return { rows, skipped };
}

function usageLock(title, note, btnText, tab) {
  document.getElementById('usage-main').hidden = true;
  document.getElementById('usage-locked').hidden = false;
  document.getElementById('usage-locked-title').textContent = title;
  document.getElementById('usage-locked-note').textContent = note;
  const btn = document.getElementById('usage-locked-btn');
  btn.textContent = btnText;
  btn.onclick = () => {
    if (tab === 'auth') openAuthForm('register');
    else openTab(tab);
  };
}

async function loadUsage() {
  const dateInput = document.getElementById('usage-date');
  dateInput.max = localDate();
  if (!dateInput.value) dateInput.value = localDate();

  if (!isSignedIn()) {
    usageLock('Sign in to add data', 'Create a free account, add a household, then log its water use here.', 'Create account', 'auth');
    return;
  }
  const list = await getJSON('/api/profiles');
  const cur = Array.isArray(list) ? list.find(p => p.id === currentProfileId) : null;
  if (!cur || cur.owner_id !== currentUser.id) {
    usageLock('The Demo household uses sample data', 'Add your own household to log real usage.', 'Go to Households', 'households');
    return;
  }
  document.getElementById('usage-locked').hidden = true;
  document.getElementById('usage-main').hidden = false;
  document.getElementById('usage-for').textContent = cur.name;

  const h = await getJSON('/api/usage');
  const tbody = document.getElementById('usage-rows');
  if (h.error) { tbody.innerHTML = `<tr><td colspan="3">${esc(h.error)}</td></tr>`; return; }
  document.getElementById('usage-count').textContent = h.count ? `(${h.count})` : '';
  document.getElementById('usage-clear').hidden = !h.count;
  tbody.innerHTML = h.count
    ? h.entries.map(e => `<tr><td>${esc(e.date)}</td><td>${esc(e.gallons)}</td>
        <td><button class="btn btn-quiet btn-sm" data-del="${esc(e.date)}" type="button">Delete</button></td></tr>`).join('')
    : '<tr><td colspan="3"><p class="empty-note">Nothing yet. Add your first day above.</p></td></tr>';
}

async function afterUsageChange() {
  await reloadAllTabs();
}

document.getElementById('usage-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const date = document.getElementById('usage-date').value;
  let amount = parseFloat(document.getElementById('usage-amount').value);
  if (!date) return usageMsg('usage-msg', 'Pick a date.', true);
  if (!isFinite(amount) || amount < 0) return usageMsg('usage-msg', 'Enter how much was used, as a number.', true);
  if (document.getElementById('usage-unit').value === 'ccf') amount = Math.round(amount * USAGE_CCF_TO_GAL * 100) / 100;
  const btn = document.getElementById('usage-save');
  btn.disabled = true;
  const res = await getJSON('/api/usage', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entries: [{ date, gallons: amount }] }),
  });
  btn.disabled = false;
  if (res.error) return usageMsg('usage-msg', res.error, true);
  usageMsg('usage-msg', `Saved ${amount} gallons for ${date}.`);
  document.getElementById('usage-amount').value = '';
  await afterUsageChange();
});

document.getElementById('csv-file').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  usageCsvRows = null;
  document.getElementById('csv-upload').disabled = true;
  if (!file) return usageMsg('csv-msg', '');
  if (file.size > 2 * 1024 * 1024) return usageMsg('csv-msg', 'That file is too large. Keep it under 2 MB.', true);
  const { rows, skipped } = parseUsageCsv(await file.text());
  if (!rows.length) return usageMsg('csv-msg', 'No valid rows found. Each row needs a date and a gallons number.', true);
  usageCsvRows = rows;
  document.getElementById('csv-upload').disabled = false;
  usageMsg('csv-msg', `Found ${rows.length} days${skipped ? `, ${skipped} rows will be skipped` : ''}. Press Upload to save them.`);
});

document.getElementById('csv-upload').addEventListener('click', async () => {
  if (!usageCsvRows) return;
  const btn = document.getElementById('csv-upload');
  btn.disabled = true;
  let saved = 0;
  for (let i = 0; i < usageCsvRows.length; i += 1000) {
    const res = await getJSON('/api/usage', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entries: usageCsvRows.slice(i, i + 1000) }),
    });
    if (res.error) {
      usageMsg('csv-msg', `Saved ${saved} days, then stopped: ${res.error}`, true);
      await afterUsageChange();
      return;
    }
    saved += res.saved;
  }
  usageCsvRows = null;
  document.getElementById('csv-file').value = '';
  usageMsg('csv-msg', `Saved ${saved} days.`);
  await afterUsageChange();
});

document.getElementById('flume-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const val = (id) => document.getElementById(id).value.trim();
  const body = {
    client_id: val('flume-client-id'), client_secret: val('flume-client-secret'),
    email: val('flume-email'), password: document.getElementById('flume-password').value,
    days: +document.getElementById('flume-days').value,
  };
  if (!body.client_id || !body.client_secret || !body.email || !body.password) {
    return usageMsg('flume-msg', 'Fill in all four fields.', true);
  }
  const btn = document.getElementById('flume-submit');
  btn.disabled = true;
  usageMsg('flume-msg', 'Contacting Flume...');
  const res = await getJSON('/api/usage/flume', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  btn.disabled = false;
  if (res.error) return usageMsg('flume-msg', res.error, true);
  ['flume-client-secret', 'flume-password'].forEach(id => { document.getElementById(id).value = ''; });
  usageMsg('flume-msg', `Imported ${res.saved} days from Flume.`);
  await afterUsageChange();
});

document.getElementById('usage-rows').addEventListener('click', async (e) => {
  const day = e.target.dataset && e.target.dataset.del;
  if (!day) return;
  const res = await getJSON('/api/usage?date=' + encodeURIComponent(day), { method: 'DELETE' });
  if (res.error) return usageMsg('usage-msg', res.error, true);
  await afterUsageChange();
});

(function () {
  const btn = document.getElementById('usage-clear');
  let armed = null;
  btn.addEventListener('click', async () => {
    if (!armed) {
      btn.textContent = 'Click again to clear everything';
      armed = setTimeout(() => { armed = null; btn.textContent = 'Clear all data'; }, 4000);
      return;
    }
    clearTimeout(armed); armed = null;
    btn.textContent = 'Clear all data';
    const res = await getJSON('/api/usage?all=true', { method: 'DELETE' });
    if (res.error) return usageMsg('usage-msg', res.error, true);
    await afterUsageChange();
  });
})();
