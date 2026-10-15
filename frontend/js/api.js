const API = 'http://localhost:5000';

async function getJSON(path, opts) {
  const res = await fetch(API + path, opts);
  return res.json();
}
