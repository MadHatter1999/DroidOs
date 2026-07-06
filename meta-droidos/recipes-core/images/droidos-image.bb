SUMMARY = "DroidOS production image (spec §35)"
LICENSE = "Apache-2.0"

inherit core-image

# Read-only root filesystem with A/B update slots (spec §31, §33).
IMAGE_FEATURES += "read-only-rootfs ssh-server-openssh"
IMAGE_FSTYPES = "wic wic.bmap"

IMAGE_INSTALL:append = " \
    droidos-runtime \
    droidos-interfaces \
    droidos-bodies \
    droidos-hardening \
    packagegroup-droidos-ros \
    rauc \
    kernel-modules \
    "

# Every build must carry version, source revision and manifests (spec §35).
IMAGE_NAME_SUFFIX = ""
DROIDOS_IMAGE_VERSION = "${DISTRO_VERSION}"

ROOTFS_POSTPROCESS_COMMAND += "droidos_write_manifest;"

droidos_write_manifest() {
    cat > ${IMAGE_ROOTFS}/etc/droidos/build.json <<EOF
{
  "distro": "${DISTRO}",
  "version": "${DISTRO_VERSION}",
  "codename": "${DISTRO_CODENAME}",
  "machine": "${MACHINE}",
  "kernel": "${PREFERRED_VERSION_linux-droidos}",
  "ros_distro": "${DROIDOS_ROS_DISTRO}",
  "build_time": "${DATETIME}"
}
EOF
}
droidos_write_manifest[vardepsexclude] = "DATETIME"
