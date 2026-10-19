(function () {
  var header = document.getElementById('site-header');
  function onScroll() { header.classList.toggle('scrolled', window.scrollY > 18); }
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });
})();

(function () {
  var email = null;
  try { email = localStorage.getItem('aquaai_signed_in'); } catch (e) {}
  if (!email) return;
  var signin = document.getElementById('nav-signin');
  if (signin) signin.hidden = true;
  document.querySelectorAll('.js-signup').forEach(function (a) {
    a.href = '/app';
    a.textContent = 'Open AquaAI';
  });
})();
