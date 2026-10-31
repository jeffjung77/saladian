(() => {
 const banner = document.getElementById('deployment-banner');
 const dialog = document.getElementById('deployment-notice');
 let lastState = null, cutoffTimer;
 const close = () => {dialog.close(); if (lastState) {try {sessionStorage.setItem('bpms-deploy-seen:' + lastState.id, '1');} catch (_) {}}};
 document.getElementById('deployment-notice-close').addEventListener('click', close);
 dialog.addEventListener('cancel', () => {if(lastState) {try {sessionStorage.setItem('bpms-deploy-seen:' + lastState.id,'1');} catch (_) {}}});
 function show(state) {
  lastState = state;
  if (state.blocked) {location.replace('/maintenance/'); return;}
  banner.hidden = !state.active;
  clearTimeout(cutoffTimer);
  if (!state.active) {if (dialog.open) dialog.close(); return;}
  const message = (state.simulation ? '[개발 모의 실행] ' : '') + state.label + ' 배포 예정입니다. 00:00에 자동 로그아웃됩니다. ' + state.message;
  banner.textContent = message;
  document.getElementById('deployment-notice-text').textContent = message;
  let seen = false;
  try {seen = sessionStorage.getItem('bpms-deploy-seen:' + state.id) === '1';} catch (_) {}
  if (!seen && !dialog.open && !document.querySelector('dialog[open]')) dialog.showModal();
  // Re-check the server at the boundary, so cancelled schedules cannot log users out.
  cutoffTimer = setTimeout(poll, Math.max(1000, Date.parse(state.cutoff) - Date.now()));
 }
 async function poll() {
  try {const response = await fetch('/deployment/status/', {credentials:'same-origin',cache:'no-store'}); if(response.ok) show(await response.json());} catch (_) {}
 }
 poll(); setInterval(poll, 5000);
 window.addEventListener('pageshow', poll);
 document.addEventListener('visibilitychange', () => {if (!document.hidden) poll();});
})();
