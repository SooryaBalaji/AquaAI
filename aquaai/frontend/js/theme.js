(function () {
  const KEY = 'aquaai-theme';
  const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function stored() {
    try {
      const v = localStorage.getItem(KEY);
      return v === 'light' || v === 'dark' || v === 'system' ? v : 'light';
    } catch {
      return 'light';
    }
  }

  function resolve(mode) {
    if (mode === 'system') return media && media.matches ? 'dark' : 'light';
    return mode;
  }

  function apply(announce) {
    document.documentElement.dataset.theme = resolve(stored());
    if (announce) document.dispatchEvent(new CustomEvent('aquaai-theme'));
  }

  window.AquaTheme = {
    get: stored,
    set(mode) {
      try {
        localStorage.setItem(KEY, mode);
      } catch {}
      apply(true);
    },
  };

  if (media) media.addEventListener('change', () => { if (stored() === 'system') apply(true); });
  apply(false);
})();
