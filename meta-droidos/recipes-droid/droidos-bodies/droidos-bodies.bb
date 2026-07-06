SUMMARY = "DroidOS body packages (spec §20)"
DESCRIPTION = "Signed, self-describing body packages installed under \
/usr/lib/droidos/bodies. Includes the reference biped (ig-mk1) and wheeled \
(r2-mk1) bodies. Adding a robot means adding a body package, not changing the brain."
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = "file://bodies"

do_install() {
    install -d ${D}${libdir}/droidos/bodies
    cp -r ${WORKDIR}/bodies/* ${D}${libdir}/droidos/bodies/
    # In production, each body package is signature-verified before activation
    # (spec §20, §40); do_install would also stage the detached signatures.
}

FILES:${PN} = "${libdir}/droidos/bodies"
