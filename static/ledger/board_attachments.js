(() => {
  const input = document.getElementById('board-files');
  const zone = document.getElementById('board-dropzone');
  const previews = document.getElementById('board-file-previews');
  let files = [], urls = [];
  function render() {
    urls.forEach(url => URL.revokeObjectURL(url)); urls = [];
    previews.replaceChildren();
    const transfer = new DataTransfer();
    files.forEach((file, index) => {
      transfer.items.add(file);
      const card = document.createElement('div');
      card.style.cssText = 'max-width:220px;overflow-wrap:anywhere';
      if (['image/jpeg', 'image/png', 'image/gif', 'image/webp'].includes(file.type)) {
        const img = document.createElement('img');
        const url = URL.createObjectURL(file); urls.push(url);
        img.src = url; img.alt = file.name;
        img.style.cssText = 'display:block;max-width:180px;max-height:140px;object-fit:contain';
        card.appendChild(img);
      }
      const text = document.createElement('p'); text.textContent = file.name;
      const remove = document.createElement('button');
      remove.type = 'button'; remove.className = 'secondary'; remove.textContent = '선택 취소';
      remove.addEventListener('click', () => {files.splice(index, 1); render();});
      card.append(text, remove); previews.appendChild(card);
    });
    input.files = transfer.files;
  }
  function add(incoming) {
    const added = Array.from(incoming);
    if (files.length + added.length > 5 || added.some(file => file.size > 10 * 1024 * 1024)) {
      alert('최대 5개, 파일당 10MB 이하로 선택해 주세요.'); render(); return;
    }
    files.push(...added); render();
  }
  input.addEventListener('change', () => add(input.files));
  ['dragenter', 'dragover'].forEach(name => zone.addEventListener(name, event => {
    event.preventDefault(); zone.style.background = '#edf4ef';
  }));
  zone.addEventListener('dragleave', () => {zone.style.background = '';});
  zone.addEventListener('drop', event => {
    event.preventDefault(); zone.style.background = ''; add(event.dataTransfer.files);
  });
})();
