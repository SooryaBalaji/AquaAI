const FIREBASE_SDK_VERSION = '10.14.1';
let authConfig = { provider: 'local' };
let fbAuth = null;
let fbApi = null;
let authSettled = false;
let authReady = false;

const FIREBASE_MESSAGES = {
  'auth/invalid-credential': 'Incorrect email or password.',
  'auth/wrong-password': 'Incorrect email or password.',
  'auth/user-not-found': 'Incorrect email or password.',
  'auth/invalid-email': 'Enter a valid email address.',
  'auth/email-already-in-use': 'An account with that email already exists. Try signing in.',
  'auth/weak-password': 'Password must be at least 8 characters.',
  'auth/missing-password': 'Enter your password.',
  'auth/too-many-requests': 'Too many attempts. Wait a few minutes and try again.',
  'auth/popup-closed-by-user': 'The Google window was closed before finishing.',
  'auth/network-request-failed': 'Could not reach the sign in service. Check your connection.',
  'auth/operation-not-allowed': 'This sign in method is not enabled yet. In Firebase, open Authentication, then Sign-in method, and turn it on.',
  'auth/unauthorized-domain': 'This address is not allowed for sign in. In Firebase, add it under Authentication, Settings, Authorized domains. On your computer, open the app at http://localhost:5000 instead of 127.0.0.1.',
  'auth/popup-blocked': 'Your browser blocked the Google window. Allow pop-ups for this site and try again.',
  'auth/cancelled-popup-request': 'Another sign in window was already open. Try again.',
  'auth/account-exists-with-different-credential': 'An account with this email already exists. Sign in with your password instead.',
  'auth/internal-error': 'Google sign in could not start. Open the browser console (F12) and check for a blocked request.',
  'auth/user-disabled': 'This account has been disabled.',
};

function authErrorText(err) {
  if (err && err.code) console.error('Sign in error:', err.code, err.message);
  return FIREBASE_MESSAGES[err && err.code] || 'Something went wrong signing in. Try again.';
}

function setAuthMessage(text, isError) {
  const el = document.getElementById('auth-error');
  el.textContent = text || '';
  el.dataset.kind = isError === false ? 'notice' : 'error';
}

function rememberSession() {
  if (!authReady) return;
  try {
    if (currentUser) localStorage.setItem('aquaai_signed_in', currentUser.email || '1');
    else localStorage.removeItem('aquaai_signed_in');
  } catch {}
}

function renderAccountArea() {
  rememberSession();
  const area = document.getElementById('account-area');
  if (currentUser) {
    area.innerHTML = `
      <button class="account-email-btn" id="account-email-btn" title="Open settings">${esc(currentUser.email)}</button>
      <button class="link-btn-light" id="signout-btn">Sign out</button>`;
    document.getElementById('signout-btn').addEventListener('click', signOut);
    document.getElementById('account-email-btn').addEventListener('click', () => {
      document.querySelector('.rail-btn[data-tab="settings"]').click();
    });
  } else {
    area.innerHTML = `<button class="link-btn-light" id="signin-btn">Sign in</button>`;
    document.getElementById('signin-btn').addEventListener('click', () => openAuthForm());
  }
  syncVerifyPage();
  updateProfileBarForAuthState();
}

let authMode = 'login';

function setAuthMode(mode) {
  authMode = mode;
  const login = mode === 'login';
  document.getElementById('auth-title').textContent = login ? 'Welcome back' : 'Create your account';
  document.getElementById('auth-sub').textContent = login
    ? 'Sign in to manage your households.'
    : 'Add your own household and track its water.';
  document.getElementById('auth-submit-btn').textContent = login ? 'Sign in' : 'Create account';
  document.getElementById('auth-switch-text').textContent = login ? 'New to AquaAI?' : 'Already have an account?';
  document.getElementById('auth-switch-btn').textContent = login ? 'Create an account' : 'Sign in';
  document.getElementById('auth-password').placeholder = login ? 'Your password' : 'At least 8 characters';
  document.getElementById('auth-password').autocomplete = login ? 'current-password' : 'new-password';
  document.getElementById('auth-forgot-btn').hidden = !(login && authConfig.provider === 'firebase');
  setAuthMessage('');
}

function openAuthForm(mode) {
  setAuthMode(mode === 'register' ? 'register' : 'login');
  document.getElementById('auth-form').hidden = false;
  document.body.classList.add('auth-open');
  document.getElementById('auth-email').focus();
}

