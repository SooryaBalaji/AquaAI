/* A short list of California cities with known coordinates, so creating a
   profile doesn't require a geocoding API. The backend only ever sees the
   resulting lat/lon; it doesn't know about city names. */
const CA_CITIES = {
  'San Jose': [37.3382, -121.8863],
  'Los Angeles': [34.0522, -118.2437],
  'San Diego': [32.7157, -117.1611],
  'Sacramento': [38.5816, -121.4944],
  'Fresno': [36.7378, -119.7871],
  'Oakland': [37.8044, -122.2712],
};

async function refreshProfileList() {
  const list = await getJSON('/api/profiles');
  const select = document.getElementById('profile-select');
  select.innerHTML = list.map(p =>
    `<option value="${esc(p.id)}" ${p.id === currentProfileId ? 'selected' : ''}>${esc(p.name)} (${esc(p.household_size)} people)</option>`
  ).join('');
  updateDeleteButtonVisibility(list);
  const current = list.find(p => p.id === currentProfileId);
  renderFilterChips(current ? current.name : null);
  return list;
}

function updateDeleteButtonVisibility(list) {
  const btn = document.getElementById('delete-profile-btn');
  const mine = isSignedIn() && Array.isArray(list) && list.find(p => p.id === currentProfileId && p.owner_id === currentUser?.id);
  btn.hidden = !mine;
}

async function reloadAllTabs() {
  await Promise.all([loadDashboard(), loadLeaks(), loadForecast()]);
}

function updateProfileBarForAuthState() {
  const btn = document.getElementById('new-profile-btn');
  const hint = document.getElementById('signin-hint');
  btn.hidden = !isSignedIn();
  hint.hidden = isSignedIn();
  if (!isSignedIn()) document.getElementById('profile-form').hidden = true;
}

document.getElementById('profile-select').addEventListener('change', async (e) => {
  setActiveProfile(e.target.value);
  await refreshProfileList();
  await reloadAllTabs();
});

document.getElementById('delete-profile-btn').addEventListener('click', async () => {
  const list = await getJSON('/api/profiles');
  const current = list.find(p => p.id === currentProfileId);
  if (!current || !confirm(`Delete "${current.name}"? This can't be undone.`)) return;

  const res = await getJSON('/api/profiles/' + currentProfileId, { method: 'DELETE' });
  if (res.error) {
    alert(res.error);
    return;
  }
  setActiveProfile('demo');
  await refreshProfileList();
  await reloadAllTabs();
});

document.getElementById('new-profile-btn').addEventListener('click', () => {
  if (!isSignedIn()) return;
  const form = document.getElementById('profile-form');
  form.hidden = !form.hidden;
});

document.getElementById('pf-cancel-btn').addEventListener('click', () => {
  document.getElementById('profile-form').hidden = true;
});

document.getElementById('pf-create-btn').addEventListener('click', async () => {
  if (!isSignedIn()) {
    document.getElementById('pf-error').textContent = 'Sign in first.';
    return;
  }
  const name = document.getElementById('pf-name').value.trim();
  if (!name) {
    document.getElementById('pf-error').textContent = 'Give the household a name.';
    return;
  }
  const city = document.getElementById('pf-city').value;
  const [lat, lon] = CA_CITIES[city];
  const householdSize = parseInt(document.getElementById('pf-size').value, 10) || 4;
  const tierLimit = parseInt(document.getElementById('pf-tier').value, 10) || 4500;

  const res = await getJSON('/api/profiles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, lat, lon, household_size: householdSize, tier1_limit_gal: tierLimit })
  });

  if (res.error) {
    document.getElementById('pf-error').textContent = res.error;
    return;
  }

  document.getElementById('pf-name').value = '';
  document.getElementById('pf-error').textContent = '';
  document.getElementById('profile-form').hidden = true;

  setActiveProfile(res.id);
  await refreshProfileList();
  await reloadAllTabs();
});
