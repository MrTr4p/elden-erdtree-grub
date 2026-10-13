import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1]/'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.defaults = self.root/'defaults'
        self.defaults.write_text('GRUB_TIMEOUT=7\nGRUB_THEME="/old/theme.txt"\n')
        self.grub = self.root/'grub'
        self.grub.mkdir()
        self.config = self.grub/'grub.cfg'
        self.config.write_text('original working config\n')
        self.state = self.root/'state'
        self.target = self.grub/'themes/elden-erdtree'

    def install(self):
        installer.install(self.defaults, self.grub, self.state, '1920x1080', 'mock-grub-mkconfig')

    def test_roundtrip_preserves_other_changes(self):
        original = self.defaults.read_text()
        with patch.object(installer, 'run_mkconfig') as command:
            self.install()
            self.assertEqual((self.state/'defaults.before').read_text(), original)
            self.assertTrue((self.target/'theme.txt').exists())
            self.defaults.write_text(self.defaults.read_text()+'GRUB_DISABLE_OS_PROBER=false\n')
            installer.uninstall(self.state, 'mock-grub-mkconfig')
            self.assertEqual(command.call_count, 2)
        self.assertEqual(self.defaults.read_text(), original+'GRUB_DISABLE_OS_PROBER=false\n')
        self.assertFalse(self.target.exists())
        self.assertFalse(self.state.exists())

    def test_failed_generation_restores_both_files(self):
        original = self.defaults.read_bytes()
        def fail(_, config):
            config.write_text('broken partial output')
            raise subprocess.CalledProcessError(1, ['mock'])
        with patch.object(installer, 'run_mkconfig', side_effect=fail):
            with self.assertRaises(subprocess.CalledProcessError):
                self.install()
        self.assertEqual(self.defaults.read_bytes(), original)
        self.assertEqual(self.config.read_text(), 'original working config\n')
        self.assertFalse(self.target.exists())
        self.assertFalse(self.state.exists())

    def test_failed_uninstall_keeps_installed_state(self):
        with patch.object(installer, 'run_mkconfig'):
            self.install()
        installed = self.defaults.read_bytes()
        with patch.object(installer, 'run_mkconfig', side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                installer.uninstall(self.state, 'mock')
        self.assertEqual(self.defaults.read_bytes(), installed)
        self.assertTrue(self.target.exists())
        self.assertTrue(self.state.exists())

    def test_refuses_existing_destination(self):
        self.target.mkdir(parents=True)
        (self.target/'mine.txt').write_text('keep')
        with self.assertRaises(RuntimeError):
            self.install()
        self.assertEqual((self.target/'mine.txt').read_text(), 'keep')

    def test_refuses_changed_marker(self):
        with patch.object(installer, 'run_mkconfig'):
            self.install()
            (self.target/'.erdtree-install-id').write_text('different')
            with self.assertRaises(RuntimeError):
                installer.uninstall(self.state, 'mock')
        self.assertTrue(self.target.exists())

    def test_path_cannot_inject_shell(self):
        with self.assertRaises(RuntimeError):
            installer.block(Path('/boot/$(touch BAD)/theme.txt'), '1920x1080')

    def test_no_newline_roundtrip(self):
        self.defaults.write_text('GRUB_TIMEOUT=9')
        with patch.object(installer, 'run_mkconfig'):
            self.install()
            installer.uninstall(self.state, 'mock')
        self.assertEqual(self.defaults.read_text(), 'GRUB_TIMEOUT=9')

if __name__ == '__main__':
    unittest.main()
