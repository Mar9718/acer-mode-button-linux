#!/usr/bin/python3
"""Botón de modo HID Acer -> perfiles nativos de Linux/KDE.

Sólo abre en lectura el control Acer 1025:174B. No lee el teclado,
no escribe mensajes HID y no modifica registros EC ni ventiladores.
"""
import json
import argparse
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

HID_ID = '0018:00001025:0000174B'
REPORT = bytes.fromhex('04 85 ff')
PROFILES = ('power-saver', 'balanced', 'performance')
LABELS = {'power-saver': 'Ahorro de energía', 'balanced': 'Equilibrado', 'performance': 'Rendimiento'}
RUNNING = True


def log(**values):
    print(json.dumps(values, ensure_ascii=False), flush=True)


def command(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=8).stdout.strip()


def on_ac():
    for supply in Path('/sys/class/power_supply').glob('*'):
        try:
            if (supply / 'type').read_text().strip() != 'Battery' and (supply / 'online').read_text().strip() == '1':
                return True
        except OSError:
            continue
    return False


def show_osd(profile):
    # Consultar la sesión local activa evita fijar un UID o nombre de usuario.
    try:
        session = command('/usr/bin/loginctl', 'show-seat', 'seat0', '-p', 'ActiveSession', '--value')
        if not session:
            return
        properties = dict(line.split('=', 1) for line in command(
            '/usr/bin/loginctl', 'show-session', session, '-p', 'User', '-p', 'Remote', '-p', 'Active'
        ).splitlines() if '=' in line)
        uid = properties.get('User', '')
        if not uid.isdecimal() or properties.get('Remote') != 'no' or properties.get('Active') != 'yes':
            return
        bus = Path('/run/user') / uid / 'bus'
        if not bus.exists():
            return
        address = 'unix:path=' + str(bus)
        command('/usr/bin/busctl', '--address=' + address, 'call',
                'org.kde.plasmashell', '/org/kde/osdService',
                'org.kde.osdService', 'powerProfileChanged', 's', profile)
    except (OSError, subprocess.SubprocessError):
        # Un escritorio ausente o distinto de KDE no afecta al cambio de perfil.
        pass


def next_profile(previous, ac):
    allowed = PROFILES if ac else PROFILES[:2]
    return allowed[(allowed.index(previous) + 1) % len(allowed)] if previous in allowed else 'balanced'


def cycle():
    previous = command('/usr/bin/powerprofilesctl', 'get')
    ac = on_ac()
    target = next_profile(previous, ac)
    command('/usr/bin/powerprofilesctl', 'set', target)
    actual = command('/usr/bin/powerprofilesctl', 'get')
    if actual != target:
        raise RuntimeError(f'El servicio de energía devolvió {actual}, se solicitó {target}.')
    log(evento='perfil_cambiado', anterior=previous, perfil=actual,
        nombre=LABELS[actual], conectado=ac)
    show_osd(actual)


def control_device():
    matches = []
    for node in Path('/sys/class/hidraw').glob('hidraw*'):
        try:
            if 'HID_ID=' + HID_ID + '\n' in (node / 'device/uevent').read_text():
                matches.append('/dev/' + node.name)
        except OSError:
            continue
    if len(matches) != 1:
        raise RuntimeError(f'Se requiere una interfaz Acer 1025:174B; encontradas: {len(matches)}.')
    return matches[0]


def stop(*args):
    global RUNNING
    RUNNING = False


def main():
    parser = argparse.ArgumentParser(description='Botón HID Acer 1025:174B -> perfiles de energía.')
    parser.add_argument('--check', action='store_true', help='Comprobar el control compatible sin cambiar perfiles.')
    parser.add_argument('--listen', action='store_true', help='Observar sólo la señal conocida del botón, sin cambiar perfiles.')
    args = parser.parse_args()
    if args.check and args.listen:
        parser.error('--check y --listen son modos alternativos.')
    device = control_device()
    if args.check:
        log(evento='control_encontrado', hid_id=HID_ID, mensaje_esperado=REPORT.hex(' '))
        return
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
    last_press = -10.0
    log(evento='escuchando', mensaje=REPORT.hex(' '), acceso='solo lectura')
    try:
        while RUNNING:
            if not select.select([fd], [], [], 1)[0]:
                continue
            data = os.read(fd, 4096)
            if not data:
                raise RuntimeError('La interfaz Acer se desconectó.')
            now = time.monotonic()
            if data == REPORT and now - last_press >= 0.8:
                last_press = now
                if args.listen:
                    log(evento='boton_detectado', mensaje=REPORT.hex(' '))
                    continue
                try:
                    cycle()
                except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                    log(evento='error_cambiando_perfil', detalle=str(error))
    finally:
        os.close(fd)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        log(evento='error', detalle=str(error))
        sys.exit(1)
