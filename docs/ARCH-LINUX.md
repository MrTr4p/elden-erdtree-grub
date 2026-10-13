# Arch Linux: install and try the Ring theme

Use a current checkout of `main`; v0.1.0 does not contain this design. These commands assume an existing working GRUB installation, usually with `/boot/grub/grub.cfg`. They do not migrate systemd-boot or another bootloader to GRUB.

## Static theme with your existing GRUB

```sh
sudo pacman -Syu --needed git python python-pillow grub
git clone https://github.com/MrTr4p/elden-erdtree-grub.git
cd elden-erdtree-grub
./install.sh --variant ring --dry-run
sudo ./install.sh --variant ring
```

Reboot when convenient. This installs the artwork and gold menu styling. Stock GRUB retains left-aligned labels inside the centered menu area; the animated build below supplies centered uppercase text and native effects.

For another supported mode, add `--resolution 2560x1440` to both installer commands. To list modes, press `c` in your current GRUB menu, run `videoinfo`, and press Escape to return. If `/boot` is a separate filesystem, mount it before installing.

Backups are in `/var/lib/elden-erdtree-grub`, accessible only to root. Installation regenerates your existing menu and retains entries discovered by your GRUB scripts. It does not create Windows entries that were already missing. [INSTALL.md](INSTALL.md) covers recovery and custom paths.

To update an existing installation:

```sh
sudo ./install.sh --uninstall
git pull --ff-only
./install.sh --variant ring --dry-run
sudo ./install.sh --variant ring
```

To remove the theme without reinstalling, run only the uninstall command. The installer refuses to overwrite an existing installation.

## Full animation in a VM

```sh
sudo pacman -Syu --needed base-devel curl freetype2 python-pillow python-numpy \
  grub qemu-system-x86 edk2-ovmf xorriso mtools dosfstools ffmpeg
./build.sh
python3 preview.py --variant ring --record
python3 live-preview.py --variant ring --port 8134
```

Build as your normal user. Outputs go into this checkout's `vendor`, `build`, `prefix`, `dist`, and `previews` directories. Nothing is installed into your real `/boot` or firmware. Tests print `"passed": true` on success; the viewer prints a localhost URL and opens it in your browser.

The VM attaches only its generated demo image, with no host disks or network. Use Up/Down, Enter, and Escape. Demo actions print markers. KVM is recommended; slower emulation may not satisfy animation timing checks.

## Animation at real boot

First check [ANIMATED-EFI.md](ANIMATED-EFI.md): x86_64 UEFI, a simple unencrypted configuration filesystem, and an unsigned custom executable. Keep your original firmware entry available. Secure Boot, encrypted `/boot`, and saved-default workflows require additional work and are outside the tested path.

Test a standalone image:

```sh
python3 preview.py --variant ring --standalone
```

Then collect your own existing configuration and build an image for it:

```sh
ERDTREE_CFG=/boot/grub/grub.cfg
ERDTREE_UUID=$(sudo grub-probe --target=fs_uuid "$ERDTREE_CFG")
ERDTREE_PATH=$(sudo grub-mkrelpath "$ERDTREE_CFG")
mkdir -p dist
sudo cat "$ERDTREE_CFG" > dist/host-grub.cfg
python3 make-efi.py --variant ring \
  --config dist/host-grub.cfg \
  --fs-uuid "$ERDTREE_UUID" --config-path "$ERDTREE_PATH" \
  --output dist/erdtree-ring-x86_64.efi
```

This only creates a file. Follow [the separate firmware-entry steps](ANIMATED-EFI.md#3-add-a-separate-firmware-entry) using your actual EFI partition, disk, and partition number. Do not copy the example disk identifiers. The static theme need not be installed first.

The image reads your existing menu at boot, so menu regeneration updates its OS entries. Rebuild the EFI image for theme or animation changes. The package manager does not update this custom executable.

## What was checked

- Clean Arch container: distribution font tools and menu generator, five variants, a second Ring resolution, install/uninstall, preserved entries/settings, overwrite refusal, and failed-generation rollback. Device discovery is a fixture for Docker's overlay filesystem.
- QEMU/OVMF: stock theme and standalone animated EFI, including interactions, glow, and particles.
- These checks do not validate physical firmware, actual Linux/Windows boot, or Secure Boot signing. Keep a working recovery boot path on your own machine.

Sources: [Arch GRUB documentation](https://wiki.archlinux.org/title/GRUB), [Arch QEMU package](https://archlinux.org/packages/extra/x86_64/qemu-system-x86/), and [GNU GRUB manual](https://www.gnu.org/software/grub/manual/grub/grub.html).
