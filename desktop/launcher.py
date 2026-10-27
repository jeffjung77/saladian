"""Personal edition entry point; no developer database or credentials are bundled."""
import os
import sys
from pathlib import Path

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(ROOT))
DATA = Path(os.environ.get('BPMS_DESKTOP_DATA', Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'BPMS' / 'EasybookData'))
DATA.mkdir(parents=True, exist_ok=True)
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.desktop'


def main():
    import json
    import logging
    from logging.handlers import RotatingFileHandler
    import secrets
    import threading
    import webbrowser
    import urllib.request
    import msvcrt
    handler = RotatingFileHandler(DATA / 'easybook.log', maxBytes=2_000_000, backupCount=2, encoding='utf-8')
    logging.basicConfig(level=logging.WARNING, handlers=[handler])
    lock = (DATA / 'running.lock').open('a+b')
    lock.seek(0)
    lock.write(b'0')
    lock.flush()
    lock.seek(0)
    runtime = DATA / 'runtime.json'
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        # Only open a verified existing instance; never launch a second SQLite writer process.
        try:
            info = json.loads(runtime.read_text(encoding='utf-8'))
            request = urllib.request.Request(info['url'] + 'desktop/health/', headers={'X-BPMS-Token': info['token']})
            with urllib.request.urlopen(request, timeout=3) as response:
                if json.load(response).get('application') != 'BPMS Easybook Personal':
                    raise RuntimeError('Unexpected application')
            webbrowser.open(info['url'])
        except Exception:
            from tkinter import messagebox
            messagebox.showinfo('BPMS 쉬운장부', '프로그램이 시작 중입니다. 잠시 후 다시 실행하세요.')
        return
    os.environ['BPMS_LAUNCH_TOKEN'] = secrets.token_urlsafe(32)
    import django
    django.setup()
    from django.core.management import call_command
    call_command('migrate', interactive=False, verbosity=0)
    from django.core.wsgi import get_wsgi_application
    from waitress import create_server
    server = create_server(get_wsgi_application(), host='127.0.0.1', port=0, threads=4, expose_tracebacks=False)
    url = f'http://127.0.0.1:{server.effective_port}/'
    runtime.write_text(json.dumps({'url': url, 'pid': os.getpid(), 'token': os.environ['BPMS_LAUNCH_TOKEN']}), encoding='utf-8')
    worker = threading.Thread(target=server.run, daemon=True)
    worker.start()
    try:
        if '--serve-only' in sys.argv:
            worker.join()
            return
        import tkinter as tk
        from tkinter import messagebox, filedialog
        window = tk.Tk()
        if '--ui-check' in sys.argv:
            window.withdraw()
        window.title('BPMS 쉬운장부 · 개인 PC용')
        window.geometry('480x330')
        window.resizable(False, False)
        tk.Label(window, text='BPMS 쉬운장부', font=('Malgun Gothic', 22, 'bold'), fg='#146b55').pack(pady=(24, 10))
        tk.Label(window, text='프로그램이 실행 중입니다.\n종료하려면 이 창의 종료 버튼을 누르세요.', font=('Malgun Gothic', 11)).pack(pady=8)
        tk.Button(window, text='장부 열기', command=lambda: webbrowser.open(url), width=27).pack(pady=5)

        def credentials():
            if not messagebox.askokcancel('Google Vision 설정', '본인 Google Cloud 프로젝트에서 Vision API와 결제를 활성화하고 발급한 서비스 계정 JSON 파일을 선택하세요.\n\n분석할 때 사진이 Google로 전송되며 이용료가 발생할 수 있습니다.\n장부 입력과 사진 보관에는 이 설정이 필요하지 않습니다.'):
                return
            source = filedialog.askopenfilename(title='본인의 Google 서비스 계정 인증파일 선택', filetypes=[('JSON', '*.json')])
            if not source:
                return
            try:
                from google.oauth2 import service_account
                service_account.Credentials.from_service_account_file(source)
                target = DATA / 'google-vision.json'
                temporary = DATA / 'google-vision.json.tmp'
                temporary.write_bytes(Path(source).read_bytes())
                os.replace(temporary, target)
            except Exception:
                messagebox.showerror('설정 실패', '사용할 수 없는 인증파일입니다. 서비스 계정 JSON 파일을 확인하세요.')
                return
            messagebox.showinfo('설정 완료', 'Google Vision 인증을 설정했습니다. 분석 버튼을 눌러 사용할 수 있습니다.')

        tk.Button(window, text='Google Vision 설정', command=credentials, width=27).pack(pady=5)
        tk.Button(window, text='자료 폴더 열기', command=lambda: os.startfile(str(DATA)), width=27).pack(pady=5)
        tk.Button(window, text='프로그램 종료', command=window.destroy, width=27).pack(pady=5)
        if '--ui-check' in sys.argv:
            window.after(100, window.destroy)
        else:
            window.after(300, lambda: webbrowser.open(url))
        window.mainloop()
    finally:
        server.close()
        runtime.unlink(missing_ok=True)
        lock.close()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import logging
        logging.exception('Personal edition startup failed')
        if '--serve-only' not in sys.argv and '--ui-check' not in sys.argv:
            from tkinter import messagebox
            messagebox.showerror('BPMS 쉬운장부 실행 오류', f'프로그램을 시작하지 못했습니다.\n자료 폴더의 easybook.log를 확인하세요.\n\n{DATA}')
        sys.exit(1)
