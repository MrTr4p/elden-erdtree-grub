#!/usr/bin/env python3
"""Exercise the public installer in a disposable Arch container, never the host.

Runs Arch's real grub-mkconfig, grub-script-check and font tools. Only device
probing is a fixture because Docker's overlay root is not a bootable disk.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

BASE = Path(__file__).resolve().parents[1]


def main():
    if not Path('/.dockerenv').is_file() or 'ID=arch' not in Path('/etc/os-release').read_text():
        raise SystemExit('Run only in a fresh archlinux:base Docker container.')
    if os.geteuid() != 0:
        raise SystemExit('The disposable container must run as root.')
    defaults = Path('/etc/default/grub')
    config = Path('/boot/grub/grub.cfg')
    target = Path('/boot/grub/themes/elden-erdtree')
    state = Path('/var/lib/elden-erdtree-grub')
    assert not target.exists() and not state.exists()
    config.parent.mkdir(parents=True, exist_ok=True)
    defaults.write_text('GRUB_DEFAULT=0\nGRUB_TIMEOUT=0\nGRUB_DISTRIBUTOR="Arch"\n')
    Path('/etc/grub.d/40_custom').write_text('''#!/bin/sh
exec tail -n +3 "$0"
menuentry 'Arch Linux (installer fixture)' { echo ARCH_ENTRY_PRESERVED; }
menuentry 'Windows (installer fixture)' { echo WINDOWS_ENTRY_PRESERVED; }
''')
    Path('/etc/grub.d/40_custom').chmod(0o755)
    probe = Path('/usr/bin/grub-probe')
    report = {'environment': 'archlinux:base', 'device_probe': 'fixture for Docker overlay', 'checks': {}}

    def run(*args, ok=True, env=None):
        result = subprocess.run(args, cwd=BASE, env=env, text=True, capture_output=True)
        if (result.returncode == 0) != ok:
            raise AssertionError(f'{args}: {result.stdout}\n{result.stderr}')
        return result

    def check(name, condition):
        assert condition, name
        report['checks'][name] = True

    with tempfile.TemporaryDirectory() as directory:
        backup = Path(directory)/'grub-probe'
        shutil.copy2(probe, backup)
        try:
            probe.write_text('''#!/usr/bin/python3
import sys
args=sys.argv[1:]
target=next((arg.split('=',1)[1] for arg in args if arg.startswith('--target=')), '')
for flag in ['-t','--target']:
    if flag in args: target=args[args.index(flag)+1]
values={'device':'/dev/vda1','fs':'ext2','fs_uuid':'11111111-2222-3333-4444-555555555555',
        'drive':'(hd0,gpt1)','partmap':'gpt','compatibility_hint':'hd0,gpt1','hints_string':'--hint=hd0,gpt1'}
if target in values: print(values[target])
''')
            probe.chmod(0o755)
            run('grub-mkconfig', '-o', str(config))
            original = defaults.read_bytes(), config.read_bytes()
            run('./install.sh', '--variant', 'ring', '--dry-run')
            check('dry_run_changes_nothing', original == (defaults.read_bytes(), config.read_bytes())
                  and not state.exists() and not target.exists())
            for variant, resolution in [('ring', '1920x1080'), ('ring', '1024x768'),
                                        ('grace', '1920x1080'), ('carian', '1920x1080'),
                                        ('destined', '1920x1080'), ('farum', '1920x1080')]:
                before = defaults.read_bytes()
                run('./install.sh', '--variant', variant, '--resolution', resolution)
                run('grub-script-check', str(config))
                generated = config.read_text()
                check(f'{variant}_{resolution}_theme_and_entries', str(target/'theme.txt') in generated
                      and 'ARCH_ENTRY_PRESERVED' in generated and 'WINDOWS_ENTRY_PRESERVED' in generated)
                check(f'{variant}_{resolution}_zero_timeout_visible', 'set timeout=5' in generated)
                check(f'{variant}_{resolution}_assets', all((target/name).is_file()
                      for name in ['background.png', 'theme.txt', 'body.pf2', 'small.pf2']))
                check('private_backups', state.stat().st_mode & 0o777 == 0o700)
                installed = defaults.read_bytes(), config.read_bytes()
                run('./install.sh', '--variant', variant, ok=False)
                check('repeat_install_refused_without_changes', installed == (defaults.read_bytes(), config.read_bytes()))
                extra = b'GRUB_CMDLINE_LINUX_DEFAULT="quiet loglevel=3"\n'
                defaults.write_bytes(defaults.read_bytes()+extra)
                run('./install.sh', '--uninstall')
                run('grub-script-check', str(config))
                check(f'{variant}_{resolution}_uninstall', defaults.read_bytes() == before+extra
                      and not target.exists() and not state.exists())
                defaults.write_bytes(before)
            before = defaults.read_bytes(), config.read_bytes()
            shim_dir = Path(directory)/'bin'
            shim_dir.mkdir()
            shim = shim_dir/'grub-mkconfig'
            shim.write_text('#!/bin/sh\nprintf "broken partial config\\n" > "$2"\nexit 1\n')
            shim.chmod(0o755)
            run('./install.sh', '--variant', 'ring', ok=False,
                env={**os.environ, 'PATH': str(shim_dir)+':'+os.environ['PATH']})
            check('failed_generation_restores_defaults_and_config', before == (defaults.read_bytes(), config.read_bytes()))
            check('failed_generation_removes_owned_files', not target.exists() and not state.exists())
        finally:
            shutil.copy2(backup, probe)
    report['packages'] = run('pacman', '-Q', 'grub', 'python', 'python-pillow', 'gcc').stdout.splitlines()
    report['passed'] = True
    output = BASE/'dist/arch-installer-validation.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
