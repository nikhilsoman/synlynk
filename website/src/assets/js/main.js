// Global UI interactions for synlynk website (Phase 2)
// - Copy buttons: .copy-btn with data-copy="..."
// Pure vanilla, no deps.

(function () {
  function showCopied(btn, html) {
    btn.innerHTML = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.innerHTML = html;
      btn.classList.remove('copied');
    }, 1500);
  }

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

        // preserve inner HTML if it contains svg etc.
        const originalHTML = btn.innerHTML;

        try {
          await navigator.clipboard.writeText(text);

          // Visual feedback
          showCopied(btn, originalHTML);
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

            showCopied(btn, originalHTML);
          } catch (_) {
            // Last resort: select the text for manual copy
            btn.innerHTML = 'Select & copy';
            setTimeout(() => {
              btn.innerHTML = originalHTML;
            }, 1500);
          }
        }
      });
    });
  }

  function initWaitlistForm() {
    const form = document.querySelector('.waitlist-form');
    if (!form) return;

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const input = form.querySelector('.waitlist-input');
      if (input && !input.value.trim()) return;

      form.style.display = 'none';
      const thanksDiv = document.querySelector('.waitlist-thanks');
      if (thanksDiv) {
        thanksDiv.style.display = 'block';
      }
    });
  }

  function init() {
    initCopyButtons();
    initWaitlistForm();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

