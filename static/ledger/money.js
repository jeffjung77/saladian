(() => {
  const format = input => {
    const original = input.value;
    const raw = original.replace(/,/g, '');
    if (!/^-?\d*$/.test(raw)) return;
    const position = input.selectionStart;
    const prefixLength = position === null ? 0 : original.slice(0, position).replace(/,/g, '').length;
    const formatted = raw.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    input.value = formatted;
    if (document.activeElement === input && position !== null) {
      let cursor = 0, seen = 0;
      while (cursor < formatted.length && seen < prefixLength) {
        if (formatted[cursor] !== ',') seen++;
        cursor++;
      }
      input.setSelectionRange(cursor, cursor);
    }
  };
  document.querySelectorAll('input[data-money]').forEach(format);
  document.addEventListener('input', event => {
    if (event.target.matches('input[data-money]') && !event.isComposing) format(event.target);
  }, true);
  document.addEventListener('compositionend', event => {
    if (event.target.matches('input[data-money]')) format(event.target);
  });
})();
