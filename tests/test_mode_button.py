import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mode', ROOT / 'src/acer_mode_button.py')
mode = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mode)
spec_manager = importlib.util.spec_from_file_location('manager', ROOT / 'manage.py')
manager = importlib.util.module_from_spec(spec_manager)
spec_manager.loader.exec_module(manager)


class Profiles(unittest.TestCase):
    def test_ac_cycle(self):
        current = 'balanced'
        for expected in ('performance', 'power-saver', 'balanced'):
            current = mode.next_profile(current, True)
            self.assertEqual(current, expected)

    def test_battery_never_selects_performance(self):
        for previous in mode.PROFILES + ('unknown',):
            self.assertIn(mode.next_profile(previous, False), ('power-saver', 'balanced'))

    def test_failed_selection_is_not_reported_as_success(self):
        with patch.object(mode, 'command', side_effect=['balanced', '', 'power-saver']), \
             patch.object(mode, 'on_ac', return_value=True), patch.object(mode, 'show_osd') as osd:
            with self.assertRaises(RuntimeError):
                mode.cycle()
            osd.assert_not_called()


class Devices(unittest.TestCase):
    def test_numbering_and_keyboard_exclusion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wrong = root / 'hidraw2'
            (wrong / 'device').mkdir(parents=True)
            (wrong / 'device/uevent').write_text('HID_ID=0018:00001025:00001825\n')
            for number in (0, 37, 601):
                node = root / f'hidraw{number}'
                (node / 'device').mkdir(parents=True)
                (node / 'device/uevent').write_text('HID_ID=' + mode.HID_ID + '\n')
                with patch.object(Path, 'glob', return_value=[wrong, node]):
                    self.assertEqual(mode.control_device(), '/dev/' + node.name)

    def test_missing_and_ambiguous_devices_rejected(self):
        with patch.object(Path, 'glob', return_value=[]):
            with self.assertRaises(RuntimeError):
                mode.control_device()
        with tempfile.TemporaryDirectory() as temporary:
            node = Path(temporary) / 'hidraw9'
            (node / 'device').mkdir(parents=True)
            (node / 'device/uevent').write_text('HID_ID=' + mode.HID_ID + '\n')
            with patch.object(Path, 'glob', return_value=[node, node]):
                with self.assertRaises(RuntimeError):
                    mode.control_device()

    def test_listen_mode_does_not_change_profile(self):
        def finish_read(_fd, _length):
            mode.RUNNING = False
            return mode.REPORT
        mode.RUNNING = True
        with patch('sys.argv', ['acer_mode_button.py', '--listen']), \
             patch.object(mode, 'control_device', return_value='/dev/hidraw99'), \
             patch.object(mode.os, 'open', return_value=42), \
             patch.object(mode.os, 'close'), patch.object(mode.os, 'read', side_effect=finish_read), \
             patch.object(mode.select, 'select', return_value=([42], [], [])), \
             patch.object(mode.signal, 'signal'), patch.object(mode, 'log') as log, \
             patch.object(mode, 'cycle') as cycle:
            mode.main()
            cycle.assert_not_called()
            log.assert_any_call(evento='boton_detectado', mensaje='04 85 ff')
        mode.RUNNING = True


class Desktop(unittest.TestCase):
    def test_active_session_uid_is_discovered(self):
        with patch.object(mode, 'command', side_effect=['example-session', 'User=42000\nRemote=no\nActive=yes', '']) as command, \
             patch.object(Path, 'exists', return_value=True):
            mode.show_osd('balanced')
            self.assertEqual(command.call_args.args[1], '--address=unix:path=/run/user/42000/bus')

    def test_remote_session_does_not_receive_osd(self):
        with patch.object(mode, 'command', side_effect=['example-session', 'User=42000\nRemote=yes\nActive=yes']) as command:
            mode.show_osd('balanced')
            self.assertEqual(command.call_count, 2)

    def test_no_desktop_is_not_fatal(self):
        with patch.object(mode, 'command', side_effect=OSError):
            mode.show_osd('balanced')


class Packaging(unittest.TestCase):
    def test_staging_root_is_rejected_before_any_operation(self):
        with patch('sys.argv', ['manage.py', 'install', '--destdir', '/']), \
             patch.object(manager, 'install') as install, patch('sys.stderr'):
            with self.assertRaises(SystemExit) as stopped:
                manager.main()
            self.assertEqual(stopped.exception.code, 2)
            install.assert_not_called()

    def test_staged_install_refuses_overwrite_and_uninstalls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manager.install(root, False)
            self.assertTrue((root / manager.STATE).exists())
            with self.assertRaises(RuntimeError):
                manager.install(root, False)
            manager.uninstall(root, False)
            self.assertFalse((root / manager.STATE).exists())
            self.assertTrue(all(not (root / value).exists() for value in manager.FILES.values()))

    def test_uninstall_preserves_edited_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manager.install(root, False)
            target = root / next(iter(manager.FILES.values()))
            target.write_text(target.read_text() + '\n# Local customization\n')
            with self.assertRaises(RuntimeError):
                manager.uninstall(root, False)
            self.assertTrue(all((root / value).exists() for value in manager.FILES.values()))


if __name__ == '__main__':
    unittest.main()
