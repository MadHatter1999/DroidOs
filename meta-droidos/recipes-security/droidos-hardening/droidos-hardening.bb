SUMMARY = "DroidOS system hardening (spec §31)"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = "file://droidos-sysctl.conf file://droidos-modprobe-blacklist.conf"

do_install() {
    install -d ${D}${sysconfdir}/sysctl.d
    install -m 0644 ${WORKDIR}/droidos-sysctl.conf ${D}${sysconfdir}/sysctl.d/90-droidos.conf
    install -d ${D}${sysconfdir}/modprobe.d
    install -m 0644 ${WORKDIR}/droidos-modprobe-blacklist.conf ${D}${sysconfdir}/modprobe.d/droidos-blacklist.conf
}

FILES:${PN} = "${sysconfdir}/sysctl.d ${sysconfdir}/modprobe.d"
