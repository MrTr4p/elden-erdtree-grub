#!/usr/bin/env python3
"""Generate native UI decorations without retouching the approved background."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
from PIL import Image, ImageDraw
from variants import VARIANTS, background_path
BASE = Path(__file__).resolve().parent

def build_theme(dest, width=1920, height=1080, variant='grace'):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    palette = VARIANTS[variant]
    accent = tuple(bytes.fromhex(palette['accent'][1:]))
    source = background_path(variant)
    if source.resolve() != (dest / 'background.png').resolve():
        shutil.copy2(source, dest / 'background.png')
    size = max(20, round(42 * width / 1920))
    small = max(13, round(20 * width / 1920))
    row = max(34, round(62 * height / 1080))
    spacing = max(9, round(21 * height / 1080))
    pad = max(16, round(30 * width / 1920))
    menu_left, menu_top, menu_width, menu_height = 4, 46, 43, 35
    hint_left, hint_top, hint_width, timeout_top = 6, 89, 40, 93
    hint_align = 'left'
    backdrop, ornament = '', ''
    if variant == 'ring':
        size = max(14, round(26 * width / 1920))
        small = max(10, round(14 * width / 1920))
        row = max(size + 4, round(30 * height / 1080))
        spacing = max(5, round(12 * height / 1080))
        menu_left, menu_top, menu_width, menu_height = 35, 68, 30, 17
        hint_left, hint_top, hint_width, timeout_top = 25, 96, 50, 93
        hint_align = 'center'
        # Native UI overlays: a feathered shade for text contrast and a tiny
        # title-screen chevron. The supplied desktop image stays unchanged.
        shade = Image.new('RGBA', (256, 128))
        for y in range(128):
            for x in range(256):
                falloff = max(0, 1 - ((x-127.5)/127.5)**2 - ((y-63.5)/63.5)**2)
                shade.putpixel((x,y), (0, 3, 2, round(210*falloff**2)))
        shade.save(dest / 'menu-shade.png')
        chevron = Image.new('RGBA', (11, 6))
        ImageDraw.Draw(chevron).line((0,0,5,5,10,0), fill=(*accent,180))
        chevron.save(dest / 'menu-chevron.png')
        backdrop = '''+ image {
 left = 23% top = 60% width = 54% height = 30%
 file = "menu-shade.png"
}
'''
        chevron_width = max(7, round(11 * width / 1920))
        chevron_height = max(4, round(6 * height / 1080))
        ornament = f'''+ image {{
 left = 50%-{chevron_width//2} top = 84% width = {chevron_width} height = {chevron_height}
 file = "menu-chevron.png"
}}
'''
    for name, fs in [('body', size), ('small', small)]:
        subprocess.run([os.environ.get('GRUB_MKFONT', 'grub-mkfont'), '-n', 'Erdtree', '-s', str(fs), '-r',
                        '0x20-0x7E,0x2190-0x2193', '-o', str(dest / (name + '.pf2')),
                        str(BASE / 'EBGaramond.ttf')], check=True)
    for style in ['normal', 'selected', 'terminal']:
        for part in ['nw','n','ne','w','c','e','sw','s','se']:
            dims = (pad,1) if part in ['w','e','nw','ne','sw','se'] else (1,1)
            if variant == 'ring' and style == 'selected' and part == 'c':
                dims = (256, row)
            im = Image.new('RGBA', dims)
            d = ImageDraw.Draw(im)
            if style == 'selected':
                if variant == 'ring':
                    if part == 'c':
                        for y in range(row):
                            vertical = max(0, 1 - abs(2*y/(row-1) - 1)) ** 3
                            for x in range(256):
                                horizontal = (1 - abs(2*x/255 - 1)) ** 2
                                im.putpixel((x,y), (*accent, round(135*vertical*horizontal)))
                else:
                    d.rectangle((0,0,dims[0]-1,0), fill=(*accent,110 if part in ['n','s'] else 35))
            elif style == 'terminal':
                d.rectangle((0,0,dims[0]-1,0), fill=(8,9,8,248))
            im.save(dest / f'{style}_{part}.png')
    # GRUB canvases paint in reverse declaration order: put the shade last.
    theme = f'''# {palette['title']}: native GRUB menu and ambient scene.
title-text: ""
desktop-image: "background.png"
desktop-image-scale-method: "stretch"
desktop-color: "{palette['background']}"
terminal-font: "Unifont Regular 16"
terminal-box: "terminal_*.png"
terminal-left: "6%"
terminal-top: "8%"
terminal-width: "88%"
terminal-height: "84%"
terminal-border: "12"
+ boot_menu {{
 left = {menu_left}% top = {menu_top}% width = {menu_width}% height = {menu_height}%
 item_font = "Erdtree Regular {size}"
 selected_item_font = "Erdtree Regular {size}"
 item_color = "{palette['text']}" selected_item_color = "{palette['selected']}"
 icon_width = 0 icon_height = 0 item_icon_space = 0
 item_height = {row} item_padding = 0 item_spacing = {spacing}
 item_pixmap_style = "normal_*.png"
 selected_item_pixmap_style = "selected_*.png"
 scrollbar = false
}}
{ornament}
+ label {{
 left = {hint_left}% top = {hint_top}% width = {hint_width}% height = 30
 align = "{hint_align}"
 text = "↑ ↓   SELECT       ENTER   BOOT"
 font = "Erdtree Regular {small}" color = "{palette['hint']}"
}}
+ label {{
 id = "__timeout__"
 left = {hint_left}% top = {timeout_top}% width = {hint_width}% height = 30
 align = "{hint_align}"
 text = "Continuing in %d seconds"
 font = "Erdtree Regular {small}" color = "{palette['hint']}"
}}
{backdrop}
'''
    (dest / 'theme.txt').write_text(theme.rstrip()+'\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resolution', default='1920x1080')
    parser.add_argument('--output', type=Path, default=BASE / 'theme')
    parser.add_argument('--variant', choices=VARIANTS, default='grace')
    args = parser.parse_args()
    try:
        width, height = map(int, args.resolution.split('x'))
        if not (640 <= width <= 4096 and 480 <= height <= 2160):
            raise ValueError()
    except ValueError:
        parser.error('Use WIDTHxHEIGHT, between 640x480 and 4096x2160.')
    if args.variant != 'grace' and args.output.resolve() == (BASE/'theme').resolve():
        parser.error('Use --output to build a concept without overwriting the Grace theme.')
    build_theme(args.output, width, height, args.variant)
