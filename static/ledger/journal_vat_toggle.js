(() => {
  const table = document.querySelector('.journal-input');
  if (!table) return;
  const rows = Array.from(table.querySelectorAll('tbody tr'));
  const enabledRow = row => !!row.querySelector('input[name$="-vat_enabled"]')?.checked;
  function update() {
    table.classList.add('vat-visible');
    table.querySelectorAll('[data-vat-column]').forEach(cell => {cell.hidden = false;});
    rows.forEach(row => {
      const enabled = enabledRow(row);
      row.querySelectorAll('[data-vat-fields]').forEach(group => {
        group.hidden = false;
        group.querySelectorAll('input,select,textarea').forEach(field => {
          field.disabled = !enabled;
          field.setAttribute('aria-disabled', String(!enabled));
        });
      });
    });
    window.dispatchEvent(new Event('resize'));
  }
  ['input', 'change'].forEach(eventName => table.addEventListener(eventName, event => {
    if (event.target.matches('input[type="checkbox"][name$="-vat_enabled"]')) update();
  }));
  window.addEventListener('pageshow', update);
  update();
})();
