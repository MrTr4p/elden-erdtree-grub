#!/usr/bin/env python3
"""Install or remove the ordinary GRUB theme; never replaces a bootloader."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

BASE = Path(__file__).resolve().parent
BEGIN = '# BEGIN ELDEN ERDTREE GRUB'
END = '# END ELDEN ERDTREE GRUB'
NAME = 'elden-erdtree'

def atomic_write(path, text):
    mode = path.stat() if path.exists() else None
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if mode:
            os.chmod(temporary, mode.st_mode & 0o7777)
            if os.geteuid() == 0:
                os.chown(temporary, mode.st_uid, mode.st_gid)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def remove_block(text):
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise RuntimeError('The installer block was changed; restore from the saved backup manually.')
    start = text.index(BEGIN)
    stop = text.index(END) + len(END)
    if text[stop:stop+1] == '\n':
        stop += 1
    return text[:start] + text[stop:]

def block(theme, resolution):
    # The path becomes shell source; restrict it instead of interpolating arbitrary syntax.
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(theme)):
        raise RuntimeError('Theme path must contain only letters, numbers, /, _, . and -.')
    return (f'{BEGIN}\nGRUB_THEME="{theme}"\nGRUB_GFXMODE="{resolution},auto"\n'
            'unset GRUB_TERMINAL\nGRUB_TERMINAL_OUTPUT="gfxterm"\n'
            'GRUB_TIMEOUT_STYLE="menu"\n'
            'if [ "${GRUB_TIMEOUT:-5}" = 0 ]; then GRUB_TIMEOUT=5; fi\n'
            f'{END}\n')

def run_mkconfig(command, config):
    subprocess.run([command, '-o', str(config)], check=True)

def install(defaults, grub_dir, state, resolution, mkconfig):
    target = grub_dir/'themes'/NAME
    config = grub_dir/'grub.cfg'
    if state.exists() or target.exists():
        raise RuntimeError('Already installed or destination exists. Uninstall first; nothing was overwritten.')
    if not defaults.is_file() or not config.is_file():
        raise RuntimeError('Expected existing defaults and grub.cfg. This installer requires working GRUB.')
    original = defaults.read_text()
    if BEGIN in original or END in original:
        raise RuntimeError('An existing installer block was found; resolve it before installing.')
    addition = block(target/'theme.txt', resolution)
    identity = uuid.uuid4().hex
    target.parent.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, mode=0o700)
    changed = False
    try:
        shutil.copy2(defaults, state/'defaults.before')
        shutil.copy2(config, state/'grub.cfg.before')
        receipt = dict(defaults=str(defaults), grub_dir=str(grub_dir), id=identity,
                       original_had_newline=original.endswith('\n'))
        (state/'receipt.json').write_text(json.dumps(receipt, indent=2))
        with tempfile.TemporaryDirectory(prefix='.erdtree-', dir=target.parent) as stage:
            staged = Path(stage)/'theme'
            if resolution == '1920x1080':
                shutil.copytree(BASE/'theme', staged)
            else:
                subprocess.run(['python3', str(BASE/'build-theme.py'), '--resolution',
                                resolution, '--output', str(staged)], check=True)
            (staged/'.erdtree-install-id').write_text(identity)
            staged.rename(target)
        changed = True
        atomic_write(defaults, original + ('' if original.endswith('\n') else '\n') + addition)
        run_mkconfig(mkconfig, config)
    except BaseException:
        if changed:
            shutil.copy2(state/'defaults.before', defaults)
            shutil.copy2(state/'grub.cfg.before', config)
        if target.exists() and (target/'.erdtree-install-id').read_text() == identity:
            shutil.rmtree(target)
        shutil.rmtree(state)
        raise
    print(f'Installed theme: {target}\nBackups: {state}\nYour existing GRUB bootloader was kept.')

def uninstall(state, mkconfig):
    receipt = json.loads((state/'receipt.json').read_text())
    defaults = Path(receipt['defaults'])
    grub_dir = Path(receipt['grub_dir'])
    config = grub_dir/'grub.cfg'
    target = grub_dir/'themes'/NAME
    marker = target/'.erdtree-install-id'
    if target.is_symlink() or not marker.is_file() or marker.read_text() != receipt['id']:
        raise RuntimeError('Theme ownership marker changed; refusing to remove it.')
    current = defaults.read_text()
    restored = remove_block(current)
    # Preserve exact original text when no unrelated changes were made.
    original = (state/'defaults.before').read_text()
    if restored == original + ('\n' if not original.endswith('\n') else ''):
        restored = original
    with tempfile.TemporaryDirectory(prefix='erdtree-uninstall-') as temporary:
        backup = Path(temporary)/'grub.cfg'
        shutil.copy2(config, backup)
        try:
            atomic_write(defaults, restored)
            run_mkconfig(mkconfig, config)
        except BaseException:
            atomic_write(defaults, current)
            shutil.copy2(backup, config)
            raise
    shutil.rmtree(target)
    shutil.rmtree(state)
    print('Removed the theme and its configuration block; other settings were preserved.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--resolution', default='1920x1080')
    parser.add_argument('--grub-dir', type=Path, help='Usually /boot/grub or /boot/grub2')
    parser.add_argument('--state-dir', type=Path, default=Path('/var/lib/elden-erdtree-grub'))
    args = parser.parse_args()
    args.defaults = Path('/etc/default/grub')
    if not re.fullmatch(r'[0-9]{3,4}x[0-9]{3,4}', args.resolution):
        parser.error('Use a resolution such as 1920x1080.')
    width, height = map(int, args.resolution.split('x'))
    if not (640 <= width <= 4096 and 480 <= height <= 2160):
        parser.error('Supported build sizes: 640x480 through 4096x2160.')
    command = shutil.which('grub-mkconfig') or shutil.which('grub2-mkconfig')
    if args.uninstall:
        if args.dry_run:
            print(f'Would read {args.state_dir}/receipt.json, remove only the marked block and theme, and regenerate grub.cfg.')
            return
    else:
        candidates = [p for p in (Path('/boot/grub'), Path('/boot/grub2')) if p.is_dir()]
        if args.grub_dir is None:
            if len(candidates) != 1:
                parser.error('Specify --grub-dir /boot/grub or --grub-dir /boot/grub2.')
            args.grub_dir = candidates[0]
        args.grub_dir = args.grub_dir.resolve()
        if args.dry_run:
            print(f'Would copy theme to {args.grub_dir}/themes/{NAME}, back up and update '
                  f'{args.defaults}, then run {command or "grub-mkconfig"} -o {args.grub_dir}/grub.cfg.\n'
                  f'Backup directory: {args.state_dir}\nResolution: {args.resolution}\nNo files changed.')
            return
    if os.geteuid() != 0:
        parser.error('Use sudo to install/uninstall, or --dry-run to inspect without changes.')
    if not command:
        parser.error('Install GRUB first; grub-mkconfig/grub2-mkconfig was not found.')
    try:
        if args.uninstall:
            uninstall(args.state_dir.resolve(), command)
        else:
            install(args.defaults.resolve(), args.grub_dir, args.state_dir.resolve(), args.resolution, command)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Installation stopped: {error}\n')
if __name__ == '__main__':
    main()
