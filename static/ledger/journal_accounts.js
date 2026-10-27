(() => {
  document.querySelectorAll('.journal-input tbody tr').forEach(row => {
    for (const side of ['debit', 'credit']) {
      const account = row.querySelector(`input[name$="-${side}_account"]`);
      const code = row.querySelector(`input[name$="-${side}_code"]`);
      if (!account || !code) continue;
      const choices = Array.from(document.getElementById(account.getAttribute('list')).options).map(option => {
        const [id, ...name] = option.value.split(' \u00b7 ');
        return {id, name: name.join(' \u00b7 '), label: option.value};
      });
      code.addEventListener('input', () => {
        const match = choices.find(choice => choice.id === code.value.trim());
        account.value = match ? match.name : '';
      });
      account.addEventListener('input', () => {
        const text = account.value.trim();
        const matches = choices.filter(choice => [choice.id, choice.name, choice.label].includes(text));
        code.value = matches.length === 1 ? matches[0].id : '';
        if (matches.length === 1 && (text === matches[0].id || text === matches[0].label)) {
          account.value = matches[0].name;
        }
      });
      account.addEventListener('change', () => {
        const text = account.value.trim();
        const match = choices.find(choice => choice.id === code.value && [choice.id, choice.name, choice.label].includes(text));
        if (match) account.value = match.name;
      });
      const match = choices.find(choice => choice.id === account.value || choice.label === account.value ||
        (choice.id === code.value && choice.name === account.value));
      if (match) {account.value = match.name; code.value = match.id;}
    }
  });
})();
