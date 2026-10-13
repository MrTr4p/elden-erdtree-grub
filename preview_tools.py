"""Portable QEMU/OVMF discovery. Optional extracted tool bundle: GRUB_PREVIEW_TOOLS."""
import os
from pathlib import Path
import shutil

def firmware_args(found, work):
    code = Path(found['ovmf'])
    if 'CODE' not in code.name:
        return ['-bios', str(code)]
    variables = Path(os.environ.get('OVMF_VARS', str(code).replace('CODE', 'VARS').replace('.secboot', '')))
    if not variables.is_file():
        raise SystemExit('Set OVMF_VARS to the matching writable firmware template.')
    copy = Path(work)/'OVMF_VARS.fd'
    shutil.copy2(variables, copy)
    return ['-drive', f'if=pflash,format=raw,unit=0,readonly=on,file={code}',
            '-drive', f'if=pflash,format=raw,unit=1,file={copy}']

def tools():
    root = Path(os.environ.get('GRUB_PREVIEW_TOOLS', '/usr'))
    def executable(name):
        bundled = root / 'bin' / name
        found = str(bundled) if bundled.is_file() else shutil.which(name)
        if not found:
            raise SystemExit(f'Missing {name}; see docs/BUILD.md for preview dependencies.')
        return found
    def first(paths, label):
        for path in paths:
            if path and Path(path).exists():
                return str(path)
        raise SystemExit(f'Missing {label}; see docs/BUILD.md.')
    ovmf = first([os.environ.get('OVMF_CODE'),
                  root/'share/edk2/x64/OVMF.4m.fd',
                  root/'share/edk2/x64/OVMF_CODE.4m.fd',
                  root/'share/edk2/x64/OVMF_CODE.fd',
                  root/'share/OVMF/OVMF_CODE_4M.fd',
                  root/'share/OVMF/OVMF_CODE.fd',
                  root/'share/edk2/ovmf/OVMF_CODE.fd'], 'OVMF firmware (or set OVMF_CODE)')
    font = first([Path(__file__).resolve().parent/'prefix/share/grub/unicode.pf2',
                  '/usr/share/grub/unicode.pf2', '/usr/share/grub2/unicode.pf2'], 'unicode.pf2')
    accel = os.environ.get('QEMU_ACCEL', 'kvm' if os.access('/dev/kvm', os.R_OK | os.W_OK) else 'tcg')
    if accel not in ('kvm', 'tcg'):
        raise SystemExit('QEMU_ACCEL must be kvm or tcg.')
    return dict(qemu=executable('qemu-system-x86_64'), xorriso=executable('xorriso'),
                qemu_data=first([root/'share/qemu', '/usr/share/qemu'], 'QEMU data'),
                ovmf=ovmf, font=font, accel=accel, cpu='host' if accel == 'kvm' else 'max',
                root=str(root))

def preview_env(found):
    env = os.environ.copy()
    if 'GRUB_PREVIEW_TOOLS' in env:
        env['LD_LIBRARY_PATH'] = str(Path(found['root'])/'lib') + (
            ':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
        env['PATH'] = str(Path(found['root'])/'bin') + ':' + env.get('PATH', '')
    return env