function closeAuthForm() {
  document.getElementById('auth-form').hidden = true;
  document.body.classList.remove('auth-open');
  document.getElementById('auth-email').value = '';
  document.getElementById('auth-password').value = '';
  document.getElementById('auth-password').type = 'password';
  document.getElementById('auth-pw-toggle').textContent = 'Show';
  setAuthMessage('');
}

async function afterSignInChange() {
  renderAccountArea();
  if (!currentUser) setActiveProfile('demo');
  await refreshProfileList();
  await reloadAllTabs();
}

async function initAuth() {
  const cfg = await getJSON('/api/auth/config');
  if (!cfg.error) authConfig = cfg;

  const firebaseMode = authConfig.provider === 'firebase';
  document.getElementById('auth-google-btn').hidden = !firebaseMode;
  document.getElementById('auth-or').hidden = !firebaseMode;

  if (firebaseMode) {
    await initFirebase();
  } else {
    await trySavedSession();
    authReady = true;
    renderAccountArea();
  }
}

async function initFirebase() {
  const base = `https://www.gstatic.com/firebasejs/${FIREBASE_SDK_VERSION}`;
  try {
    const [appMod, authMod] = await Promise.all([
      import(`${base}/firebase-app.js`),
      import(`${base}/firebase-auth.js`),
    ]);
    fbApi = authMod;
    fbAuth = authMod.getAuth(appMod.initializeApp(authConfig.firebase));
  } catch {
    setAuthMessage('Could not load the sign in service. Reload the page to try again.');
    renderAccountArea();
    return;
  }

  tokenProvider = async () => (fbAuth.currentUser ? fbAuth.currentUser.getIdToken() : null);

  await new Promise(resolve => {
    fbApi.onAuthStateChanged(fbAuth, async (u) => {
      currentUser = u ? { id: u.uid, email: u.email, email_verified: u.emailVerified } : null;
      if (authSettled) {
        closeAuthForm();
        await afterSignInChange();
      } else {
        authSettled = true;
        authReady = true;
        renderAccountArea();
        resolve();
      }
    });
  });
}

async function trySavedSession() {
  if (!authToken) return;
  const res = await getJSON('/api/auth/me');
  if (res.user) currentUser = res.user;
  else setAuthToken(null);
}

async function signOut() {
  verifySkipped = false;
  if (fbAuth) {
    await fbApi.signOut(fbAuth);
    return;
  }
  setAuthToken(null);
  currentUser = null;
  await afterSignInChange();
}

async function deleteAccountNow() {
  const res = await getJSON('/api/account', { method: 'DELETE' });
  if (res.error) return res.error;
  if (fbAuth) {
    await fbApi.signOut(fbAuth);
    return null;
  }
  setAuthToken(null);
  currentUser = null;
  await afterSignInChange();
  return null;
}

async function handleAuthSubmit(mode) {
  const btn = document.getElementById('auth-submit-btn');
  btn.disabled = true;
  try {
    await submitAuth(mode);
  } finally {
    btn.disabled = false;
  }
}

