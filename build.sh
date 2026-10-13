#!/bin/sh
set -eu
cd "$(dirname "$0")"
base=$(pwd)
mkdir -p vendor build prefix dist patches
archive=vendor/grub-2.14.tar.xz
if [ ! -f "$archive" ]; then
  curl --fail --location --retry 2 https://ftp.gnu.org/gnu/grub/grub-2.14.tar.xz --output "$archive"
fi
printf '%s\n' 'bc8d3c73535b8838d8c8e2654d73edc4e6ae8c8acdb45d5df5dc9a1547446d43  vendor/grub-2.14.tar.xz' | sha256sum --check -
if [ ! -d vendor/grub-2.14 ]; then
  tar -xf "$archive" -C vendor
fi
python3 patch-source.py
if [ ! -f build/Makefile ]; then
  (cd build && ../vendor/grub-2.14/configure --target=x86_64 --with-platform=efi \
    --prefix="$base/prefix" --disable-werror --disable-nls --disable-grub-mount \
    --disable-device-mapper --disable-liblzma --disable-libzfs > configure.log 2>&1)
fi
make -C build -j"${JOBS:-4}" > build.log 2>&1
make -C build install > install-build.log 2>&1
for font in /usr/share/grub/unicode.pf2 /usr/share/grub2/unicode.pf2; do
  if [ -f "$font" ]; then
    cp "$font" prefix/share/grub/unicode.pf2
    break
  fi
done
printf '%s\n' 'Built private EFI GRUB modules. No installation to /boot or firmware.'
