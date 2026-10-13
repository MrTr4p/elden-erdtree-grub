import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('efi_builder', Path(__file__).resolve().parents[1]/'make-efi.py')
efi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(efi)


class EfiLoaderTest(unittest.TestCase):
    def test_variant_and_effects_restored_after_host_config(self):
        script = efi.loader('1234-ABCD', '/@/boot/grub/grub.cfg', '1920x1080', 'ring')
        after_source = script.split('source ($erdtree_root)', 1)[1]
        for setting in ['set erdtree_variant=ring', 'export erdtree_variant',
                        'set erdtree_motion=1', 'set erdtree_ambient=1',
                        'set prefix=(memdisk)/boot/grub']:
            self.assertIn(setting, after_source)
        self.assertIn('/@/boot/grub/grub.cfg', script)

    def test_rejects_injected_values_and_bad_sizes(self):
        for uuid, path, size, variant in [
            ('1234; reboot', '/grub.cfg', '1920x1080', 'ring'),
            ('1234', '/grub.cfg;reboot', '1920x1080', 'ring'),
            ('1234', '/../grub.cfg', '1920x1080', 'ring'),
            ('1234', '/grub.cfg', '9999x9999', 'ring'),
            ('1234', '/grub.cfg', '1920x1080', 'ring; reboot'),
        ]:
            with self.subTest(uuid=uuid, path=path, size=size, variant=variant):
                with self.assertRaises(ValueError):
                    efi.loader(uuid, path, size, variant)


if __name__ == '__main__':
    unittest.main()
