(() => {
  const storageKey = 'bpms-page-zoom';
  const levels = [50, 67, 75, 80, 90, 100, 110, 125, 150, 175, 200];
  let zoom = 100;
  try {
    const saved = Number(localStorage.getItem(storageKey));
    if (levels.includes(saved)) zoom = saved;
  } catch (_) {}
  document.documentElement.style.zoom = String(zoom / 100);
  const setup = () => {
    const brand = document.querySelector('header nav > .brand');
    if (!brand) return;
    const row = document.createElement('div');
    row.className = 'brand-row';
    brand.parentNode.insertBefore(row, brand);
    row.appendChild(brand);
    const section = document.createElement('section');
    section.className = 'panel page-zoom-section';
    section.setAttribute('aria-label', '화면크기');
    row.appendChild(section);
    const toolbar = document.createElement('div');
    toolbar.className = 'page-zoom-controls';
    toolbar.setAttribute('role', 'group');
    toolbar.setAttribute('aria-label', '화면크기');
    toolbar.innerHTML = '<span>화면크기</span><button type="button" class="secondary" aria-label="화면 축소">−</button><output aria-live="polite"></output><button type="button" class="secondary" aria-label="화면 확대">+</button>';
    section.appendChild(toolbar);
    const [minus, plus] = toolbar.querySelectorAll('button');
    const output = toolbar.querySelector('output');
    const update = () => {
      document.documentElement.style.zoom = String(zoom / 100);
      output.textContent = zoom + '%';
      minus.disabled = zoom === levels[0];
      plus.disabled = zoom === levels[levels.length - 1];
      try {localStorage.setItem(storageKey, String(zoom));} catch (_) {}
      window.dispatchEvent(new Event('resize'));
    };
    minus.addEventListener('click', () => {zoom = levels[Math.max(0, levels.indexOf(zoom) - 1)]; update();});
    plus.addEventListener('click', () => {zoom = levels[Math.min(levels.length - 1, levels.indexOf(zoom) + 1)]; update();});
    update();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup, {once:true});
  else setup();
})();
