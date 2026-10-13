# Standard theme installation

The normal installer only installs artwork, fonts, and theme configuration. It does not add native animations or run `grub-install`.

## Requirements

- Linux with working GRUB 2 and an existing full `grub.cfg`.
- Python 3.
- `grub-mkconfig` or `grub2-mkconfig`.
- For custom sizes: Pillow and `grub-mkfont` / `grub2-mkfont`.
- A firmware graphics mode compatible with the chosen size.

Default installation uses the checked-in fonts and images. It does not require a compiler, QEMU, or Pillow.

## Commands

```sh
git clone https://github.com/MrTr4p/elden-erdtree-grub.git
cd elden-erdtree-grub
./install.sh --dry-run
sudo ./install.sh
```

Use `--grub-dir /boot/grub2` on a system whose full configuration lives there. Do not point this at an ESP directory such as `/boot/efi/EFI/fedora`; that may contain a forwarding stub rather than the full configuration.

The installer regenerates the full menu at `GRUB_DIR/grub.cfg`. It inherits your distribution's installed GRUB scripts and OS discovery behavior.

## What changes

Theme directory: `GRUB_DIR/themes/elden-erdtree`.

Backup directory: `/var/lib/elden-erdtree-grub`, created with mode 0700. It contains `defaults.before`, `grub.cfg.before`, and an installation receipt.

A marked block at the end of `/etc/default/grub` sets `GRUB_THEME`, `GRUB_GFXMODE`, `GRUB_TERMINAL_OUTPUT=gfxterm`, and `GRUB_TIMEOUT_STYLE=menu`. It unsets the combined `GRUB_TERMINAL` override, retaining the separate input setting. An existing timeout of zero is raised to five seconds; other timeouts remain unchanged.

The installer refuses to overwrite an existing theme directory or installation receipt. A failed configuration generation restores the original defaults and generated menu.

## Remove or update

```sh
sudo ./install.sh --uninstall
git pull --ff-only
sudo ./install.sh
```

Uninstall keeps unrelated edits made to your defaults after installation. If regeneration fails during uninstall, the installed configuration is restored and the theme stays in place.

## Manual recovery

If the marked block was manually edited and uninstall refuses, first inspect the files in `/var/lib/elden-erdtree-grub`. To restore the exact pre-installation settings, copy `defaults.before` to `/etc/default/grub` and `grub.cfg.before` to the full GRUB configuration path recorded in `receipt.json`. This replaces settings changed since installation, so compare the files first. Once your original configuration is restored, remove only the `elden-erdtree` theme directory and its state directory.

## Appearance and missing entries

The image contains the title, subtitle, divider, and tree. Actual OS names, highlight, navigation help, and timeout text are rendered by GRUB.

The four short names in the preview are demonstration entries. Your real menu keeps your distribution's labels. Rename entries through your distribution's supported GRUB configuration mechanism; editing generated `grub.cfg` is overwritten on the next regeneration.

If Windows is absent before installation, this theme does not add it. If a long label is clipped, adjust `item_font` / `selected_item_font`, generate smaller fonts with `build-theme.py`, or shorten the label. More entries scroll within the menu, although the scrollbar is hidden.

For display modes, press `c` in GRUB and use `videoinfo`; press Escape to return. Build for a mode your firmware supports.

Reference: [GRUB simple configuration](https://www.gnu.org/software/grub/manual/grub/html_node/Simple-configuration.html).
