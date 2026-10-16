const API = AQUAAI_CONFIG.apiUrl;

let currentProfileId = localStorage.getItem('aquaai_profile') || 'demo';
let authToken = localStorage.getItem('aquaai_token') || null;
let currentUser = null;
let tokenProvider = null;

const PROFILE_SCOPED_PATHS = ['/api/dashboard', '/api/anomalies', '/api/forecast', '/api/score', '/api/savings', '/api/ask'];

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function needsProfile(path) {
  return PROFILE_SCOPED_PATHS.some(p => path.startsWith(p));
}

function setActiveProfile(id) {
  currentProfileId = id;
  localStorage.setItem('aquaai_profile', id);
}

function setAuthToken(token) {
  authToken = token;
  if (token) localStorage.setItem('aquaai_token', token);
  else localStorage.removeItem('aquaai_token');
}

function isSignedIn() {
  return !!currentUser;
}

async function currentToken() {
  if (tokenProvider) return tokenProvider();
  return authToken;
}

async function getJSON(path, opts = {}) {
  let url = API + path;
  if (needsProfile(path)) {
    url += (path.includes('?') ? '&' : '?') + 'profile=' + encodeURIComponent(currentProfileId);
  }
  const headers = Object.assign({}, opts.headers || {});
  const token = await currentToken();
  if (token) headers['Authorization'] = 'Bearer ' + token;

  try {
    const res = await fetch(url, Object.assign({}, opts, { headers }));
    const data = await res.json().catch(() => ({ error: 'The server sent back something unreadable.' }));
    if (!res.ok && !data.error) data.error = 'Something went wrong (' + res.status + ').';
    return data;
  } catch {
    return { error: 'Could not reach the server. Check your connection and try again.' };
  }
}

function freshCanvas(id) {
  const wrap = document.getElementById(id + '-wrap');
  wrap.innerHTML = `<canvas id="${id}"></canvas>`;
  return document.getElementById(id);
}
