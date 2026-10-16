document.querySelectorAll('.rail-btn[data-tab]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.rail-btn[data-tab]').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('page-' + btn.dataset.tab).classList.add('active');
  });
});

(async () => {
  renderAccountArea();
  await initAuth();
  await refreshProfileList();
  await reloadAllTabs();

  if (location.hash === '#signin' && !isSignedIn()) openAuthForm();
})();
