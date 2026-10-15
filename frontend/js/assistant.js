function addMessage(text, who, src) {
  const win = document.getElementById('chat-window');
  const div = document.createElement('div');
  div.className = 'msg ' + who;
  div.innerHTML = text + (src ? `<span class="src">${src}</span>` : '');
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
  thinking.textContent = 'Thinking…';
  win.appendChild(thinking);
  win.scrollTop = win.scrollHeight;

  const res = await getJSON('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question })
  });

  document.getElementById('thinking-msg')?.remove();
  addMessage(res.answer, 'bot', res.source === 'claude' ? 'Answered by Claude' : res.source);
}

document.getElementById('chat-form').addEventListener('submit', (e) => {
  e.preventDefault();
  askQuestion(document.getElementById('chat-input').value);
});

document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => askQuestion(chip.textContent));
});
