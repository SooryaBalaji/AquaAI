let activeFilters = { days: null, confirmedOnly: false };

function renderFilterChips(householdName) {
  document.getElementById('chip-household').textContent = 'Household: ' + (householdName || 'Demo household');

  const daysChip = document.getElementById('chip-days');
  if (activeFilters.days) {
    daysChip.textContent = 'Last ' + activeFilters.days + ' days';
    daysChip.hidden = false;
  } else {
    daysChip.hidden = true;
  }

  const confirmedChip = document.getElementById('chip-confirmed');
  confirmedChip.textContent = 'Confirmed leaks only';
  confirmedChip.hidden = !activeFilters.confirmedOnly;
}

document.getElementById('open-filters-btn').addEventListener('click', () => {
  document.getElementById('filter-panel').hidden = false;
});

document.getElementById('close-filters-btn').addEventListener('click', () => {
  document.getElementById('filter-panel').hidden = true;
});

document.getElementById('apply-filters-btn').addEventListener('click', async () => {
  activeFilters.days = document.getElementById('filter-days').value || null;
  activeFilters.confirmedOnly = document.getElementById('filter-confirmed').checked;
  document.getElementById('filter-panel').hidden = true;

  const list = await getJSON('/api/profiles');
  const current = list.find(p => p.id === currentProfileId);
  renderFilterChips(current ? current.name : null);

  await loadLeaks();
});
