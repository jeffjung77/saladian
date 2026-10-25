(() => {
  const area = document.getElementById('journal-scroll-area');
  const add = document.getElementById('journal-add-row');
  const count = document.getElementById('journal-visible-count');
  const label = document.getElementById('journal-row-count');
  if (!area || !add || !count) return;
  const rows = Array.from(area.querySelectorAll('tbody tr'));
  function update() {
    const visible = rows.filter(row => !row.hidden).length;
    count.value = visible;
    label.textContent = `${visible}/5`;
    window.dispatchEvent(new Event('resize'));
  }
  add.addEventListener('click', () => {
    const next = rows.find(row => row.hidden);
    if (!next) {
      document.getElementById('journal-row-limit-notice').showModal();
      return;
    }
    next.hidden = false;
    update();
    area.scrollTop += next.getBoundingClientRect().bottom - area.getBoundingClientRect().bottom + 24;
    next.querySelector('input')?.focus({preventScroll: true});
  });
  update();
})();
