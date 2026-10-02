"""Build a Windows one-file portal using the build machine's PyInstaller."""
import pathlib
import subprocess
import sys
import zipfile
import argparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORTAL = ROOT / 'portal'
OUTPUT = ROOT / 'portable'
BUILD = ROOT / '.portable-build'
NAME = 'Stack n Stock Portal'


def main():
    global OUTPUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=pathlib.Path, default=OUTPUT)
    OUTPUT = parser.parse_args().output.resolve()
    OUTPUT.mkdir(exist_ok=True)
    BUILD.mkdir(exist_ok=True)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile',
               '--console', '--name', NAME, '--distpath', str(OUTPUT),
               '--workpath', str(BUILD / 'work'), '--specpath', str(BUILD),
               '--paths', str(PORTAL)]
    assets = [('sns_study_portal.html', '.'), ('css', 'css'),
              ('assets/logo', 'assets/logo'), ('algorithms/randomizer.js', 'algorithms')]
    for name in ('event_bus','inventory','state_machine','hardware','data_export',
                 'analysis','persistence','advanced','workspace'):
        assets.append((f'js/{name}.js', 'js'))
    for source, destination in assets:
        command += ['--add-data', f'{PORTAL / source};{destination}']
    subprocess.run(command + [str(PORTAL / 'launch_portal.py')], check=True, cwd=ROOT)
    readme = OUTPUT / 'READ ME.txt'
    readme.write_text('''STACK N STOCK - PORTABLE STUDY PORTAL

Windows 64-bit. No Python, Node.js, installation or internet connection required.

1. Put "Stack n Stock Portal.exe" in a writable folder on your computer or USB drive.
2. Double-click it. Your default browser opens the portal automatically.
3. Keep the server window open while using the portal. Close it to stop the server.

Saved studies and presets live in data/study_sessions.sqlite3 beside the EXE.
Copy the EXE AND its data folder together to move your saved studies.
Stop the portal before copying its data folder. Browser downloads use your
browser's normal download folder; legacy server CSV exports go to data/raw.

This package starts with no study data. Your existing workspace is unchanged.
To bring existing studies, stop both portal servers and copy your original
data/study_sessions.sqlite3 into the portable app's data folder. Do not overwrite
another database containing studies you need to keep.

The browser opens http://127.0.0.1:8765 by default (or the next available port).
Use the NEW address printed in the server window, not an old localhost:8000 tab.
If the browser does not open, double-click the generated Open Portal.html file
beside the EXE while the server window is running.
After refreshing an active session, recovery may require up to 8 seconds for
the previous tab's lease to expire. Use Session history / Retry recovery.

Wait for Saved before closing or moving the app. Failed pending saves stay in
the browser on that computer; resolve them before transferring the data folder.
Hardware is simulated. Smart insights provide advice without changing the protocol.

The executable is unsigned; Windows may show an unknown-publisher prompt.
''', encoding='utf-8')
    archive = OUTPUT / 'Stack n Stock Portal - Portable.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for file in (OUTPUT / f'{NAME}.exe', readme):
            z.write(file, file.name)
    print(f'Portable executable: {OUTPUT / (NAME + ".exe")}')
    print(f'Portable archive: {archive}')


if __name__ == '__main__':
    main()
