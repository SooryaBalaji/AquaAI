const HOUSEHOLD_LIMIT = 5;
const placeResults = {};
let placeTimer = null;
let editing = null;
let deleteArmed = null;
let householdList = [];

async function searchPlaces(text) {
  const res = await getJSON('/api/geocode?q=' + encodeURIComponent(text));
  return Array.isArray(res) ? res : null;
}

document.getElementById('pf-city').addEventListener('input', (e) => {
  clearTimeout(placeTimer);
  const text = e.target.value.trim();
  if (text.length < 2 || placeResults[text]) return;
  placeTimer = setTimeout(async () => {
    const found = await searchPlaces(text);
    if (!found) return;
    const list = document.getElementById('pf-city-list');
    list.innerHTML = '';
    found.forEach(p => {
      placeResults[p.label] = [p.lat, p.lon];
      const opt = document.createElement('option');
      opt.value = p.label;
      list.appendChild(opt);
    });
  }, 300);
});

function formError(text) {
  document.getElementById('pf-error').textContent = text || '';
}

function openHouseholdForm(profile) {
  editing = profile || null;
  document.getElementById('hh-form-title').textContent = profile ? 'Edit household' : 'Add a household';
  document.getElementById('pf-name').value = profile ? profile.name : '';
  document.getElementById('pf-city').value = profile ? placeLabel(profile) : '';
  document.getElementById('pf-size').value = profile ? profile.household_size : 4;
  document.getElementById('pf-tier').value = profile ? profile.tier1_limit_gal : 4500;
  formError('');
  const form = document.getElementById('hh-form');
  form.hidden = false;
  document.getElementById('pf-name').focus();
  form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function closeHouseholdForm() {
  editing = null;
  document.getElementById('hh-form').hidden = true;
  formError('');
}

function placeLabel(p) {
  if (p.place) return p.place;
  return Number(p.lat).toFixed(2) + ', ' + Number(p.lon).toFixed(2);
}

function householdCard(p, mine) {
  const viewing = p.id === currentProfileId;
  const meta = `${p.household_size} ${p.household_size === 1 ? 'person' : 'people'} · Tier 1 limit ${Number(p.tier1_limit_gal).toLocaleString()} gal/month`;
  const badges = (viewing ? '<span class="hh-badge hh-badge--on">Viewing</span>' : '')
    + (mine ? '' : '<span class="hh-badge">Demo</span>');
  const actions = mine
    ? `<button class="btn btn-quiet btn-sm" data-act="open" data-id="${esc(p.id)}" ${viewing ? 'disabled' : ''}>${viewing ? 'Open now' : 'Open'}</button>
       <button class="btn btn-quiet btn-sm" data-act="edit" data-id="${esc(p.id)}">Edit</button>
       <button class="btn btn-quiet btn-sm btn-delete" data-act="delete" data-id="${esc(p.id)}">Delete</button>`
    : `<button class="btn btn-quiet btn-sm" data-act="open" data-id="${esc(p.id)}" ${viewing ? 'disabled' : ''}>${viewing ? 'Open now' : 'Open'}</button>`;
  return `<article class="hh-card">
    <div class="hh-info">
      <div class="hh-name">${esc(p.name)} ${badges}</div>
      <div class="hh-place">${esc(mine ? placeLabel(p) : 'Sample household, San Jose, California')}</div>
      <div class="hh-meta">${esc(meta)}</div>
    </div>
    <div class="hh-actions">${actions}</div>
  </article>`;
}

function renderHouseholds(list) {
  householdList = list;
  const signedIn = isSignedIn();
  document.getElementById('hh-signed-out').hidden = signedIn;
  document.getElementById('hh-signed-in').hidden = !signedIn;
  if (!signedIn) closeHouseholdForm();

  const mine = list.filter(p => signedIn && p.owner_id === currentUser.id);
  const others = list.filter(p => !mine.includes(p));
  const full = mine.length >= HOUSEHOLD_LIMIT;
  document.getElementById('hh-count').textContent = `${mine.length} of ${HOUSEHOLD_LIMIT} households`;
  const addBtn = document.getElementById('hh-add-btn');
  addBtn.disabled = full;
  addBtn.title = full ? `You can have up to ${HOUSEHOLD_LIMIT} households. Delete one to add another.` : '';

  const emptyNote = signedIn && !mine.length
    ? '<p class="hh-empty">You have not added a household yet. Choose Add household to start.</p>'
    : '';
  document.getElementById('hh-list').innerHTML =
    mine.map(p => householdCard(p, true)).join('') + emptyNote + others.map(p => householdCard(p, false)).join('');
}

document.getElementById('hh-list').addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-act]');
  if (!btn || btn.disabled) return;
  const id = btn.dataset.id;
  const profile = householdList.find(p => p.id === id);
  if (!profile) return;

  if (btn.dataset.act === 'open') {
    setActiveProfile(id);
    await refreshProfileList();
    await reloadAllTabs();
    document.querySelector('.rail-btn[data-tab="dashboard"]').click();
  } else if (btn.dataset.act === 'edit') {
    openHouseholdForm(profile);
  } else if (btn.dataset.act === 'delete') {
    if (deleteArmed !== id) {
      deleteArmed = id;
      btn.textContent = 'Click again to delete';
      btn.classList.add('armed');
      setTimeout(() => {
        if (deleteArmed === id) { deleteArmed = null; btn.textContent = 'Delete'; btn.classList.remove('armed'); }
      }, 4000);
      return;
    }
    deleteArmed = null;
    btn.disabled = true;
    const res = await getJSON('/api/profiles/' + id, { method: 'DELETE' });
    if (res.error) { alert(res.error); btn.disabled = false; return; }
    if (currentProfileId === id) setActiveProfile('demo');
    if (editing && editing.id === id) closeHouseholdForm();
    await refreshProfileList();
    await reloadAllTabs();
  }
});

