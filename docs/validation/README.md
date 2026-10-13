# Recorded validation

## Current Ring design and Arch installation (2026-10-14)

`ring-particles-2026-10-14.json` records the current animated Ring menu at
1920×1080 and 1024×768, with browser interaction checks. The separate
`ring-standalone-2026-10-14.json` and `ring-stock-2026-10-14.json` cover the
standalone EFI builder and the ordinary static theme on stock GRUB.

`arch-installer-2026-10-14.json` records installation and uninstall in a clean
Arch container with real Arch menu-generation and font tools. Device probing
uses a fixture because Docker's overlay root is not a boot disk. It covers all
five variants, a second Ring resolution, preservation of entries/settings,
overwrite refusal, and rollback after failed menu generation. Thirteen unit
tests cover the installer and EFI loader. CI repeats these on each push.

The standalone VM's external configuration deliberately selects Grace; the
Ring EFI loader must restore its own variant after sourcing that configuration.
The generated images have no machine-specific host configuration in Git.

## Original release checks (2026-10-13)

These reports were generated on 2026-10-13 on x86_64 Arch Linux using QEMU,
OVMF, and KVM. GRUB was rebuilt from the pinned 2.14 source using this repository.
The stock-theme run used the system's unmodified GRUB 2.14.

Six VM runs passed: animated 1920x1080, animated 1024x768, effects disabled,
automatic selection, stock GRUB, and a standalone EFI image with a disposable
configuration. Installer recovery tests additionally passed all seven cases.

Image hashes identify those particular test builds. Timestamps and build paths
can change the binary hash on a later build; these are functional reproduction
instructions, not a guarantee of bit-identical binaries. The `iso_sha256` field
in the standalone report refers to its FAT disk image.

The tests run simulated menu actions. They do not boot Linux or Windows kernels,
verify real firmware, or test a Secure Boot signing setup.
