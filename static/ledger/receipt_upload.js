(() => {
  const form = document.getElementById('receipt-upload');
  const camera = document.getElementById('receipt-camera');
  const select = document.getElementById('receipt-select');
  const message = document.getElementById('receipt-upload-message');
  let previewUrls = [];
  function clearPreview() {
    previewUrls.forEach(url => URL.revokeObjectURL(url));
    previewUrls = [];
    document.getElementById('receipt-previews').replaceChildren();
  }
  document.getElementById('receipt-camera-button').onclick = () => {
    const mobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    if (!mobile) {
      document.getElementById('receipt-camera-notice').showModal();
      return;
    }
    camera.click();
  };
  document.getElementById('receipt-select-button').onclick = () => select.click();
  function choose(event) {
    const input = event.target;
    if (!input.files.length) return;
    const other = input === camera ? select : camera;
    other.value = ''; other.removeAttribute('name');
    input.name = 'photo';
    clearPreview();
    if (input.files.length > 10 || Array.from(input.files).some(file => file.size > 10 * 1024 * 1024)) {
      input.value = '';
      document.getElementById('receipt-preview-panel').hidden = true;
      message.textContent = '사진은 최대 10장, 사진당 10MB 이하로 선택하세요.';
      return;
    }
    Array.from(input.files).forEach(file => {
      const figure = document.createElement('figure');
      figure.style.margin = '0';
      const image = document.createElement('img');
      const url = URL.createObjectURL(file);
      previewUrls.push(url);
      image.src = url; image.alt = file.name;
      image.style.cssText = 'display:block;width:100%;height:220px;object-fit:contain';
      const caption = document.createElement('figcaption');
      caption.textContent = file.name;
      caption.style.overflowWrap = 'anywhere';
      figure.append(image, caption);
      document.getElementById('receipt-previews').appendChild(figure);
    });
    document.getElementById('receipt-filename').textContent = `선택한 사진 ${input.files.length}장`;
    document.getElementById('receipt-preview-panel').hidden = false;
    message.textContent = '';
  }
  camera.addEventListener('change', choose);
  select.addEventListener('change', choose);
  form.addEventListener('submit', event => {
    const input = form.querySelector('input[name="photo"]');
    if (!input?.files.length || input.files.length > 10 || Array.from(input.files).some(file => file.size > 10 * 1024 * 1024)) {
      event.preventDefault(); message.textContent = '최대 10장, 사진당 10MB 이하의 사진을 선택하세요.'; return;
    }
    document.getElementById('receipt-save').disabled = true;
    message.textContent = '사진을 업로드하고 있습니다.';
  });
})();
