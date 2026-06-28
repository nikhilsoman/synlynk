// Terminal carousel for Section 2 (synlynk init / join / dispatch / status)
// Auto-advance 4.2s fade, click pill or dot to switch + pause auto
// Pure vanilla JS, no dependencies. Ported from hero-v4.html

(function () {
  const track = document.getElementById('carousel-track');
  if (!track) return;

  let slides = Array.from(track.querySelectorAll('.carousel-slide, .terminal-slide'));
  let dots = [];
  let pills = [];

  let current = 0;
  let timer = null;
  const INTERVAL = 4200;

  function updateActive(idx) {
    slides.forEach((s, i) => s.classList.toggle('active', i === idx));
    dots.forEach((d, i) => d.classList.toggle('active', i === idx));
    pills.forEach((p, i) => p.classList.toggle('active', i === idx));
  }

  function goTo(idx) {
    if (idx < 0) idx = slides.length - 1;
    if (idx >= slides.length) idx = 0;
    current = idx;
    updateActive(current);
  }

  function next() {
    goTo(current + 1);
  }

  function restartTimer() {
    if (timer) clearInterval(timer);
    timer = setInterval(next, INTERVAL);
  }

  function pauseTimer() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  // Find controls (pills + dots). They may be outside track.
  function initControls() {
    // Pills: prefer data-pill, fallback to .cmd-pill in document
    pills = Array.from(document.querySelectorAll('.cmd-pill'));

    // Dots: inside #slide-nav or .slide-nav
    const nav = document.getElementById('slide-nav') || document.querySelector('.slide-nav');
    if (nav) {
      dots = Array.from(nav.querySelectorAll('.slide-dot'));
    } else {
      dots = Array.from(document.querySelectorAll('.slide-dot'));
    }

    // Attach listeners to pills
    pills.forEach((pill) => {
      const idx = parseInt(pill.getAttribute('data-pill') || '-1', 10);
      pill.addEventListener('click', () => {
        const target = (idx >= 0) ? idx : pills.indexOf(pill);
        if (target >= 0) { pauseTimer(); goTo(target); }
      });
    });

    // Attach listeners to dots
    dots.forEach((dot) => {
      const idx = parseInt(dot.getAttribute('data-dot') || '-1', 10);
      dot.addEventListener('click', () => {
        const target = (idx >= 0) ? idx : dots.indexOf(dot);
        if (target >= 0) { pauseTimer(); goTo(target); }
      });
    });
  }

  function init() {
    if (!slides.length) return;

    // Ensure initial active state
    slides.forEach((s, i) => s.classList.toggle('active', i === 0));

    initControls();

    // If no dots/pills found, still run auto (defensive)
    // Click anywhere on track pauses? Not required.

    // Start auto advance
    restartTimer();

    // Optional: pause on hover of the carousel container
    const container = track.closest('.carousel-container') || track;
    container.addEventListener('mouseenter', pauseTimer);
    container.addEventListener('mouseleave', () => {
      if (!timer) restartTimer();
    });

    // Keyboard support (left/right) when carousel in view
    document.addEventListener('keydown', (e) => {
      if (document.activeElement && document.activeElement.closest && document.activeElement.closest('.carousel-container')) {
        if (e.key === 'ArrowRight') { e.preventDefault(); next(); }
        if (e.key === 'ArrowLeft') { e.preventDefault(); goTo(current - 1); }
      }
    });

    // Expose a tiny API for debug if needed
    window.__synlynkCarousel = { goTo, next, pause: pauseTimer, resume: restartTimer };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
