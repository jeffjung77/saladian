"""Build from an explicit clean source stage, never from the working database."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

PROJECT = Path(__file__).resolve().parent.parent
BUILD = PROJECT / 'build' / 'personal'
STAGE = BUILD / 'source'
DIST = PROJECT / 'dist'
RELEASE = DIST / 'release'


def copy_sources():
    # A new build uses only program sources and public assets. No sqlite/media/env/key files.
    STAGE.mkdir(parents=True, exist_ok=True)
    for package in ('config', 'ledger', 'desktop'):
        for source in (PROJECT / package).rglob('*'):
            relative = source.relative_to(PROJECT)
            if not source.is_file() or '__pycache__' in source.parts:
                continue
            if source.suffix == '.py' and not source.name.startswith('test'):
                if package == 'config' and source.name not in ('__init__.py', 'settings.py', 'desktop.py', 'urls.py', 'wsgi.py'):
                    continue
                if package == 'desktop' and source.name in ('build.py', 'installer.py', 'smoke_test.py'):
                    continue
            elif 'templates' in source.parts and source.suffix in ('.html', '.txt'):
                pass
            else:
                continue
            target = STAGE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    shutil.copy2(PROJECT / 'manage.py', STAGE / 'manage.py')
    shutil.copytree(PROJECT / 'static', STAGE / 'static', dirs_exist_ok=True)


def run(command, env):
    subprocess.run([sys.executable, *command], cwd=STAGE, env=env, check=True)


def main():
    if STAGE.exists():
        # Verified fixed build target only; never touch program data.
        assert STAGE.resolve().is_relative_to((PROJECT / 'build').resolve())
        shutil.rmtree(STAGE)
    copy_sources()
    env = os.environ.copy()
    env.update(DJANGO_SETTINGS_MODULE='config.desktop', BPMS_DESKTOP_DATA=str(BUILD / 'build-data'), PYTHONPATH=str(STAGE))
    # Some Python 3.14 Windows installs ship Tcl/Tk scripts as separate archives.
    tk_runtime = BUILD / 'tk-runtime'
    for archive_path in (Path(sys.base_prefix) / 'tcl').glob('libt*.zip'):
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(tk_runtime)
    if (tk_runtime / 'tcl_library/init.tcl').exists():
        env['TCL_LIBRARY'] = str(tk_runtime / 'tcl_library')
    if (tk_runtime / 'tk_library/tk.tcl').exists():
        env['TK_LIBRARY'] = str(tk_runtime / 'tk_library')
    for key in ('GOOGLE_APPLICATION_CREDENTIALS', 'DJANGO_SECRET_KEY', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN'):
        env.pop(key, None)
    run(['manage.py', 'collectstatic', '--noinput', '--verbosity', '0'], env)
    icon = BUILD / 'easybook.ico'
    from PIL import Image
    with Image.open(PROJECT / 'static' / 'branding' / 'bpms-logo.png') as image:
        image.convert('RGBA').save(icon, sizes=[(16,16), (32,32), (48,48), (128,128), (256,256)])
    imports = []
    for package in ('config', 'ledger', 'desktop'):
        for source in (STAGE / package).rglob('*.py'):
            module = '.'.join(source.relative_to(STAGE).with_suffix('').parts)
            if module.endswith('.__init__'):
                module = module[:-9]
            imports.extend(['--hidden-import', module])
    run(['-m', 'PyInstaller', '--clean', '--noconfirm', '--onedir', '--windowed', '--name', 'Easybook',
        '--icon', str(icon), '--distpath', str(DIST / 'personal'), '--workpath', str(BUILD / 'pyinstaller-app'),
        '--specpath', str(BUILD), '--paths', str(STAGE),
        '--add-data', f'{STAGE / "ledger/templates"}:ledger/templates', '--add-data', f'{STAGE / "desktop/templates"}:desktop/templates',
        '--add-data', f'{STAGE / "desktop_static"}:desktop_static',
        '--hidden-import', 'waitress', '--hidden-import', 'whitenoise.middleware',
        '--hidden-import', 'google.cloud.vision', '--hidden-import', 'google.auth.transport.requests',
        '--hidden-import', 'django.contrib.sessions.backends.db', '--hidden-import', 'django.contrib.messages.storage.fallback',
        *imports, 'desktop/launcher.py'], env)
    app = DIST / 'personal' / 'Easybook'
    public_certificates = {'certifi/cacert.pem', 'grpc/_cython/_credentials/roots.pem'}
    forbidden = [p for p in app.rglob('*') if p.is_file() and
        (p.suffix in ('.sqlite3', '.pem', '.key') or p.name.startswith('.env') or p.name == 'google-vision.json') and
        p.relative_to(app / '_internal').as_posix() not in public_certificates]
    if forbidden:
        raise RuntimeError('Unexpected private material in application bundle: ' + str(forbidden))
    shutil.copy2(PROJECT / 'desktop' / 'README.md', app / 'README.md')
    from importlib.metadata import distributions
    notices = app / 'third-party-licenses'
    notices.mkdir(exist_ok=True)
    for distribution in distributions():
        for entry in distribution.files or []:
            if any(part.lower().startswith(('license', 'copying', 'notice')) for part in entry.parts):
                original = Path(distribution.locate_file(entry))
                if original.is_file():
                    folder = notices / distribution.metadata['Name']
                    folder.mkdir(exist_ok=True)
                    shutil.copy2(original, folder / original.name)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.exists():
        shutil.copy2(python_license, notices / 'Python-LICENSE.txt')
    payload = BUILD / 'easybook-payload.zip'
    with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in app.rglob('*'):
            if path.is_file():
                archive.write(path, path.relative_to(app).as_posix())
    RELEASE.mkdir(parents=True, exist_ok=True)
    run(['-m', 'PyInstaller', '--clean', '--noconfirm', '--onefile', '--windowed', '--name', 'EasybookSetup',
        '--icon', str(icon), '--distpath', str(RELEASE), '--workpath', str(BUILD / 'pyinstaller-installer'),
        '--specpath', str(BUILD), '--add-data', f'{payload}:.', str(PROJECT / 'desktop' / 'installer.py')], env)
    with zipfile.ZipFile(RELEASE / 'Easybook-Personal-Windows-x64.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in app.rglob('*'):
            if path.is_file():
                archive.write(path, 'Easybook/' + path.relative_to(app).as_posix())
    shutil.copy2(PROJECT / 'desktop' / 'README.md', RELEASE / 'README.md')
    entries = []
    for path in sorted(RELEASE.iterdir()):
        if path.is_file() and path.suffix in ('.exe', '.zip'):
            entries.append({'file': path.name, 'bytes': path.stat().st_size, 'sha256': hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()})
    (RELEASE / 'SHA256.json').write_text(json.dumps(entries, indent=2), encoding='utf-8')
    print('Release ready:', RELEASE)


if __name__ == '__main__':
    main()
