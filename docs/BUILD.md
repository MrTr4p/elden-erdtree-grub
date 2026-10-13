# Reproduce the build and preview

Build on x86_64 Linux. The scripts keep downloads in `vendor/`, compile into `build/`, and install build outputs into the repository's private `prefix/`. Run the build as your regular user.

## Dependencies

Arch:

```sh
sudo pacman -S --needed base-devel curl bison flex gettext freetype2 python-pillow python-numpy grub qemu-system-x86 edk2-ovmf xorriso mtools dosfstools ffmpeg
```

Debian / Ubuntu:

```sh
sudo apt update
sudo apt install build-essential curl bison flex gettext pkg-config libfreetype6-dev python3-pil python3-numpy grub-common grub-efi-amd64-bin qemu-system-x86 ovmf xorriso mtools dosfstools ffmpeg
```

These are native Linux builds; WSL and cross-compilation are not verified. KVM acceleration is used when `/dev/kvm` is accessible. Otherwise the preview uses TCG, which is slower and may fail timing-sensitive animation assertions. Use `QEMU_ACCEL=tcg` to choose it explicitly.

## Download, patch, compile

```sh
./build.sh
```

The script downloads [GNU GRUB 2.14](https://ftp.gnu.org/gnu/grub/grub-2.14.tar.xz), verifies the SHA-256, applies `patch-source.py`, and builds all x86_64 EFI modules together.

Pinned archive SHA-256:

```text
bc8d3c73535b8838d8c8e2654d73edc4e6ae8c8acdb45d5df5dc9a1547446d43
```

Configuration flags:

```text
--target=x86_64 --with-platform=efi
--prefix=<repository>/prefix
--disable-werror --disable-nls --disable-grub-mount
--disable-device-mapper --disable-liblzma --disable-libzfs
```

Use `JOBS=8 ./build.sh` to change compilation parallelism. Build logs are `build.log`, `build/configure.log`, and `install-build.log`. GNU tools in `prefix/bin/` are private copies; the script does not install to `/usr`, `/boot`, the ESP, or firmware.

The complete diff is [grub-2.14-erdtree-interactions.patch](../patches/grub-2.14-erdtree-interactions.patch). To apply it manually to a fresh GRUB 2.14 source tree:

```sh
patch -p1 < /path/to/elden-erdtree-grub/patches/grub-2.14-erdtree-interactions.patch
```

Do not apply the manual diff and then run the scripted patcher on the same source tree. Do not mix patched `normal.mod` or `gfxmenu.mod` with stock modules: this patch changes the menu viewer interface.

## Artwork, fonts, layout

```sh
python3 build-theme.py --resolution 1920x1080
# Or create a separate output:
python3 build-theme.py --resolution 1024x768 --output dist/theme-1024
```

This copies the existing background unchanged, generates PF2 fonts from the bundled EB Garamond, writes small UI pixmaps, and creates `theme.txt`. It does not call an image-generation service. The font is renamed to Erdtree in PF2 metadata.

The image generation step itself is not deterministic. [ARTWORK.md](ARTWORK.md) records the editing prompt; the exact approved pixels are checked into the repository.

The menu begins at 4% left / 46% top, with width 43% and height 35%. Font sizes and row spacing scale with the requested resolution. The scene is stretched to the actual firmware mode.

## Native effects

- `erdtree_highlight.h`: a matte gold highlight with a sweep lasting 360 ms, triggered by a selection change.
- `erdtree_view.h`: redraws the menu at roughly 25 ms intervals only while the transition is active. Confirmation flashes for 170 ms and fades over the next 680 ms; submenus get only the flash.
- The animation is enabled by `set erdtree_motion=1` and `export erdtree_motion` in the GRUB configuration.
- Set `erdtree_motion=0` to use the ordinary theme's highlight.
- The background remains unchanged during selection. The whole screen darkens only during confirmation.
- Confirmation temporarily delays executing the selected entry by about 850 ms.
- Full-screen effects fall back to normal confirmation above 2560×1600 or if allocation fails. The theme builder accepts larger static layouts.

## Automated VM checks and recording

```sh
python3 preview.py --record
python3 preview.py --resolution 1024x768
python3 preview.py --static
python3 preview.py --autoboot
python3 preview.py --stock
python3 preview.py --standalone
python3 -m unittest discover -s tests -v
```

The first command creates `previews/1920x1080/preview.iso`, screenshots, `validation.json`, and `erdtree-menu-preview.mp4`. Other runs use separate subdirectories.

`--stock` tests the standard theme with system tools at `/usr/bin/grub-*` and `/usr/lib/grub/x86_64-efi`; systems using other tool names/locations need a local adjustment.

`--standalone` runs `make-efi.py` against a disposable test configuration and boots its result from a 64 MiB FAT image. The FAT image is used with temporary QEMU snapshot writes; no host partitions are attached.

The tests check idle stability, menu selection, multiple shimmer frames, unchanged tree pixels during selection, fade, submenu, editor, console, rapid input, and test-action execution. The entries only print markers. Real kernel boot, Windows chainloading, Secure Boot, and physical hardware are outside these tests.

## Interactive preview

After the default preview has built its ISO:

```sh
python3 live-preview.py
```

This starts QEMU and opens a local browser viewer on an available port. Use arrow keys, Enter, and Escape, or the on-screen controls. Stop it with Ctrl+C. To print the URL without opening a browser, add `--no-open`; use `--port 8129` to select a port.

The viewer binds only to `127.0.0.1` and uses a fresh access token. Its local URL file is ignored by Git.

Firmware is detected from common Arch, Debian/Ubuntu, and Fedora locations. For another layout, set `OVMF_CODE=/path/to/OVMF_CODE.fd` and `OVMF_VARS=/path/to/matching/OVMF_VARS.fd`. The variables template is copied before use. A combined `OVMF.4m.fd` also works through `OVMF_CODE`. Optional `GRUB_PREVIEW_TOOLS=/path/to/extracted/usr` supports an isolated QEMU/xorriso bundle.
