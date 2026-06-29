function initFeaturesToggle() {
  const btns = document.querySelectorAll('.toggle-btn');
  if (!btns.length) return;
  const layerEls = document.querySelectorAll('.layer-view');
  const userEls = document.querySelectorAll('.user-view');

  // initial state: layer view visible
  layerEls.forEach(el => { el.style.display = ''; });
  userEls.forEach(el => { el.style.display = 'none'; });

  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const view = btn.dataset.view;
      layerEls.forEach(el => { el.style.display = view === 'layer' ? '' : 'none'; });
      userEls.forEach(el => { el.style.display = view === 'user' ? '' : 'none'; });
    });
  });
}

function init() {
  initFeaturesToggle();
}

init();
