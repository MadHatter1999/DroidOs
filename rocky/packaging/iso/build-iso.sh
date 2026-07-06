#!/bin/sh
# Build a bootable Debian live ISO with Rocky preinstalled.
#
# Run on a Debian host as root (live-build writes to loop devices):
#   sudo apt install live-build
#   cd rocky/packaging/iso && sudo ./build-iso.sh
#
# Output: live-image-amd64.hybrid.iso in this directory. Burn it with the steps in
# ../BURNING.md. Boot it to get a live Debian session where 'rockyctl' is on PATH.
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
DEB_DIR="$HERE/../deb"
WORK="$HERE/live"
DISTRO="${DISTRO:-bookworm}"
ARCH="${ARCH:-amd64}"

command -v lb >/dev/null 2>&1 || { echo "install live-build: apt install live-build"; exit 1; }

# 1. Build the rocky .deb.
( cd "$DEB_DIR" && sh ./build-deb.sh )
DEB_FILE="$(ls "$DEB_DIR"/rocky_*_all.deb | head -n1)"

# 2. Configure a minimal live image.
rm -rf "$WORK"
mkdir -p "$WORK"
cd "$WORK"
lb config \
    --distribution "$DISTRO" \
    --architectures "$ARCH" \
    --debian-installer none \
    --archive-areas "main contrib non-free non-free-firmware" \
    --iso-application "Rocky Debian" \
    --iso-volume "rocky-$DISTRO"

# 3. Install python and drop the rocky .deb into the image.
mkdir -p config/package-lists config/packages.chroot
printf '%s\n' python3 python3-yaml sqlite3 > config/package-lists/rocky.list.chroot
cp "$DEB_FILE" config/packages.chroot/

# 4. Build. Produces live-image-amd64.hybrid.iso.
lb build

ISO="$(ls "$WORK"/*.iso | head -n1)"
cp "$ISO" "$HERE/"
echo "built $HERE/$(basename "$ISO")"
