# DroidOS kernel configuration (spec §5). The kernel is configured and branded,
# not rewritten. Board-specific fragments live in the RPi/Tegra layers.

FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI += " \
    file://droidos-realtime.cfg \
    file://droidos-can.cfg \
    file://droidos-watchdog.cfg \
    file://droidos-hardening.cfg \
    file://droidos-robotics.cfg \
"

# Brand the kernel (spec §5): Linux 6.x-droidos.
KERNEL_LOCALVERSION:append = "-droidos"
