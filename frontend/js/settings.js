function settingsMsg(id, text, kind) {
  const el = document.getElementById(id);
  el.textContent = text || '';
  el.dataset.kind = kind || 'error';
}

async function loadSettings() {
  const signedIn = isSignedIn();
  document.getElementById('set-signed-out').hidden = signedIn;
  document.getElementById('set-signed-in').hidden = !signedIn;
  document.getElementById('set-notify-block').hidden = !signedIn;
  document.getElementById('set-danger-block').hidden = !signedIn;
  syncThemeRadios();
  if (!signedIn) return;

  document.getElementById('set-email').textContent = currentUser.email;
  document.getElementById('set-email-note').textContent = currentUser.email_verified === false
    ? 'Email not verified yet. Check your inbox for the link.'
    : 'Signed in';
  document.getElementById('set-notify-email').textContent = currentUser.email;

  const res = await getJSON('/api/settings');
  if (res.error) { settingsMsg('set-notify-msg', res.error); return; }
  document.querySelectorAll('[data-setting]').forEach(box => { box.checked = !!res.settings[box.dataset.setting]; });
}

function syncThemeRadios() {
  const mode = AquaTheme.get();
  document.querySelectorAll('input[name="theme"]').forEach(r => { r.checked = r.value === mode; });
}

document.querySelectorAll('input[name="theme"]').forEach(r => {
  r.addEventListener('change', () => { if (r.checked) AquaTheme.set(r.value); });
});

document.querySelectorAll('[data-setting]').forEach(box => {
  box.addEventListener('change', async () => {
    const res = await getJSON('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [box.dataset.setting]: box.checked }),
    });
    if (res.error) {
      box.checked = !box.checked;
      settingsMsg('set-notify-msg', res.error);
      return;
    }
    settingsMsg('set-notify-msg', 'Saved.', 'notice');
  });
});

document.getElementById('set-signin-btn').addEventListener('click', () => openAuthForm());
document.getElementById('set-signout-btn').addEventListener('click', () => signOut());

const deleteInput = document.getElementById('set-delete-input');
const deleteBtn = document.getElementById('set-delete-btn');
deleteInput.addEventListener('input', () => { deleteBtn.disabled = deleteInput.value.trim() !== 'DELETE'; });

document.getElementById('set-delete-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (deleteInput.value.trim() !== 'DELETE') return;
  deleteBtn.disabled = true;
  settingsMsg('set-delete-msg', '');
  const problem = await deleteAccountNow();
  if (problem) {
    settingsMsg('set-delete-msg', problem);
    deleteBtn.disabled = false;
    return;
  }
  deleteInput.value = '';
  document.querySelector('.rail-btn[data-tab="dashboard"]').click();
});
