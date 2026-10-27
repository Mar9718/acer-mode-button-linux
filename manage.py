#!/usr/bin/python3
"""Instala o retira únicamente los tres archivos administrados del proyecto."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

SOURCE = Path(__file__).resolve().parent
SERVICE = 'acer-nitro-mode.service'
FILES = {
    'src/acer_mode_button.py': 'usr/local/libexec/acer-nitro-mode.py',
    'systemd/acer-nitro-mode.service': 'etc/systemd/system/acer-nitro-mode.service',
    'udev/90-acer-nitro-mode.rules': 'etc/udev/rules.d/90-acer-nitro-mode.rules',
}
STATE = 'var/lib/acer-nitro-mode-public/install.json'


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=30).stdout.strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh():
    run('/usr/bin/systemctl', 'daemon-reload')
    run('/usr/bin/udevadm', 'control', '--reload-rules')
    run('/usr/bin/udevadm', 'trigger', '--subsystem-match=hidraw')
    run('/usr/bin/udevadm', 'settle')


def install(prefix, native):
    manifest = prefix / STATE
    targets = [prefix / relative for relative in FILES.values()]
    for target in targets + [manifest]:
        if target.exists() or target.is_symlink():
            raise RuntimeError('Ya existen archivos administrados. No se sobrescribirán; revisa la instalación anterior.')
    if native:
        for executable in ('python3', 'systemctl', 'udevadm', 'powerprofilesctl'):
            if not (Path('/usr/bin') / executable).is_file():
                raise RuntimeError(f'Falta la dependencia: {executable}.')
        run('/usr/bin/python3', '-I', str(SOURCE / 'src/acer_mode_button.py'), '--check')
        profiles = set(re.findall(r'^\s*\*?\s*(power-saver|balanced|performance):\s*$',
                                  run('/usr/bin/powerprofilesctl', 'list'), re.MULTILINE))
        if profiles != {'power-saver', 'balanced', 'performance'}:
            raise RuntimeError('Se requieren los tres perfiles de energía compatibles.')
    created = []
    activation_started = False
    try:
        for source, relative in FILES.items():
            target = prefix / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            created.append(target)
            shutil.copyfile(SOURCE / source, target)
            target.chmod(0o644)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.parent.chmod(0o700)
        created.append(manifest)
        manifest.write_text(json.dumps({relative: digest(prefix / relative) for relative in FILES.values()}, indent=2) + '\n')
        manifest.chmod(0o600)
        if native:
            restorecon = shutil.which('restorecon', path='/usr/sbin:/usr/bin:/sbin:/bin')
            if restorecon:
                run(restorecon, *map(str, targets))
            activation_started = True
            refresh()
            run('/usr/bin/systemctl', 'enable', '--now', SERVICE)
            if run('/usr/bin/systemctl', 'is-active', SERVICE) != 'active':
                raise RuntimeError('El servicio no quedó activo.')
    except Exception:
        if native and activation_started:
            subprocess.run(['/usr/bin/systemctl', 'disable', '--now', SERVICE], check=False, timeout=30)
        for target in reversed(created):
            target.unlink(missing_ok=True)
        if native and activation_started:
            refresh()
        raise


def uninstall(prefix, native):
    manifest = prefix / STATE
    contents = json.loads(manifest.read_text())
    if set(contents) != set(FILES.values()):
        raise RuntimeError('El registro contiene rutas inesperadas; no se borrará ningún archivo.')
    for relative, expected in contents.items():
        target = prefix / relative
        if target.is_symlink() or not target.is_file() or digest(target) != expected:
            raise RuntimeError('Un archivo instalado cambió o falta. Se conserva todo para revisión manual.')
    if native:
        run('/usr/bin/systemctl', 'disable', '--now', SERVICE)
    for relative in FILES.values():
        (prefix / relative).unlink()
    manifest.unlink()
    if native:
        refresh()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'uninstall'))
    parser.add_argument('--destdir', type=Path, help='Empaquetar en una carpeta temporal sin activar servicios ni consultar hardware.')
    args = parser.parse_args()
    prefix = args.destdir.resolve() if args.destdir else Path('/')
    if args.destdir and prefix == Path('/'):
        parser.error('--destdir debe ser una carpeta temporal, nunca la raíz del sistema.')
    native = prefix == Path('/')
    if native and os.geteuid() != 0:
        parser.error('La instalación real requiere administración; usa sudo.')
    (install if args.action == 'install' else uninstall)(prefix, native)
    print('Operación completada.' if native else 'Operación completada en carpeta temporal; no se activaron servicios.')


if __name__ == '__main__':
    main()
