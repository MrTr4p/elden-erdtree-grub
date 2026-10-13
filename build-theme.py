#!/usr/bin/env python3
"""Generate native UI decorations without retouching the approved background."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
from PIL import Image, ImageDraw
BASE = Path(__file__).resolve().parent

def build_theme(dest, width=1920, height=1080):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    source = BASE / 'theme/background.png'
    if source.resolve() != (dest / 'background.png').resolve():
        shutil.copy2(source, dest / 'background.png')
    size = max(20, round(42 * width / 1920))
    small = max(13, round(20 * width / 1920))
    row = max(34, round(62 * height / 1080))
    spacing = max(9, round(21 * height / 1080))
    pad = max(16, round(30 * width / 1920))
    for name, fs in [('body', size), ('small', small)]:
        subprocess.run([os.environ.get('GRUB_MKFONT', 'grub-mkfont'), '-n', 'Erdtree', '-s', str(fs), '-r',
                        '0x20-0x7E,0x2190-0x2193', '-o', str(dest / (name + '.pf2')),
                        str(BASE / 'EBGaramond.ttf')], check=True)
    for style in ['normal', 'selected', 'terminal']:
        for part in ['nw','n','ne','w','c','e','sw','s','se']:
            dims = (pad,1) if part in ['w','e','nw','ne','sw','se'] else (1,1)
            im = Image.new('RGBA', dims)
            d = ImageDraw.Draw(im)
            if style == 'selected':
                d.rectangle((0,0,dims[0]-1,0), fill=(200,163,94,110 if part in ['n','s'] else 35))
            elif style == 'terminal':
                d.rectangle((0,0,dims[0]-1,0), fill=(8,9,8,248))
            im.save(dest / f'{style}_{part}.png')
    theme = f'''# Erdtree: static artwork, event-triggered native menu effects.
title-text: ""
desktop-image: "background.png"
desktop-image-scale-method: "stretch"
desktop-color: "#080908"
terminal-font: "Unifont Regular 16"
terminal-box: "terminal_*.png"
terminal-left: "6%"
terminal-top: "8%"
terminal-width: "88%"
terminal-height: "84%"
terminal-border: "12"
+ boot_menu {{
 left = 4% top = 46% width = 43% height = 35%
 item_font = "Erdtree Regular {size}"
 selected_item_font = "Erdtree Regular {size}"
 item_color = "#d3c3a1" selected_item_color = "#f8e7be"
 icon_width = 0 icon_height = 0 item_icon_space = 0
 item_height = {row} item_padding = 0 item_spacing = {spacing}
 item_pixmap_style = "normal_*.png"
 selected_item_pixmap_style = "selected_*.png"
 scrollbar = false
}}
+ label {{
 left = 6% top = 89% width = 40% height = 30
 text = "↑ ↓   SELECT       ENTER   BOOT"
 font = "Erdtree Regular {small}" color = "#bd9c61"
}}
+ label {{
 id = "__timeout__"
 left = 6% top = 93% width = 40% height = 30
 text = "Continuing in %d seconds"
 font = "Erdtree Regular {small}" color = "#bd9c61"
}}
'''
    (dest / 'theme.txt').write_text(theme)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resolution', default='1920x1080')
    parser.add_argument('--output', type=Path, default=BASE / 'theme')
    args = parser.parse_args()
    try:
        width, height = map(int, args.resolution.split('x'))
        if not (640 <= width <= 4096 and 480 <= height <= 2160):
            raise ValueError()
    except ValueError:
        parser.error('Use WIDTHxHEIGHT, between 640x480 and 4096x2160.')
    build_theme(args.output, width, height)
