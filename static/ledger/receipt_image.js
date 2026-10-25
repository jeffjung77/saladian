(() => {
  document.querySelectorAll('.receipt-image-viewer').forEach(viewer => {
    if (viewer.dataset.initialized) return;
    viewer.dataset.initialized = 'true';
    const image = viewer.querySelector('[data-receipt-image]');
    const stage = viewer.querySelector('.receipt-image-stage');
    let rotation = 0;
    function layout() {
      if (!image.naturalWidth || !stage.clientWidth) return;
      const sideways = rotation % 180 !== 0;
      const rotatedWidth = sideways ? image.naturalHeight : image.naturalWidth;
      const rotatedHeight = sideways ? image.naturalWidth : image.naturalHeight;
      const scale = Math.min(1, stage.clientWidth / rotatedWidth);
      stage.style.height = `${rotatedHeight * scale}px`;
      image.style.width = `${image.naturalWidth * scale}px`;
      image.style.height = `${image.naturalHeight * scale}px`;
      image.style.transform = `translate(-50%, -50%) rotate(${rotation}deg)`;
      viewer.querySelector('[data-rotation-label]').textContent = `${rotation}°`;
    }
    viewer.querySelectorAll('[data-rotate]').forEach(button => button.addEventListener('click', () => {
      rotation = button.dataset.rotate === 'reset' ? 0 : (rotation + Number(button.dataset.rotate) + 360) % 360;
      layout();
    }));
    image.addEventListener('load', layout);
    if ('ResizeObserver' in window) new ResizeObserver(layout).observe(stage);
    else window.addEventListener('resize', layout);
    layout();
  });
})();
