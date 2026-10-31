(() => {
  const config = JSON.parse(document.getElementById('idle-session-config').textContent);
  const timeout = 30 * 60 * 1000;
  const key = 'bpms-last-activity:' + config.user;
  let last = Date.now(), lastPing = 0, closing = false;
  const remember = () => {try {localStorage.setItem(key, String(last));} catch (_) {}};
  remember();
  async function expire() {
    if (closing) return;
    closing = true;
    try {
      await fetch(config.logout, {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':config.csrf}});
    } finally {
      alert('30분 동안 활동이 없어 자동 로그아웃되었습니다. 다시 로그인해 주세요.');
      location.replace(config.login);
    }
  }
  function check() {
    try {last = Math.max(last, Number(localStorage.getItem(key)) || 0);} catch (_) {}
    if (Date.now() - last >= timeout) {expire(); return false;}
    return !closing;
  }
  function active(event) {
    if (!event.isTrusted || !check()) return;
    last = Date.now(); remember();
    if (last - lastPing < 60000) return;
    lastPing = last;
    fetch(config.activity, {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':config.csrf}})
      .then(response => {if (response.status === 401 || response.redirected) expire();})
      .catch(() => {});
  }
  ['pointerdown','keydown','input','scroll','touchstart','mousemove'].forEach(name =>
    document.addEventListener(name, active, {passive:true}));
  window.addEventListener('storage', event => {if (event.key === key) check();});
  function verifySession() {
    if (!check()) return;
    fetch(config.activity, {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':config.csrf}})
      .then(response => {if (response.status === 401 || response.redirected) {
        closing = true;
        location.replace(config.login);
      }})
      .catch(() => {});
  }
  window.addEventListener('pageshow', verifySession);
  document.addEventListener('visibilitychange', check);
  setInterval(check, 1000);
})();
