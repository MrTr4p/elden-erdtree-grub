#!/usr/bin/env python3
"""Test and record real GRUB in a UEFI VM. No host disks or network attached."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import numpy as np
from PIL import Image
from variants import VARIANTS, preview_tag

BASE = Path(__file__).resolve().parent
from preview_tools import tools, preview_env, firmware_args
TOOLS = tools()
ENV = preview_env(TOOLS)
spec = importlib.util.spec_from_file_location('theme_builder', BASE / 'build-theme.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
parser = argparse.ArgumentParser()
parser.add_argument('--resolution', default='1920x1080')
parser.add_argument('--variant', choices=VARIANTS, default='grace')
parser.add_argument('--record', action='store_true')
parser.add_argument('--static', action='store_true')
parser.add_argument('--no-ambient', action='store_true', help='Keep selection effects but disable the animated scene')
parser.add_argument('--autoboot', action='store_true')
parser.add_argument('--standalone', action='store_true', help='Test make-efi.py in a disposable FAT image')
parser.add_argument('--stock', action='store_true', help='Test ordinary theme with system GRUB')
args = parser.parse_args()
if args.stock:
    args.static = True
runtime = Path('/usr') if args.stock else BASE/'prefix'
width, height = map(int, args.resolution.split('x'))
scene_rect = (.27,.205,.73,.67) if args.variant == 'ring' else (.5,0,1,1)
menu_rect = (.34,.675,.66,.99) if args.variant == 'ring' else (0,0,.5,1)
title_rect = (0,0,1,.20) if args.variant == 'ring' else (0,0,.48,.44)
pulse_rect = (.35,.71,.65,.75) if args.variant == 'ring' else (.04,.52,.47,.61)
tag = preview_tag(args.resolution, args.variant, '-stock' if args.stock else '-standalone' if args.standalone else '-static' if args.static else '-autoboot' if args.autoboot else '-no-ambient' if args.no_ambient else '')
ambient = not args.static and not args.no_ambient
work = BASE / 'previews' / tag
work.mkdir(parents=True, exist_ok=True)
iso_root = work / 'iso'
theme = iso_root / 'boot/grub/themes/erdtree'
builder.build_theme(theme, width, height, args.variant)
fonts = iso_root / 'boot/grub/fonts'
fonts.mkdir(parents=True, exist_ok=True)
shutil.copy2(TOOLS['font'], fonts / 'unicode.pf2')

def run(command, **kwargs):
    result = subprocess.run(command, env=ENV, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-6000:])
    return result

font_commands = '\n'.join(f'loadfont /boot/grub/themes/erdtree/{p.name}' for p in theme.glob('*.pf2'))
config = f'''serial --unit=0 --speed=115200
set default=0
set timeout_style=menu
set timeout={3 if args.autoboot else -1}
set erdtree_motion={0 if args.static else 1}
export erdtree_motion
set erdtree_ambient={1 if ambient else 0}
export erdtree_ambient
set erdtree_variant={'grace' if args.standalone else args.variant}
export erdtree_variant
insmod efi_gop
insmod efi_uga
insmod gfxterm
insmod gfxmenu
insmod png
loadfont /boot/grub/fonts/unicode.pf2
{font_commands}
set gfxterm_font="Unifont Regular 16"
set gfxmode={args.resolution},auto
terminal_output gfxterm serial
set theme=/boot/grub/themes/erdtree/theme.txt
export theme
echo ERDTREE_MENU_READY
menuentry 'Linux' --hotkey=l {{ echo ERDTREE_LINUX_SELECTED; sleep 1; }}
menuentry 'Windows' --hotkey=w {{ echo ERDTREE_WINDOWS_SELECTED; sleep 1; }}
submenu 'Advanced options' {{
 menuentry 'Linux (recovery)' {{ echo ERDTREE_RECOVERY_SELECTED; sleep 1; }}
 menuentry 'Linux (text console)' {{ echo ERDTREE_TEXT_SELECTED; sleep 1; }}
}}
menuentry 'UEFI Firmware Settings' {{ echo ERDTREE_FIRMWARE_SELECTED; sleep 1; }}
'''
(iso_root / 'boot/grub/grub.cfg').write_text(config)
run([str(runtime / 'bin/grub-script-check'), str(iso_root / 'boot/grub/grub.cfg')])
iso = work / ('preview.img' if args.standalone else 'preview.iso')
if args.standalone:
    efi = work / 'BOOTX64.EFI'
    run(['python3', str(BASE/'make-efi.py'), '--config', str(iso_root/'boot/grub/grub.cfg'),
         '--fs-uuid', 'EED7-2026', '--config-path', '/boot/grub/grub.cfg',
         '--theme-dir', str(theme), '--variant', args.variant,
         '--resolution', args.resolution, '--output', str(efi)])
    with iso.open('wb') as disk:
        disk.truncate(64 * 1024 * 1024)
    run(['mkfs.fat', '-F', '16', '-i', 'EED72026', str(iso)])
    run(['mmd', '-i', str(iso), '::/EFI', '::/EFI/BOOT'])
    run(['mcopy', '-i', str(iso), str(efi), '::/EFI/BOOT/BOOTX64.EFI'])
    run(['mcopy', '-s', '-i', str(iso), str(iso_root/'boot'), '::/'])
    boot_args = ['-boot', 'order=c', '-drive', f'file={iso},format=raw,snapshot=on']
else:
    run([str(runtime / 'bin/grub-mkrescue'), '-d', str(runtime / 'lib/grub/x86_64-efi'),
         f'--xorriso={TOOLS["xorriso"]}', '-o', str(iso), str(iso_root)])
    boot_args = ['-boot', 'order=d', '-drive', f'file={iso},media=cdrom,readonly=on']
qmp = work / 'qmp.sock'
qmp.unlink(missing_ok=True)
serial = work / 'serial.log'
serial.write_text('')
vm_command = [TOOLS['qemu'], '-L', TOOLS['qemu_data'],
    '-machine','q35','-accel',TOOLS['accel'],'-cpu',TOOLS['cpu'],'-m','512','-vga','std',
    *firmware_args(TOOLS, work),'-display','none','-nic','none',
    '-no-reboot', *boot_args,
    '-serial',f'file:{serial}','-qmp',f'unix:{qmp},server=on,wait=off']
(work / 'vm-command.json').write_text(json.dumps(vm_command, indent=2))
report = {'resolution':args.resolution,'host_disks_attached':False,
    'mode':'stock' if args.stock else 'standalone' if args.standalone else 'static' if args.static else 'autoboot' if args.autoboot else 'interactive',
    'ambient':ambient, 'variant':args.variant,
    'iso_sha256':hashlib.sha256(iso.read_bytes()).hexdigest(),'checks':{}}
vm = subprocess.Popen(vm_command,env=ENV,stdout=subprocess.DEVNULL,stderr=(work/'qemu.log').open('w'))
encoder = None
try:
    sock = socket.socket(socket.AF_UNIX)
    sock.settimeout(15)
    for _ in range(150):
        if vm.poll() is not None:
            raise RuntimeError((work/'qemu.log').read_text())
        try:
            sock.connect(str(qmp))
            break
        except (FileNotFoundError, ConnectionRefusedError):
            time.sleep(.1)
    else:
        raise RuntimeError('QEMU monitor did not become ready.')
    stream = sock.makefile('rwb',buffering=0)
    stream.readline()
    def command(name, arguments=None):
        request = {'execute':name}
        if arguments: request['arguments'] = arguments
        stream.write(json.dumps(request).encode()+b'\n')
        while True:
            response = json.loads(stream.readline())
            if 'error' in response: raise RuntimeError(response)
            if 'return' in response: return response['return']
    def screen(name=None):
        path = work/'capture.ppm'
        command('screendump',{'filename':str(path)})
        with Image.open(path) as im: frame=np.asarray(im.convert('RGB')).copy()
        if name: Image.fromarray(frame).save(work/(name+'.png'))
        return frame
    def key(name, delay=.6):
        command('send-key',{'keys':[{'type':'qcode','data':name}],'hold-time':40})
        if delay: time.sleep(delay)
    def wait_log(marker, seconds=30):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if marker in serial.read_text(errors='replace'): return
            if vm.poll() is not None: break
            time.sleep(.1)
        raise RuntimeError(f'Missing {marker}: {serial.read_text(errors="replace")[-3000:]}')
    def check(name, condition):
        report['checks'][name]=bool(condition)
        if not condition: raise AssertionError(name)
    def region(frame,rect):
        x0,y0,x1,y1=rect
        return frame[int(y0*height):int(y1*height),int(x0*width):int(x1*width)]
    command('qmp_capabilities')
    wait_log('ERDTREE_MENU_READY')
    if args.autoboot:
        start=time.monotonic()
        wait_log('ERDTREE_LINUX_SELECTED',12)
        elapsed=time.monotonic()-start
        report['autoboot_seconds']=round(elapsed,3)
        check('countdown_and_confirmation_execute',2.5<elapsed<6)
    else:
        time.sleep(1)
        initial=screen('01-linux')
        check('resolution',initial.shape[:2]==(height,width))
        if args.variant == 'ring' and not args.stock:
            # Test the rendered text: it must stay above the contrast overlay
            # and each of the four labels must sit on the screen's centerline.
            menu=region(initial,(.35,.68,.65,.84))
            colors=[tuple(bytes.fromhex(VARIANTS['ring'][name][1:])) for name in ['text','selected']]
            gold=np.any([np.all(menu==color,axis=2) for color in colors],axis=0)
            check('gold_menu_text_is_unobscured',int(gold.sum())>width//4)
            occupied=np.flatnonzero(gold.sum(axis=1)>2)
            lines=np.split(occupied,np.flatnonzero(np.diff(occupied)>1)+1)
            centers=[]
            for line in lines:
                if len(line)<3: continue
                xs=np.nonzero(gold[line])[1]
                centers.append(float((xs.min()+xs.max())/2 + int(.35*width)))
            report['menu_label_centers_px']=centers
            check('four_menu_labels_are_centered',len(centers)==4 and
                  all(abs(center-width/2)<max(4,width*.003) for center in centers))
        time.sleep(.65)
        idle=screen('01-ambient')
        if ambient:
            check('ambient_animates_scene',not np.array_equal(region(initial,scene_rect),region(idle,scene_rect)))
            check('ambient_keeps_title_and_menu_still',np.array_equal(region(initial,menu_rect),region(idle,menu_rect)))
            delta=np.abs(region(initial,scene_rect).astype(float)-region(idle,scene_rect).astype(float))
            report['ambient_mean_pixel_delta']=round(float(delta.mean()),3)
            check('ambient_is_subtle',.02<float(delta.mean())<8)
            if args.variant == 'grace':
                # Observe a full wave. Bright flame pixels must travel both ways,
                # while the central stone mound remains anchored pixel-for-pixel.
                centers=[]
                for _ in range(25):
                    frame=screen()
                    flame=region(frame,(.64,.12,.85,.55))
                    bright=(flame[:,:,0]>230)&(flame[:,:,1]>210)&(flame[:,:,2]>140)
                    check('grace_flame_visible',int(bright.sum())>width)
                    centers.append(float(np.nonzero(bright)[1].mean()))
                    check('grace_mound_stays_anchored',np.array_equal(
                        region(initial,(.70,.69,.80,.79)),region(frame,(.70,.69,.80,.79))))
                    check('menu_stays_still_through_wave',np.array_equal(
                        region(initial,menu_rect),region(frame,menu_rect)))
                    time.sleep(.25)
                report['flame_horizontal_travel_px']=round(max(centers)-min(centers),2)
                steps=np.diff(centers)
                check('grace_waves_left_and_right',max(centers)-min(centers)>width*.018 and
                      int((steps>.5).sum())>=3 and int((steps<-.5).sum())>=3)
            else:
                samples=[]
                particles=[]
                outside=None
                if args.variant == 'ring':
                    outside=np.ones(initial.shape[:2],dtype=bool)
                    outside[int(.205*height):int(.67*height),int(.27*width):int(.73*width)]=False
                for _ in range(16):
                    frame=screen()
                    check('menu_stays_still_through_scene',np.array_equal(
                        region(initial,menu_rect),region(frame,menu_rect)))
                    if outside is not None:
                        check('only_sigil_region_glows',np.array_equal(initial[outside],frame[outside]))
                        # These side strips contain dust but no animated bloom.
                        particles.append(np.concatenate([region(frame,(.27,.22,.32,.65)),
                                                         region(frame,(.68,.22,.73,.65))],axis=1))
                    samples.append(region(frame,scene_rect))
                    time.sleep(.3)
                changed=sum(not np.array_equal(a,b) for a,b in zip(samples,samples[1:]))
                report['scene_motion_frames']=changed
                check('scene_has_continuous_motion',changed>=10)
                if args.variant == 'ring':
                    particle_motion=[int((np.abs(a.astype(int)-b.astype(int)).max(axis=2)>12).sum())
                                     for a,b in zip(particles,particles[1:])]
                    report['particle_motion_pixels']=particle_motion
                    check('gold_dust_flows_beyond_sigil',sum(count>8 for count in particle_motion)>=8)
                    brightness=[float(frame.mean()) for frame in samples]
                    report['sigil_glow_brightness_range']=[round(min(brightness),3),round(max(brightness),3)]
                    changes=np.diff(brightness)
                    check('sigil_glow_brightens_and_settles',max(brightness)-min(brightness)>1 and
                          bool((changes>.1).any()) and bool((changes<-.1).any()))
        else:
            check('entire_scene_still_when_idle',np.array_equal(initial,idle))
        key('down',0)
        frames=[]
        for _ in range(12):
            time.sleep(.035)
            frames.append(screen())
        selected=screen('02-windows')
        check('selection_changes',not np.array_equal(region(initial,menu_rect),region(selected,menu_rect)))
        if not ambient:
            check('scene_stays_identical_during_selection',all(np.array_equal(
                region(initial,scene_rect),region(f,scene_rect)) for f in frames))
        else:
            check('title_stays_identical_during_selection',all(np.array_equal(
                region(initial,title_rect),region(f,title_rect)) for f in frames))
        if not args.static:
            pulse_frames=[region(f,pulse_rect) for f in frames]
            check('selection_shimmer_has_multiple_frames',sum(not np.array_equal(
                pulse_frames[i],pulse_frames[i+1]) for i in range(len(pulse_frames)-1))>=3)
        time.sleep(.5)
        settled=screen()
        time.sleep(.5)
        check('selection_settles_completely',np.array_equal(region(settled,menu_rect),region(screen(),menu_rect)))
        if not args.static:
            key('ret',0)
            confirmation=[]
            start=time.monotonic()
            while time.monotonic()-start<1.05:
                confirmation.append(screen())
                time.sleep(.025)
            brightness=[float(region(f,(.55,.05,.98,.9)).mean()) for f in confirmation]
            report['confirmation_scene_brightness_range']=[round(min(brightness),3),round(max(brightness),3)]
            check('confirmation_fades_scene',min(brightness)<brightness[0]*.15)
            Image.fromarray(confirmation[len(confirmation)//2]).save(work/'03-confirm-fade.png')
            wait_log('ERDTREE_WINDOWS_SELECTED',5)
            check('windows_test_action_runs',True)
            time.sleep(2)
        key('home'); key('down'); key('down'); key('ret')
        screen('04-submenu')
        wait_log('Linux (recovery)',5)
        check('submenu_opens',True)
        key('esc'); key('e')
        wait_log('Minimum Emacs',5)
        check('entry_editor_opens',True)
        key('esc'); key('c')
        wait_log('Minimal BASH',5)
        check('console_opens',True)
        key('esc'); key('home')
        time.sleep(.5)
        after=screen('05-returned')
        time.sleep(.5)
        returned=screen()
        check('menu_still_after_return',np.array_equal(region(after,menu_rect),region(returned,menu_rect)))
        if ambient:
            check('ambient_resumes_after_return',not np.array_equal(region(after,scene_rect),region(returned,scene_rect)))
        key('down',.06); key('down',.06); key('up',.6)
        check('rapid_input_selects_windows',np.array_equal(region(selected,menu_rect),region(screen(),menu_rect)))
        key('home')
        if args.record:
            video=work/'erdtree-menu-preview.mp4'
            fps=30
            encoder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y',
                '-f','rawvideo','-pixel_format','rgb24','-video_size',f'{width}x{height}',
                '-framerate',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast',
                '-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE)
            events={45:'down',87:'down',129:'down',171:'up',213:'up',261:'ret'}
            start=time.monotonic()
            for frame_number in range(285):
                pause=start+frame_number/fps-time.monotonic()
                if pause>0: time.sleep(pause)
                if frame_number in events: key(events[frame_number],0)
                encoder.stdin.write(screen().tobytes())
            encoder.stdin.close()
            if encoder.wait(timeout=30): raise RuntimeError('Video encoding failed')
            report['recording_wall_seconds']=round(time.monotonic()-start,3)
            report['video']=str(video)
            encoder=None
            time.sleep(2)
        key('home'); key('ret',2)
        wait_log('ERDTREE_LINUX_SELECTED',5)
        check('linux_test_action_runs',True)
    check('no_grub_errors','error:' not in serial.read_text(errors='replace').lower())
    report['passed']=True
finally:
    if encoder is not None and encoder.poll() is None:
        encoder.kill()
        encoder.wait(timeout=5)
    if vm.poll() is None:
        vm.terminate()
        vm.wait(timeout=10)
    (work/'validation.json').write_text(json.dumps(report,indent=2))
    (work/'capture.ppm').unlink(missing_ok=True)
print(json.dumps(report,indent=2),flush=True)