async function resolveCoordinates(place) {
  if (editing && place === placeLabel(editing)) return [editing.lat, editing.lon];
  if (placeResults[place]) return placeResults[place];
  const found = await searchPlaces(place);
  if (found === null) { formError('Location search is unavailable right now. Try again in a moment.'); return null; }
  if (!found.length) { formError("Couldn't find that place. Try a city name or a 5-digit ZIP code."); return null; }
  return [found[0].lat, found[0].lon];
}

document.getElementById('hh-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!isSignedIn()) { formError('Sign in first.'); return; }
  const name = document.getElementById('pf-name').value.trim();
  const place = document.getElementById('pf-city').value.trim();
  if (!name) { formError('Give the household a name.'); return; }
  if (!place) { formError('Enter a city or ZIP code.'); return; }
  const size = parseInt(document.getElementById('pf-size').value, 10);
  const tier = parseInt(document.getElementById('pf-tier').value, 10);
  if (!size || !tier) { formError('Enter the number of people and the Tier 1 limit.'); return; }

  const saveBtn = document.getElementById('pf-save-btn');
  saveBtn.disabled = true;
  formError('');
  try {
    const coords = await resolveCoordinates(place);
    if (!coords) return;
    const body = {
      name, place: editing && place === placeLabel(editing) && !editing.place ? null : place,
      lat: coords[0], lon: coords[1], household_size: size, tier1_limit_gal: tier,
    };
    const res = await getJSON(editing ? '/api/profiles/' + editing.id : '/api/profiles', {
      method: editing ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (res.error) {
      if (res.code === 'email_not_verified') {
        verifySkipped = false;
        closeHouseholdForm();
        syncVerifyPage();
        return;
      }
      formError(res.error);
      return;
    }
    const created = !editing;
    closeHouseholdForm();
    if (created) setActiveProfile(res.id);
    await refreshProfileList();
    await reloadAllTabs();
  } finally {
    saveBtn.disabled = false;
  }
});

document.getElementById('hh-add-btn').addEventListener('click', () => openHouseholdForm(null));
document.getElementById('pf-cancel-btn').addEventListener('click', closeHouseholdForm);
document.getElementById('hh-signin-btn').addEventListener('click', () => openAuthForm());
document.getElementById('manage-households-btn').addEventListener('click', () => {
  document.querySelector('.rail-btn[data-tab="households"]').click();
});
