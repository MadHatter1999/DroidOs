# Install the DroidOS RAUC system configuration (spec §33).
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI += "file://system.conf"

do_install:append() {
    install -d ${D}${sysconfdir}/rauc
    install -m 0644 ${WORKDIR}/system.conf ${D}${sysconfdir}/rauc/system.conf
    # The verification keyring (etc/rauc/keyring.pem) is provisioned per-fleet and
    # is never committed to the source tree.
}
