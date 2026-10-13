# Experimental animated EFI installation

The standard installer cannot enable animations. This guide builds a separate, self-contained x86_64 UEFI executable using the patched GRUB 2.14 modules.

**Status:** validated in QEMU/OVMF with a disposable configuration. Physical-machine Linux boot and Windows chainloading have not been validated. This route is intended for users who can select their existing bootloader from the firmware menu.

## Supported scope

Use this only with a simple, unencrypted filesystem containing a full GRUB configuration and an x86_64 UEFI system. Your normal bootloader remains available.

This guide does not support:

- Secure Boot with the unsigned output produced here. Use the standard theme with your distribution's signed GRUB, or supply your own complete signing/trust setup.
- Legacy BIOS or ARM firmware.
- Encrypted /boot, Fedora BLS/`blscfg` configurations, or distribution-specific GRUB modules.
- Configurations that reassign `prefix` or hand off through `configfile`/`normal`.
- Saved-default, next-entry, record-failure, or custom scripts that rely on writing `$prefix/grubenv`. In this image, `prefix` points to embedded modules.
- Automatic updating of the custom GRUB executable when your distribution updates GRUB.

The generator rejects obvious forwarding stubs, but it is not a complete configuration auditor. Inspect any sourced custom configuration and modules. Keep the original boot entry.

## 1. Build and test without installing

Install the dependencies in [BUILD.md](BUILD.md), then:

```sh
./build.sh
python3 preview.py --standalone
```

A successful run prints `"passed": true`. This exercises a separate FAT image in QEMU and does not attach your disks.

## 2. Locate your full configuration

On Arch/Debian/Ubuntu this is usually `/boot/grub/grub.cfg`. Other systems may use `/boot/grub2/grub.cfg`. An EFI forwarding stub is not suitable.

The EFI generator needs the filesystem UUID and the path *inside that filesystem*. This differs when /boot is a separate partition. Let GRUB's tools calculate both.

Example for systems with `grub-*` tool names:

```sh
ERDTREE_CFG=/boot/grub/grub.cfg
ERDTREE_UUID=$(sudo grub-probe --target=fs_uuid "$ERDTREE_CFG")
ERDTREE_PATH=$(sudo grub-mkrelpath "$ERDTREE_CFG")
mkdir -p dist
sudo cat "$ERDTREE_CFG" > dist/host-grub.cfg

python3 make-efi.py \
  --config dist/host-grub.cfg \
  --fs-uuid "$ERDTREE_UUID" \
  --config-path "$ERDTREE_PATH" \
  --output dist/erdtree-x86_64.efi
```

Use the corresponding `grub2-probe`/`grub2-mkrelpath` names where needed. The standard theme installer is not a prerequisite; the EFI file embeds its own theme and fonts.

The source configuration is inspected but not changed. The EFI file embeds only a small loader and theme; at boot it finds the filesystem by UUID and sources your existing menu. Regenerating that existing menu therefore updates its entries. The local configuration copy and generated EFI file stay in ignored `dist/`; do not publish machine-specific configuration.

For another resolution, generate a separate theme and pass matching flags:

```sh
python3 build-theme.py --resolution 1024x768 --output dist/theme-1024
python3 make-efi.py --config dist/host-grub.cfg \
  --fs-uuid "$ERDTREE_UUID" --config-path "$ERDTREE_PATH" \
  --theme-dir dist/theme-1024 --resolution 1024x768 \
  --output dist/erdtree-x86_64.efi
```

## 3. Add a separate firmware entry

The following commands are **examples requiring your actual ESP mount, disk, and partition number**. Do not paste the example disk identifiers without checking them.

Inspect the existing layout:

```sh
findmnt /boot /boot/efi /efi
lsblk -o NAME,FSTYPE,UUID,PARTTYPENAME,MOUNTPOINTS
sudo efibootmgr -v
```

For example, if the mounted ESP is `/boot/efi`, on partition 1 of `/dev/nvme0n1`:

```sh
sudo install -d /boot/efi/EFI/Erdtree
sudo install -m 0644 dist/erdtree-x86_64.efi /boot/efi/EFI/Erdtree/grubx64.efi
sudo efibootmgr --create-only --disk /dev/nvme0n1 --part 1 \
  --label "Erdtree Preview" --loader '\EFI\Erdtree\grubx64.efi'
sudo efibootmgr -v
```

Use a new, empty `EFI/Erdtree` directory. Do not overwrite an existing entry's executable. `--create-only` registers the new entry without inserting it into the permanent BootOrder.

Test it once using the firmware's boot picker. Alternatively, use `sudo efibootmgr --bootnext XXXX`, replacing `XXXX` with the new Erdtree entry number shown by `efibootmgr`. This selects it for the next boot only.

After verifying your real OS entries boot, you can choose whether to make the entry permanent through your firmware settings. This project does not change your BootOrder automatically.

## 4. Return to your original bootloader

Select your original Linux/Windows entry in the firmware boot menu.

To remove the experimental entry, use `sudo efibootmgr --bootnum XXXX --delete-bootnum` with its exact entry number, then remove only the file and directory you created:

```sh
sudo rm /boot/efi/EFI/Erdtree/grubx64.efi
sudo rmdir /boot/efi/EFI/Erdtree
```

Use your actual ESP mount path. Do not remove any distribution or Microsoft directory.

## Maintenance and internals

The executable includes all of its matching GRUB modules. Never copy patched modules into your distribution's module directory. Rebuild the EFI image to update the embedded theme or native code.

The loader uses `source` to retain the current menu context and reapplies the embedded theme afterwards. It keeps the module prefix on its own memdisk. That isolation is why environment-block and distribution-specific workflows listed above require additional engineering.

References: [GRUB prefix](https://www.gnu.org/software/grub/manual/grub/html_node/prefix.html), [GRUB source](https://www.gnu.org/software/grub/manual/grub/html_node/source.html), [efibootmgr upstream](https://github.com/rhboot/efibootmgr).