async function submitAuth(mode) {
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  setAuthMessage('');
  if (!email || !password) { setAuthMessage('Enter your email and password.'); return; }

  if (fbAuth) {
    try {
      if (mode === 'login') {
        await fbApi.signInWithEmailAndPassword(fbAuth, email, password);
      } else {
        if (password.length < 8) { setAuthMessage('Password must be at least 8 characters.'); return; }
        const cred = await fbApi.createUserWithEmailAndPassword(fbAuth, email, password);
        await fbApi.sendEmailVerification(cred.user);
      }
    } catch (err) {
      setAuthMessage(authErrorText(err));
    }
    return;
  }

  const res = await getJSON('/api/auth/' + (mode === 'login' ? 'login' : 'register'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  if (res.error) { setAuthMessage(res.error); return; }
  setAuthToken(res.token);
  currentUser = res.user;
  closeAuthForm();
  await afterSignInChange();
}

async function handleGoogle() {
  setAuthMessage('');
  if (!fbAuth) { setAuthMessage('The sign in service did not load. Reload the page and try again.'); return; }
  try {
    const provider = new fbApi.GoogleAuthProvider();
    provider.setCustomParameters({ prompt: 'select_account' });
    await fbApi.signInWithPopup(fbAuth, provider);
  } catch (err) {
    setAuthMessage(authErrorText(err));
  }
}

async function handleForgot() {
  const email = document.getElementById('auth-email').value.trim();
  if (!email) { setAuthMessage('Enter your email above first.'); return; }
  try {
    await fbApi.sendPasswordResetEmail(fbAuth, email);
    setAuthMessage('If an account exists for that email, a reset link is on its way.', false);
  } catch (err) {
    setAuthMessage(authErrorText(err));
  }
}

let verifySkipped = false;
let verifyTimer = null;
let resendTimer = null;

function syncVerifyPage() {
  const needs = !!(currentUser && currentUser.email_verified === false && fbAuth && !verifySkipped);
  const page = document.getElementById('verify-page');
  if (needs && page.hidden) openVerifyPage();
  if (!needs && !page.hidden) closeVerifyPage();
}

function openVerifyPage() {
  document.getElementById('verify-email').textContent = currentUser.email;
  document.getElementById('verify-note').textContent = '';
  document.getElementById('verify-page').hidden = false;
  document.body.classList.add('auth-open');
  clearInterval(verifyTimer);
  verifyTimer = setInterval(() => recheckVerification(false), 4000);
}

function closeVerifyPage() {
  clearInterval(verifyTimer);
  verifyTimer = null;
  document.getElementById('verify-page').hidden = true;
  if (document.getElementById('auth-form').hidden) document.body.classList.remove('auth-open');
}

function startResendCooldown(seconds) {
  const btn = document.getElementById('verify-resend-btn');
  clearInterval(resendTimer);
  let left = seconds;
  btn.disabled = true;
  btn.textContent = `Resend email (${left}s)`;
  resendTimer = setInterval(() => {
    left -= 1;
    if (left <= 0) {
      clearInterval(resendTimer);
      btn.disabled = false;
      btn.textContent = 'Resend email';
    } else {
      btn.textContent = `Resend email (${left}s)`;
    }
  }, 1000);
}

async function resendVerification() {
  const note = document.getElementById('verify-note');
  note.dataset.kind = 'notice';
  try {
    await fbApi.sendEmailVerification(fbAuth.currentUser);
    note.textContent = 'Sent. Check your inbox and spam folder.';
    startResendCooldown(30);
  } catch (err) {
    note.dataset.kind = 'error';
    note.textContent = authErrorText(err);
  }
}

async function recheckVerification(manual) {
  const note = document.getElementById('verify-note');
  if (!fbAuth || !fbAuth.currentUser) return;
  try {
    await fbAuth.currentUser.reload();
    if (fbAuth.currentUser.emailVerified) {
      await fbAuth.currentUser.getIdToken(true);
      currentUser.email_verified = true;
      renderAccountArea();
      await loadSettings();
    } else if (manual) {
      note.dataset.kind = 'error';
      note.textContent = 'Not verified yet. Open the link in the email first.';
    }
  } catch (err) {
    if (manual) {
      note.dataset.kind = 'error';
      note.textContent = authErrorText(err);
    }
  }
}

document.addEventListener('visibilitychange', () => {
  if (!document.hidden && !document.getElementById('verify-page').hidden) recheckVerification(false);
});

document.getElementById('auth-form-el').addEventListener('submit', e => {
  e.preventDefault();
  handleAuthSubmit(authMode);
});
document.getElementById('auth-switch-btn').addEventListener('click', () => setAuthMode(authMode === 'login' ? 'register' : 'login'));
document.getElementById('auth-google-btn').addEventListener('click', handleGoogle);
document.getElementById('auth-forgot-btn').addEventListener('click', handleForgot);
document.getElementById('auth-cancel-btn').addEventListener('click', closeAuthForm);
document.getElementById('auth-pw-toggle').addEventListener('click', () => {
  const input = document.getElementById('auth-password');
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  document.getElementById('auth-pw-toggle').textContent = show ? 'Hide' : 'Show';
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !document.getElementById('auth-form').hidden) closeAuthForm();
});
document.getElementById('verify-resend-btn').addEventListener('click', resendVerification);
document.getElementById('verify-check-btn').addEventListener('click', () => recheckVerification(true));
document.getElementById('verify-signout-btn').addEventListener('click', () => { verifySkipped = false; signOut(); });
document.getElementById('verify-skip-btn').addEventListener('click', () => { verifySkipped = true; closeVerifyPage(); });