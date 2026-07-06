#!/bin/sh
# DroidOS image build wrapper (spec §6, §35).
#
# This documents and drives the Yocto build. It is NOT runnable in this reference
# checkout, it requires a Yocto build host, the pinned upstream layers (poky,
# meta-openembedded, meta-ros) and, for Jetson, the vendor BSP. Pin exact release
# tags / commit hashes in your build manifest (spec §6).
set -eu

MACHINE="${1:-droidos-rpi5}"          # droidos-rpi5 | droidos-orin | qemuarm64
IMAGE="${2:-droidos-image}"
YOCTO_RELEASE="scarthgap"

echo "DroidOS build: MACHINE=$MACHINE IMAGE=$IMAGE (Yocto $YOCTO_RELEASE)"

# 1. Fetch pinned layers (once):
#    git clone -b $YOCTO_RELEASE https://git.yoctoproject.org/poky
#    git clone -b $YOCTO_RELEASE https://github.com/openembedded/meta-openembedded
#    git clone -b <pinned> https://github.com/ros/meta-ros
#
# 2. Initialise the build environment:
#    . poky/oe-init-build-env build
#
# 3. Add layers:
#    bitbake-layers add-layer ../meta-openembedded/meta-oe
#    bitbake-layers add-layer ../meta-ros/meta-ros2-lyrical
#    bitbake-layers add-layer ../meta-droidos
#    bitbake-layers add-layer ../meta-droidos-rpi      # or ../meta-droidos-tegra
#
# 4. Select the distro + machine in conf/local.conf:
#    DISTRO = "droidos"
#    MACHINE = "$MACHINE"
#
# 5. Build:
echo "Would run: MACHINE=$MACHINE bitbake $IMAGE"
# bitbake "$IMAGE"

echo "Outputs (spec §35): *.wic / *.img plus the signed *.raucb update bundle."
