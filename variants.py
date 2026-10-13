"""Shared names and palettes for independent native GRUB previews."""
from pathlib import Path

BASE = Path(__file__).resolve().parent
VARIANTS = {
    'grace': dict(title='Site of Grace', subtitle='CHOOSE YOUR REALM',
                  accent='#c8a35e', text='#d3c3a1', selected='#f8e7be',
                  background='#080908', panel='#0d0e0b', hint='#bd9c61',
                  description='A swaying golden flame and circling grace'),
    'carian': dict(title='Age of the Stars', subtitle='AGE OF THE STARS',
                   accent='#82b8ee', text='#b7cbe1', selected='#e7f4ff',
                   background='#050910', panel='#0b111c', hint='#84a7cc',
                   description='Moonlight, blue stardust and a glintstone blade'),
    'destined': dict(title='Destined Death', subtitle='DESTINED DEATH',
                     accent='#cb4b55', text='#cfb9b6', selected='#ffe5de',
                     background='#0b0607', panel='#140b0e', hint='#bb7a7d',
                     description='An obsidian blade, breathing crimson runes and embers'),
    'farum': dict(title='Beyond Time', subtitle='BEYOND TIME',
                  accent='#c8b896', text='#cec7b6', selected='#fff3d7',
                  background='#090a0b', panel='#111212', hint='#afa58e',
                  description='Farum Azula ruins, windblown dust and distant lightning'),
    'ring': dict(title='The Shattered Ring', subtitle='CHOOSE YOUR REALM',
                 accent='#d3ab57', text='#c5b686', selected='#f2dfaa',
                 background='#03100d', panel='#071510', hint='#8c856e',
                 description='A centered title-screen menu with a glowing sigil and flowing golden dust'),
}


def background_path(variant):
    return BASE/'theme/background.png' if variant == 'grace' else BASE/'concepts'/variant/'background.png'


def preview_tag(resolution, variant='grace', suffix=''):
    return resolution + ('' if variant == 'grace' else '-' + variant) + suffix


def url_path(variant='grace'):
    return BASE/('live-preview-url.txt' if variant == 'grace' else f'live-preview-{variant}-url.txt')
