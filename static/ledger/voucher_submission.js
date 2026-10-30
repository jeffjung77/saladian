(() => {
  const pending = 'bpms-pending-voucher';
  const completed = 'bpms-saved-voucher:';
  const read = key => {try {return sessionStorage.getItem(key);} catch (_) {return null;}};
  const write = (key, value) => {try {sessionStorage.setItem(key, value);} catch (_) {}};
  const setup = () => {
    if (document.getElementById('voucher-saved-notice') || document.querySelector('[data-voucher-created]')) {
      const token = read(pending);
      if (token) write(completed + token, '1');
    }
    document.querySelectorAll('form[method="post"]').forEach(form => {
      const field = form.querySelector('[name="submission_token"]');
      if (!field) return;
      const clearSaved = () => {
        if (field.value && read(completed + field.value)) {
          form.reset();
          // Fetch a fresh form and token instead of restoring a submitted form from history.
          window.location.replace(window.location.pathname + window.location.search);
        }
      };
      clearSaved();
      window.addEventListener('pageshow', clearSaved);
      form.addEventListener('submit', () => {write(pending, field.value);});
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup, {once:true});
  else setup();
})();
