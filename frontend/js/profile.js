const placeResults = {};
let placeTimer = null;

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
  await Promise.all([loadDashboard(), loadLeaks(), loadForecast(), loadSettings()]);
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
  const place = document.getElementById('pf-city').value.trim();
  if (!place) {
    document.getElementById('pf-error').textContent = 'Enter a city or ZIP code.';
    return;
  }
  let coords = placeResults[place];
  if (!coords) {
    const found = await searchPlaces(place);
    if (found === null) {
      document.getElementById('pf-error').textContent = 'Location search is unavailable right now. Try again in a moment.';
      return;
    }
    if (!found.length) {
      document.getElementById('pf-error').textContent = "Couldn't find that place. Try a city name or a 5-digit ZIP code.";
      return;
    }
    coords = [found[0].lat, found[0].lon];
  }
  const [lat, lon] = coords;
  const householdSize = parseInt(document.getElementById('pf-size').value, 10) || 4;
  const tierLimit = parseInt(document.getElementById('pf-tier').value, 10) || 4500;

  const res = await getJSON('/api/profiles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, lat, lon, household_size: householdSize, tier1_limit_gal: tierLimit })
  });

  if (res.error) {
    if (res.code === 'email_not_verified') {
      verifySkipped = false;
      document.getElementById('profile-form').hidden = true;
      syncVerifyPage();
      return;
    }
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