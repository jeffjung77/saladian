(() => {
  const area = document.getElementById('journal-scroll-area');
  const table = area?.querySelector('.journal-input');
  if (!table) return;
  const columns = Array.from(table.querySelectorAll('colgroup col'));
  const weights = [3, 6, 15, 13, 6, 15, 13, 23, 6];
  const taxWidths = columns.slice(9).map(col => parseFloat(col.style.width) || 0);
  let previousWidth = -1;
  function fitColumns() {
    // On small phones preserve usable input widths and retain horizontal scrolling.
    const width = Math.max(920, area.clientWidth - 2);
    if (width === previousWidth) return;
    previousWidth = width;
    let used = 0;
    weights.forEach((weight, index) => {
      const size = index === weights.length - 1 ? width - used : Math.floor(width * weight / 100);
      columns[index].style.width = `${size}px`;
      used += size;
    });
    const total = width + taxWidths.reduce((sum, size) => sum + size, 0);
    table.style.width = `${total}px`;
    table.style.minWidth = `${total}px`;
  }
  if ('ResizeObserver' in window) new ResizeObserver(fitColumns).observe(area);
  window.addEventListener('resize', fitColumns);
  fitColumns();
})();
