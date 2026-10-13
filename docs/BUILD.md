# Reproduce the build and preview

Build on x86_64 Linux. The scripts keep downloads in `vendor/`, compile into `build/`, and install build outputs into the repository's private `prefix/`. Run the build as your regular user.

## Dependencies

Arch:

```sh
sudo pacman -Syu --needed base-devel curl bison flex gettext freetype2 python-pillow python-numpy grub qemu-system-x86 edk2-ovmf xorriso mtools dosfstools ffmpeg
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
- `erdtree_ambient.h`: a 5.6-second left/right flame sway, a smaller 2.7-second travelling ripple, soft breathing light, three light accents circling the grace ring in 11 seconds, and 18 rising motes. The flame's deformation tapers toward its root, leaving the mound anchored. Horizontal sampling and the sine table are interpolated for smooth motion. It reuses one bitmap and a small precomputed mask, with no allocation or disk I/O inside a frame.
- `erdtree_view.h`: schedules the scene at 50 ms intervals and selection transitions at 25 ms intervals. Idle redraws are restricted to the right half; the title and menu remain still. Slow renderers automatically reduce the scene frame rate. Confirmation flashes for 170 ms and fades over the next 680 ms; submenus get only the flash.
- The animation is enabled by `set erdtree_motion=1` and `export erdtree_motion` in the GRUB configuration.
- Set `erdtree_motion=0` to use the ordinary theme's highlight.
- Set `erdtree_ambient=0` and `export erdtree_ambient` to retain selection and confirmation effects with a still background.
- Ambient rendering falls back to the original artwork above 2560×1600, for unsupported bitmap formats, or if allocation fails. It releases its frame when the view is destroyed.
- The whole screen darkens only during confirmation.
- Confirmation temporarily delays executing the selected entry by about 850 ms.
- Full-screen effects fall back to normal confirmation above 2560×1600 or if allocation fails. The theme builder accepts larger static layouts.

## Automated VM checks and recording

```sh
python3 preview.py --record
python3 preview.py --resolution 1024x768
python3 preview.py --static
python3 preview.py --no-ambient
python3 preview.py --autoboot
python3 preview.py --stock
python3 preview.py --standalone
python3 -m unittest discover -s tests -v
```

The first command creates `previews/1920x1080/preview.iso`, screenshots, `validation.json`, and `erdtree-menu-preview.mp4`. Other runs use separate subdirectories.

`--stock` tests the standard theme with system tools at `/usr/bin/grub-*` and `/usr/lib/grub/x86_64-efi`; systems using other tool names/locations need a local adjustment.

`--standalone` runs `make-efi.py` against a disposable test configuration and boots its result from a 64 MiB FAT image. The FAT image is used with temporary QEMU snapshot writes; no host partitions are attached.

The tests check a full flame cycle for horizontal travel in both directions, an anchored mound, subtle pixel changes, still title/menu pixels, multiple selection shimmer frames, fade, submenu, editor, console, rapid input, and test-action execution. Static and selection-only modes also check unchanged idle artwork. The entries only print markers. Real kernel boot, Windows chainloading, Secure Boot, and physical hardware are outside these tests.

## Interactive preview

After the default preview has built its ISO:

```sh
python3 live-preview.py
```

This starts QEMU and opens a local browser viewer on an available port. Use arrow keys, Enter, and Escape, or the on-screen controls. Stop it with Ctrl+C. To print the URL without opening a browser, add `--no-open`; use `--port 8129` to select a port.

The viewer has pause/resume and fullscreen controls. Pausing freezes the browser feed; navigation refreshes the still image while GRUB continues running. Reduced-motion preferences start the feed paused. The browser pauses frame requests while its tab is hidden. Edit `viewer.html` and reload to change the viewer; edit the native headers, rebuild, regenerate the ISO and restart the viewer to change GRUB effects.

To compare a still scene with selection animations, build with `python3 preview.py --no-ambient` and launch with `python3 live-preview.py --no-ambient`. Use `--static` on both commands for the static theme.

The viewer binds only to `127.0.0.1` and uses a local access token. Its owner-only URL file is ignored by Git; the token is reused on restart so the same localhost link keeps working when a fixed port is used. Delete that file to generate a new token.

With the viewer running and Playwright available on Node's module search path, `node tests/test_browser.cjs` checks keyboard/button input, pause/resume, fullscreen, access-token enforcement, mobile layout and reduced-motion preferences. Pass a variant name, such as `node tests/test_browser.cjs carian`, to test that viewer. Set `CHROMIUM_PATH` if Chromium is not at `/usr/bin/chromium`. Screenshots and validation are saved under `previews/browser-<variant>/`.

## Compare alternate concepts

The `carian`, `destined` and `farum` variants use separate generated backgrounds, native menu palettes, and native scene effects. Their assets and exact image-generation prompts are in `concepts/`. `grace` remains the default.

```sh
python3 preview.py --variant carian
python3 preview.py --variant destined
python3 preview.py --variant farum
python3 preview-concepts.py
```

The launcher runs Age of the Stars on port 8131, Destined Death on 8132, and Beyond Time on 8133, each in its own diskless QEMU VM. It leaves an existing Grace viewer alone. Use `--no-open` to avoid opening browser tabs, or `--port 8141` to use another consecutive group. Ctrl+C stops the three child previews. Each concept has its own ignored `live-preview-<variant>-url.txt`, so ports and access tokens do not overwrite one another.

For one concept, run `python3 live-preview.py --variant carian --port 8131`. To build only its theme files, run `python3 build-theme.py --variant carian --output dist/theme-carian`. The standard installer still uses the default Grace theme.

The native renderer chooses a scene using the exported `erdtree_variant` variable. Carian has breathing blue light, twinkling stars and stardust. Destined Death has pulsing crimson fissures, rising embers and thin red energy coils. Farum Azula has windblown dust and a restrained, localized lightning pulse every 9.3 seconds. All preserve the title and menu pixels during idle animation and keep the existing keyboard/confirmation behavior.

The additional `ring` variant uses the user's original cover artwork with a centered title-screen menu below the sigil. Small uppercase gold serif text, a feathered horizontal selection glow, and a small chevron match the supplied menu reference. A soft transparent UI shade behind the text keeps it legible over the landscape; the original background file remains unchanged. Entry titles are centered and capitalized only when drawn, preserving the underlying names, actions, and hotkeys. Other variants retain their original menu layout.

`erdtree_ring.h` precomputes a small blurred light mask once. Its golden bloom breathes over 5.2 seconds while crossing waves travel along the existing luminous filaments at 3.6 and 4.4 seconds. Highlights roll off near white to preserve the sigil's detail. Thirty-eight golden motes rise from the ring and curl outward at different speeds, with soft halos, short trailing sparks, subpixel positions, and a fade before each loop. Idle animation is restricted to the sigil and surrounding dust field (27–73% across, 20.5–67% down), with no allocation inside a frame; the logo and menu stay still. The same centered layout and soft selection treatment are available with motion disabled.

```sh
python3 preview.py --variant ring
python3 live-preview.py --variant ring --port 8134
```

The three-concept launcher leaves this additional viewer alone. Each viewer can run simultaneously.

Firmware is detected from common Arch, Debian/Ubuntu, and Fedora locations. For another layout, set `OVMF_CODE=/path/to/OVMF_CODE.fd` and `OVMF_VARS=/path/to/matching/OVMF_VARS.fd`. The variables template is copied before use. A combined `OVMF.4m.fd` also works through `OVMF_CODE`. Optional `GRUB_PREVIEW_TOOLS=/path/to/extracted/usr` supports an isolated QEMU/xorriso bundle.
