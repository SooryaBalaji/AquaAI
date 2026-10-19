function addMessage(text, who, src, warning) {
  const win = document.getElementById('chat-window');
  const div = document.createElement('div');
  div.className = 'msg ' + who;
  div.textContent = text;
  if (src) {
    const tag = document.createElement('span');
    tag.className = 'src';
    tag.textContent = src;
    div.appendChild(tag);
  }
  if (warning) {
    const note = document.createElement('span');
    note.className = 'warn';
    note.setAttribute('role', 'alert');
    note.textContent = warning;
    div.appendChild(note);
  }
  win.appendChild(div);
  win.scrollTop = win.scrollHeight;
}

async function askQuestion(question) {
  if (!question.trim()) return;
  addMessage(question, 'user');
  document.getElementById('chat-input').value = '';

  const win = document.getElementById('chat-window');
  const thinking = document.createElement('div');
  thinking.className = 'msg bot loading';
  thinking.id = 'thinking-msg';
  thinking.textContent = 'Thinking';
  win.appendChild(thinking);
  win.scrollTop = win.scrollHeight;

  const res = await getJSON('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question })
  });

  document.getElementById('thinking-msg')?.remove();
  if (res.error) {
    addMessage(res.error, 'bot');
    return;
  }
  addMessage(res.answer, 'bot', res.source === 'gemini' ? 'Answered by Gemini' : res.source, res.warning);
}

document.getElementById('chat-form').addEventListener('submit', (e) => {
  e.preventDefault();
  askQuestion(document.getElementById('chat-input').value);
});

document.querySelectorAll('.suggest-btn').forEach(btn => {
  btn.addEventListener('click', () => askQuestion(btn.textContent));
});

(function () {
  const select = document.getElementById('profile-select');
  const label = document.getElementById('chat-for');
  function update() {
    const opt = select.selectedOptions && select.selectedOptions[0];
    if (opt && opt.textContent.trim()) label.textContent = opt.textContent.replace(/\s*\(.*\)\s*$/, '');
  }
  select.addEventListener('change', update);
  new MutationObserver(update).observe(select, { childList: true, attributes: true, subtree: true });
  update();
})();
