async function refreshProfileList() {
  const list = await getJSON('/api/profiles');
  if (!Array.isArray(list)) return [];
  const select = document.getElementById('profile-select');
  select.innerHTML = list.map(p =>
    `<option value="${esc(p.id)}" ${p.id === currentProfileId ? 'selected' : ''}>${esc(p.name)} (${esc(p.household_size)} people)</option>`
  ).join('');
  renderHouseholds(list);
  const current = list.find(p => p.id === currentProfileId);
  renderFilterChips(current ? current.name : null);
  return list;
}

async function reloadAllTabs() {
  await Promise.all([loadDashboard(), loadLeaks(), loadForecast(), loadSettings(), loadUsage()]);
}

function updateProfileBarForAuthState() {
  document.getElementById('manage-households-btn').hidden = !isSignedIn();
  document.getElementById('signin-hint').hidden = isSignedIn();
}

document.getElementById('profile-select').addEventListener('change', async (e) => {
  setActiveProfile(e.target.value);
  await refreshProfileList();
  await reloadAllTabs();
});
