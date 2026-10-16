let phoneConfirm = null;
let phoneVerifier = null;

const PHONE_MESSAGES = {
  'auth/invalid-phone-number': 'That phone number does not look right. Include the area code.',
  'auth/missing-phone-number': 'Enter a phone number.',
  'auth/too-many-requests': 'Too many attempts. Wait a while and try again.',
  'auth/quota-exceeded': 'The daily limit for text codes was reached. Try again tomorrow.',
  'auth/captcha-check-failed': 'The security check failed. Reload the page and try again.',
  'auth/invalid-verification-code': 'That code is not correct.',
  'auth/code-expired': 'That code expired. Request a new one.',
  'auth/credential-already-in-use': 'That number is already linked to another account.',
  'auth/provider-already-linked': 'A phone number is already linked. Remove it first.',
  'auth/requires-recent-login': 'For your security, sign out, sign back in, and try again.',
  'auth/operation-not-allowed': 'Phone sign in is not enabled in Firebase yet (Authentication, Sign-in method, Phone).',
  'auth/billing-not-enabled': 'Text messages need billing turned on for the Firebase project.',
  'auth/network-request-failed': 'Could not reach the service. Check your connection.',
};

function settingsMsg(id, text, kind) {
  const el = document.getElementById(id);
  el.textContent = text || '';
  el.dataset.kind = kind || 'error';
}

function phoneErrorText(err) {
  if (err && err.code) console.error('Phone error:', err.code, err.message);
  return PHONE_MESSAGES[err && err.code] || 'Something went wrong. Try again.';
}

function normalizePhone(raw) {
  const text = raw.trim();
  const digits = text.replace(/\D/g, '');
  if (text.startsWith('+')) return digits.length >= 8 && digits.length <= 15 ? '+' + digits : null;
  if (digits.length === 10) return '+1' + digits;
  if (digits.length === 11 && digits[0] === '1') return '+' + digits;
  return null;
}

function renderPhone(phone) {
  document.getElementById('set-phone-status').textContent = phone ? 'Linked: ' + phone : 'No phone linked';
  document.getElementById('set-phone-remove').hidden = !phone;
  document.getElementById('set-phone-form').hidden = !!phone || !!phoneConfirm;
  document.getElementById('set-code-form').hidden = !phoneConfirm;
  const sms = document.getElementById('set-via-sms');
  sms.disabled = !phone;
  if (!phone) sms.checked = false;
  document.getElementById('set-via-sms-note').textContent = phone
    ? 'Alerts go to ' + phone + '.'
    : 'Link a phone number above to turn this on.';
}

async function loadSettings() {
  const signedIn = isSignedIn();
  const firebaseMode = authConfig.provider === 'firebase';
  document.getElementById('set-signed-out').hidden = signedIn;
  document.getElementById('set-signed-in').hidden = !signedIn;
  document.getElementById('set-phone-block').hidden = !(signedIn && firebaseMode);
  document.getElementById('set-notify-block').hidden = !signedIn;
  document.getElementById('set-danger-block').hidden = !signedIn;
  syncThemeRadios();
  if (!signedIn) return;

  document.getElementById('set-email').textContent = currentUser.email;
  document.getElementById('set-email-note').textContent = currentUser.email_verified === false
    ? 'Email not verified yet. Check your inbox for the link.'
    : 'Signed in';
  document.getElementById('set-via-email-note').textContent = 'Alerts go to ' + currentUser.email + '.';

  const res = await getJSON('/api/settings');
  if (res.error) { settingsMsg('set-notify-msg', res.error); return; }
  document.querySelectorAll('[data-setting]').forEach(box => { box.checked = !!res.settings[box.dataset.setting]; });
  renderPhone(res.phone);
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

function resetVerifier() {
  if (phoneVerifier) { try { phoneVerifier.clear(); } catch {} }
  phoneVerifier = null;
  document.getElementById('recaptcha-holder').innerHTML = '';
}

document.getElementById('set-phone-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  settingsMsg('set-phone-msg', '');
  const number = normalizePhone(document.getElementById('set-phone-input').value);
  if (!number) { settingsMsg('set-phone-msg', 'Enter a valid phone number, like +1 555 123 4567.'); return; }
  if (!fbAuth || !fbAuth.currentUser) { settingsMsg('set-phone-msg', 'Sign in first.'); return; }
  const btn = document.getElementById('set-phone-send');
  btn.disabled = true;
  try {
    resetVerifier();
    phoneVerifier = new fbApi.RecaptchaVerifier(fbAuth, 'recaptcha-holder', { size: 'invisible' });
    phoneConfirm = await fbApi.linkWithPhoneNumber(fbAuth.currentUser, number, phoneVerifier);
    renderPhone(null);
    settingsMsg('set-phone-msg', 'Code sent. Enter it below.', 'notice');
    document.getElementById('set-code-input').focus();
  } catch (err) {
    phoneConfirm = null;
    resetVerifier();
    settingsMsg('set-phone-msg', phoneErrorText(err));
  } finally {
    btn.disabled = false;
  }
});

document.getElementById('set-code-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const code = document.getElementById('set-code-input').value.trim();
  if (!code) { settingsMsg('set-phone-msg', 'Enter the 6-digit code.'); return; }
  const btn = document.getElementById('set-code-verify');
  btn.disabled = true;
  try {
    await phoneConfirm.confirm(code);
    phoneConfirm = null;
    resetVerifier();
    document.getElementById('set-code-input').value = '';
    document.getElementById('set-phone-input').value = '';
    await fbAuth.currentUser.getIdToken(true);
    await loadSettings();
    settingsMsg('set-phone-msg', 'Phone linked.', 'notice');
  } catch (err) {
    settingsMsg('set-phone-msg', phoneErrorText(err));
  } finally {
    btn.disabled = false;
  }
});

document.getElementById('set-code-cancel').addEventListener('click', () => {
  phoneConfirm = null;
  resetVerifier();
  settingsMsg('set-phone-msg', '');
  renderPhone(null);
});

document.getElementById('set-phone-remove').addEventListener('click', async () => {
  settingsMsg('set-phone-msg', '');
  try {
    await fbApi.unlink(fbAuth.currentUser, 'phone');
    await fbAuth.currentUser.getIdToken(true);
    await loadSettings();
    settingsMsg('set-phone-msg', 'Phone removed.', 'notice');
  } catch (err) {
    settingsMsg('set-phone-msg', phoneErrorText(err));
  }
});

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