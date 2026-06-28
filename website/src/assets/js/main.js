// Global UI interactions for synlynk website (Phase 2)
// - Copy buttons: .copy-btn with data-copy="..."
// Pure vanilla, no deps.

(function () {
  function initCopyButtons() {
    const btns = document.querySelectorAll('.copy-btn');
    if (!btns.length) return;

    btns.forEach((btn) => {
      // Prevent double-binding if script runs twice
      if (btn.dataset.copyBound === '1') return;
      btn.dataset.copyBound = '1';

      btn.addEventListener('click', async (e) => {
        e.preventDefault();
        const text = btn.dataset.copy || btn.getAttribute('data-copy') || '';
        if (!text) return;

        const originalText = btn.textContent.trim();
        // preserve inner HTML if it contains svg etc.
        const originalHTML = btn.innerHTML;

        try {
          await navigator.clipboard.writeText(text);

          // Visual feedback
          btn.innerHTML = 'Copied!';
          btn.classList.add('copied');

          setTimeout(() => {
            btn.innerHTML = originalHTML;
            btn.classList.remove('copied');
          }, 1500);
        } catch (err) {
          // Fallback for older browsers or no permission
          try {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);

            btn.innerHTML = 'Copied!';
            btn.classList.add('copied');
            setTimeout(() => {
              btn.innerHTML = originalHTML;
              btn.classList.remove('copied');
            }, 1500);
          } catch (_) {
            // Last resort: select the text for manual copy
            btn.innerHTML = 'Select & copy';
            setTimeout(() => {
              btn.innerHTML = originalHTML;
            }, 1600);
          }
        }
      });
    });
  }

  function init() {
    initCopyButtons();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
