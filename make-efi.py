#!/usr/bin/env python3
"""Build an experimental, self-contained x86_64 EFI file. Does not install it."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile
from variants import VARIANTS

BASE = Path(__file__).resolve().parent

def loader(uuid, config_path, resolution, variant='grace'):
    if variant not in VARIANTS:
        raise ValueError('Unknown theme variant.')
    if not re.fullmatch(r'[A-Za-z0-9-]+', uuid):
        raise ValueError('Invalid filesystem UUID.')
    if not re.fullmatch(r'/[A-Za-z0-9_./@+-]+', config_path) or '..' in config_path.split('/'):
        raise ValueError('Use a simple absolute GRUB-relative config path.')
    if not re.fullmatch(r'[0-9]{3,4}x[0-9]{3,4}', resolution):
        raise ValueError('Invalid resolution.')
    width, height = map(int, resolution.split('x'))
    if not (640 <= width <= 4096 and 480 <= height <= 2160):
        raise ValueError('Supported sizes: 640x480 through 4096x2160.')
    return f"""# All modules come from this image, including the patched normal/gfxmenu pair.
set prefix=(memdisk)/boot/grub
set erdtree_motion=1
export erdtree_motion
set erdtree_variant={variant}
export erdtree_variant
set erdtree_ambient=1
export erdtree_ambient
if search --no-floppy --fs-uuid --set=erdtree_root {uuid}; then
  if [ -f ($erdtree_root){config_path} ]; then
    source ($erdtree_root){config_path}
    set prefix=(memdisk)/boot/grub
    insmod all_video
    insmod gfxterm
    insmod gfxmenu
    insmod png
    loadfont (memdisk)/boot/grub/fonts/unicode.pf2
    loadfont (memdisk)/boot/grub/themes/erdtree/body.pf2
    loadfont (memdisk)/boot/grub/themes/erdtree/small.pf2
    set gfxmode={resolution},auto
    terminal_output --append gfxterm
    set theme=(memdisk)/boot/grub/themes/erdtree/theme.txt
    export theme
    set erdtree_motion=1
    export erdtree_motion
    set erdtree_variant={variant}
    export erdtree_variant
    set erdtree_ambient=1
    export erdtree_ambient
    set timeout_style=menu
    if [ "$timeout" = 0 ]; then set timeout=5; fi
  else
    echo 'Erdtree: configured grub.cfg is missing. Use your original firmware boot entry.'
    sleep --interruptible 15
  fi
else
  echo 'Erdtree: configuration filesystem not found. Use your original firmware boot entry.'
  sleep --interruptible 15
fi
"""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path, help='Existing full grub.cfg to inspect; never modified')
    parser.add_argument('--fs-uuid', required=True, help='Filesystem containing the full grub.cfg')
    parser.add_argument('--config-path', required=True, help='Path inside that filesystem, as reported by grub-mkrelpath')
    parser.add_argument('--theme-dir', type=Path, help='Existing generated theme; otherwise build the chosen variant')
    parser.add_argument('--variant', choices=VARIANTS, default='grace')
    parser.add_argument('--resolution', default='1920x1080')
    parser.add_argument('--output', type=Path, default=BASE/'dist/erdtree-x86_64.efi')
    args = parser.parse_args()
    content = args.config.read_text()
    if re.search(r'^\s*(?:set\s+prefix\s*=|configfile\s|normal(?:\s|$))', content, re.M):
        parser.error('Use a full grub.cfg without prefix reassignment or top-level configfile/normal handoffs.')
    if not re.search(r'^\s*(?:menuentry|submenu)\s', content, re.M):
        parser.error('No menu entries found. This may be an EFI stub instead of the full grub.cfg.')
    executable = BASE/'prefix/bin/grub-mkstandalone'
    if not executable.exists():
        parser.error('Run ./build.sh first.')
    try:
        config = loader(args.fs_uuid, args.config_path, args.resolution, args.variant)
    except ValueError as error:
        parser.error(str(error))
    font = BASE/'prefix/share/grub/unicode.pf2'
    if not font.exists():
        parser.error('Missing unicode.pf2; install GRUB fonts and run ./build.sh again.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='erdtree-efi-') as directory:
        theme_dir = args.theme_dir
        if theme_dir is None:
            theme_dir = Path(directory)/'theme'
            subprocess.run(['python3', str(BASE/'build-theme.py'), '--variant', args.variant,
                            '--resolution', args.resolution, '--output', str(theme_dir)], check=True)
        for name in ['theme.txt', 'background.png', 'body.pf2', 'small.pf2']:
            if not (theme_dir/name).is_file():
                parser.error(f'Missing theme asset: {theme_dir/name}')
        entry = Path(directory)/'grub.cfg'
        entry.write_text(config)
        subprocess.run([str(BASE/'prefix/bin/grub-script-check'), str(entry)], check=True)
        sources = [f'boot/grub/grub.cfg={entry}', f'boot/grub/fonts/unicode.pf2={font}']
        for path in sorted(theme_dir.iterdir()):
            if path.suffix in ('.png', '.pf2') or path.name == 'theme.txt':
                sources.append(f'boot/grub/themes/erdtree/{path.name}={path.resolve()}')
        subprocess.run([str(executable), '-O', 'x86_64-efi',
                        '-d', str(BASE/'prefix/lib/grub/x86_64-efi'),
                        '--fonts=', '--locales=', '--themes=',
                        '--modules=part_gpt part_msdos fat ext2 btrfs normal gfxmenu search search_fs_uuid',
                        '-o', str(args.output), *sources], check=True)
    print(f'Built {args.output}. Nothing was installed to your ESP or firmware.')

if __name__ == '__main__':
    main()
