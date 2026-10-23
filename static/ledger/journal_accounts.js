(() => {
  document.querySelectorAll('.journal-input tbody tr').forEach(row => {
    for (const side of ['debit', 'credit']) {
      const select = row.querySelector(`select[name$="-${side}_account"]`);
      const code = row.querySelector(`input[name$="-${side}_code"]`);
      const name = row.querySelector(`input[name$="-${side}_name"]`);
      const options = Array.from(select.options).filter(option => option.value);
      const accountName = option => option.textContent.split(' · ').slice(1).join(' · ').trim();
      function resetFilter() {Array.from(select.options).forEach(option => {option.hidden = false;});}
      function selected() {
        const option = options.find(option => option.value === select.value);
        code.value = option ? option.value : '';
        name.value = option ? accountName(option) : '';
        resetFilter(); select.size = 1;
      }
      select.addEventListener('change', selected);
      code.addEventListener('input', () => {
        resetFilter(); select.size = 1;
        const option = options.find(option => option.value === code.value.trim());
        select.value = option ? option.value : '';
        name.value = option ? accountName(option) : '';
        if (option) select.scrollTop = option.offsetTop;
      });
      name.addEventListener('input', () => {
        const query = name.value.trim().toLocaleLowerCase();
        code.value = ''; select.value = '';
        const matches = options.filter(option => accountName(option).toLocaleLowerCase().includes(query));
        options.forEach(option => {option.hidden = !!query && !matches.includes(option);});
        const exact = matches.filter(option => accountName(option).toLocaleLowerCase() === query);
        if (exact.length === 1) {
          select.value = exact[0].value; code.value = exact[0].value;
        }
        select.size = query ? 4 : 1;
      });
      name.addEventListener('keydown', event => {
        if (event.key === 'ArrowDown') {event.preventDefault(); select.focus();}
        if (event.key === 'Escape') {resetFilter(); select.size = 1;}
      });
      select.addEventListener('keydown', event => {
        if (event.key === 'Enter') {event.preventDefault(); selected();}
        if (event.key === 'Escape') {resetFilter(); select.size = 1; name.focus();}
      });
      if (!code.value && !name.value && select.value) selected();
    }
  });
})();
