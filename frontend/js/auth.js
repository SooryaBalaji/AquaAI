const FIREBASE_SDK_VERSION = '10.14.1';
let authConfig = { provider: 'local' };
let fbAuth = null;
let fbApi = null;
let authSettled = false;

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
};

function authErrorText(err) {
  return FIREBASE_MESSAGES[err && err.code] || 'Something went wrong signing in. Try again.';
}

function setAuthMessage(text, isError) {
  const el = document.getElementById('auth-error');
  el.textContent = text || '';
  el.dataset.kind = isError === false ? 'notice' : 'error';
}

function renderAccountArea() {
  const area = document.getElementById('account-area');
  if (currentUser) {
    area.innerHTML = `
      <span class="account-email">${esc(currentUser.email)}</span>
      <button class="link-btn" id="delete-account-btn">Delete account</button>
      <button class="link-btn-light" id="signout-btn">Sign out</button>`;
    document.getElementById('signout-btn').addEventListener('click', signOut);
    document.getElementById('delete-account-btn').addEventListener('click', deleteAccount);
  } else {
    area.innerHTML = `<button class="link-btn-light" id="signin-btn">Sign in</button>`;
    document.getElementById('signin-btn').addEventListener('click', openAuthForm);
  }
  document.getElementById('verify-banner').hidden = !(currentUser && currentUser.email_verified === false);
  updateProfileBarForAuthState();
}

function openAuthForm() {
  document.getElementById('auth-form').hidden = false;
  document.getElementById('auth-email').focus();
}

function closeAuthForm() {
  document.getElementById('auth-form').hidden = true;
  document.getElementById('auth-email').value = '';
  document.getElementById('auth-password').value = '';
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
  document.getElementById('auth-forgot-btn').hidden = !firebaseMode;

  if (firebaseMode) {
    await initFirebase();
  } else {
    await trySavedSession();
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
  if (fbAuth) {
    await fbApi.signOut(fbAuth);
    return;
  }
  setAuthToken(null);
  currentUser = null;
  await afterSignInChange();
}

async function deleteAccount() {
  if (!confirm('Delete your account and every household you created? This cannot be undone.')) return;
  const res = await getJSON('/api/account', { method: 'DELETE' });
  if (res.error) { alert(res.error); return; }
  if (fbAuth) {
    await fbApi.signOut(fbAuth);
    return;
  }
  setAuthToken(null);
  currentUser = null;
  await afterSignInChange();
}

async function handleAuthSubmit(mode) {
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  setAuthMessage('');

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
  try {
    await fbApi.signInWithPopup(fbAuth, new fbApi.GoogleAuthProvider());
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

async function resendVerification() {
  const note = document.getElementById('verify-note');
  try {
    await fbApi.sendEmailVerification(fbAuth.currentUser);
    note.textContent = 'Sent. Check your inbox and spam folder.';
  } catch (err) {
    note.textContent = authErrorText(err);
  }
}

async function recheckVerification() {
  const note = document.getElementById('verify-note');
  if (!fbAuth || !fbAuth.currentUser) return;
  await fbAuth.currentUser.reload();
  await fbAuth.currentUser.getIdToken(true);
  if (fbAuth.currentUser.emailVerified) {
    currentUser.email_verified = true;
    note.textContent = '';
    renderAccountArea();
  } else {
    note.textContent = 'Not verified yet. Open the link in the email first.';
  }
}

document.getElementById('auth-login-btn').addEventListener('click', () => handleAuthSubmit('login'));
document.getElementById('auth-register-btn').addEventListener('click', () => handleAuthSubmit('register'));
document.getElementById('auth-google-btn').addEventListener('click', handleGoogle);
document.getElementById('auth-forgot-btn').addEventListener('click', handleForgot);
document.getElementById('auth-cancel-btn').addEventListener('click', closeAuthForm);
document.getElementById('verify-resend-btn').addEventListener('click', resendVerification);
document.getElementById('verify-check-btn').addEventListener('click', recheckVerification);
['auth-email', 'auth-password'].forEach(id => {
  document.getElementById(id).addEventListener('keydown', e => {
    if (e.key === 'Enter') handleAuthSubmit('login');
  });
});
