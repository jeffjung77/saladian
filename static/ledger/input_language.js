// Language hints only: browsers do not expose an API to switch the OS IME.
(() => {
  const selector = 'input, textarea';
  function applyLanguage(field) {
    if (!field.matches(selector)) return;
    const isMemberId = field.name === 'username' || field.autocomplete === 'username';
    field.lang = isMemberId ? 'en' : 'ko';
    if (isMemberId) {
      field.autocapitalize = 'none';
      field.spellcheck = false;
    }
    // Preserve numeric, telephone, email and password input behavior.
  }
  document.querySelectorAll(selector).forEach(applyLanguage);
  document.addEventListener('focusin', event => applyLanguage(event.target));
})();
