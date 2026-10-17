(function () {
  var header = document.getElementById('site-header');
  function onScroll() { header.classList.toggle('scrolled', window.scrollY > 18); }
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });
})();
