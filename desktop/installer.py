"""Per-user installer; requires no administrator rights or Python installation."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
DEFAULT = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Programs' / 'BPMS Easybook'


def install(destination, shortcuts=True):
    destination = Path(destination).resolve()
    if destination == Path(destination.anchor) or len(destination.parts) < 3:
        raise ValueError('설치 전용 폴더를 지정하세요.')
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ROOT / 'easybook-payload.zip') as archive:
        for name in archive.namelist():
            target = (destination / name).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('Invalid installer payload')
        archive.extractall(destination)
    executable = destination / 'Easybook.exe'
    if not executable.is_file():
        raise ValueError('Missing executable')
    if shortcuts:
        # Paths are transferred as environment variables, not interpolated into shell code.
        script = """$w = New-Object -ComObject WScript.Shell
$folders = @([Environment]::GetFolderPath('Desktop'), (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'))
foreach ($folder in $folders) {
 $link = $w.CreateShortcut((Join-Path $folder ($env:BPMS_SHORTCUT_NAME + '.lnk')))
 $link.TargetPath = $env:BPMS_INSTALL_EXE
 $link.WorkingDirectory = [System.IO.Path]::GetDirectoryName($env:BPMS_INSTALL_EXE)
 $link.IconLocation = $env:BPMS_INSTALL_EXE + ',0'
 $link.Save()
}
"""
        env = os.environ.copy()
        env.update(BPMS_INSTALL_EXE=str(executable), BPMS_SHORTCUT_NAME='BPMS 쉬운장부')
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], env=env,
            creationflags=subprocess.CREATE_NO_WINDOW, check=True, timeout=30)
    return executable


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install-dir', default=str(DEFAULT))
    parser.add_argument('--silent', action='store_true')
    parser.add_argument('--no-shortcuts', action='store_true')
    parser.add_argument('--ui-check', action='store_true')
    args = parser.parse_args()
    if args.silent:
        install(args.install_dir, not args.no_shortcuts)
        return
    import tkinter as tk
    from tkinter import filedialog, messagebox
    window = tk.Tk()
    if args.ui_check:
        window.withdraw()
    window.title('BPMS 쉬운장부 설치')
    window.geometry('560x320')
    tk.Label(window, text='BPMS 쉬운장부 · 개인 PC용', font=('Malgun Gothic', 19, 'bold'), fg='#146b55').pack(pady=22)
    tk.Label(window, text='Windows 10/11 64비트 · Python 별도 설치 불필요\n장부와 영수증은 사용자 PC에 저장됩니다.').pack(pady=8)
    path = tk.StringVar(value=args.install_dir)
    tk.Entry(window, textvariable=path, width=65).pack(pady=8)
    tk.Button(window, text='설치 폴더 선택', command=lambda: path.set(filedialog.askdirectory() or path.get())).pack(pady=4)
    status = tk.StringVar(value='기존 사용자는 쉬운장부를 종료한 뒤 설치하세요.')
    tk.Label(window, textvariable=status).pack(pady=8)

    def clicked():
        button.config(state='disabled')
        status.set('설치 중입니다. 잠시 기다려 주세요...')
        window.update()
        try:
            executable = install(path.get())
        except Exception:
            messagebox.showerror('설치 실패', '설치하지 못했습니다. 실행 중인 쉬운장부를 종료하고 쓰기 가능한 설치 전용 폴더를 선택하세요.')
            button.config(state='normal')
            return
        if messagebox.askyesno('설치 완료', '바탕화면에 BPMS 쉬운장부 아이콘을 만들었습니다.\n지금 실행할까요?'):
            subprocess.Popen([str(executable)], cwd=executable.parent)
        window.destroy()

    button = tk.Button(window, text='설치하기', command=clicked, width=24)
    button.pack(pady=5)
    if args.ui_check:
        window.after(100, window.destroy)
    window.mainloop()


if __name__ == '__main__':
    main()
