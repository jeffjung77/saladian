(() => {
  const toggle = document.getElementById('id_vat_enabled');
  if (!toggle) return;
  const fields = Array.from(document.querySelectorAll('[data-voucher-vat] input,[data-voucher-vat] select,[data-voucher-vat] textarea'));
  const trade = document.getElementById('id_vat_trade');
  const fixedTrade = trade?.disabled;
  function update() {
    fields.forEach(field => {
      field.disabled = !toggle.checked || (field === trade && fixedTrade);
      field.setAttribute('aria-disabled', String(field.disabled));
    });
  }
  toggle.addEventListener('change', update);
  window.addEventListener('pageshow', update);
  update();
})();
