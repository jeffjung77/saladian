(() => {
  document.querySelectorAll('.excel-download').forEach(button => {
    button.addEventListener('click', async event => {
      event.preventDefault();
      if (button.dataset.busy) return;
      button.dataset.busy = '1';
      let writer;
      try {
        const filename = `${document.querySelector('h1').textContent.trim()}_${new Date().toLocaleDateString('sv-SE')}.xlsx`;
        let handle;
        // Open while user activation is still available, before awaiting the fetch.
        if (window.isSecureContext && 'showSaveFilePicker' in window) {
          handle = await window.showSaveFilePicker({suggestedName: filename,
            types: [{description: 'Excel 통합 문서', accept: {'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx']}}]});
        }
        const response = await fetch(button.href, {credentials: 'same-origin'});
        if (!response.ok || !response.headers.get('Content-Type')?.includes('spreadsheetml.sheet')) {
          throw new Error('조회 조건을 확인하고 먼저 보고서를 조회한 뒤 다시 다운로드하세요.');
        }
        const blob = await response.blob();
        if (handle) {
          writer = await handle.createWritable();
          await writer.write(blob);
          await writer.close();
          writer = null;
        } else {
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url; link.download = filename;
          document.body.appendChild(link); link.click(); link.remove();
          setTimeout(() => URL.revokeObjectURL(url), 60000);
        }
      } catch (error) {
        if (writer) await writer.abort().catch(() => {});
        if (error.name !== 'AbortError') alert(error.message || 'Excel 다운로드에 실패했습니다. 다시 시도하세요.');
      } finally {
        delete button.dataset.busy;
      }
    });
  });
})();
