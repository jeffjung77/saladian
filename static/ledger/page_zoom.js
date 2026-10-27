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
    const title = document.querySelector('main h1');
    if (!title) return;
    let heading = title.closest('.heading');
    if (!heading) {
      heading = document.createElement('div');
      heading.className = 'page-zoom-title';
      title.parentNode.insertBefore(heading, title);
      heading.appendChild(title);
    }
    const section = document.createElement('section');
    section.className = 'panel page-zoom-section';
    section.setAttribute('aria-label', '화면축소/확대');
    heading.classList.add('has-page-zoom');
    heading.appendChild(section);
    const toolbar = document.createElement('div');
    toolbar.className = 'page-zoom-controls';
    toolbar.setAttribute('role', 'group');
    toolbar.setAttribute('aria-label', '화면축소/확대');
    toolbar.innerHTML = '<span>화면축소/확대</span><button type="button" class="secondary" aria-label="화면 축소">−</button><output aria-live="polite"></output><button type="button" class="secondary" aria-label="화면 확대">+</button>';
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
