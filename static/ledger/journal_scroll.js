(() => {
  const area = document.getElementById('journal-scroll-area');
  const bar = document.getElementById('journal-scroll-position');
  if (!area || !bar) return;
  const table = area.querySelector('table');
  function sync() {
    const maximum = Math.max(0, area.scrollWidth - area.clientWidth);
    bar.max = maximum;
    bar.value = area.scrollLeft;
    bar.disabled = maximum === 0;
    const width = Math.max(28, bar.clientWidth * area.clientWidth / Math.max(1, area.scrollWidth));
    bar.style.setProperty('--scroll-thumb-width', `${width}px`);
  }
  bar.addEventListener('input', () => {area.scrollLeft = Number(bar.value);});
  area.addEventListener('scroll', sync, {passive: true});
  window.addEventListener('resize', sync);
  if ('ResizeObserver' in window) {
    const observer = new ResizeObserver(sync);
    observer.observe(area);
    observer.observe(table);
  }
  sync();
})();
