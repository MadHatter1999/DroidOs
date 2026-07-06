SUMMARY = "DroidOS reference brain (droid / droidctl and the control runtime)"
DESCRIPTION = "The natural-language control runtime described in the DroidOS \
specification: droid and droidctl CLIs, command broker, tool registry, LLM \
provider interface, body loader, services and executive (spec §12-§17)."
HOMEPAGE = "https://example.invalid/droidos"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

# The core brain has no third-party runtime dependencies by design (spec §7).
inherit setuptools3 systemd

SRC_URI = "file://droidos-src.tar.zst \
           file://droid-supervisor.service \
           file://droid-safety-gateway.service \
           file://droid-language.service \
           file://droidos.target \
           file://droidos-sysusers.conf"

S = "${WORKDIR}/droidos-src"

RDEPENDS:${PN} = "python3-core"
# Optional extras enable richer providers/backends when present.
RRECOMMENDS:${PN} = "python3-json python3-urllib"

SYSTEMD_SERVICE:${PN} = "droid-supervisor.service droid-safety-gateway.service droid-language.service"

do_install:append() {
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/*.service ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/droidos.target ${D}${systemd_system_unitdir}

    install -d ${D}${nonarch_libdir}/sysusers.d
    install -m 0644 ${WORKDIR}/droidos-sysusers.conf ${D}${nonarch_libdir}/sysusers.d/droidos.conf

    # Writable state / log / run directories (read-only rootfs; spec §30, §31).
    install -d ${D}${localstatedir}/lib/droidos
    install -d ${D}${localstatedir}/log/droidos
    install -d ${D}${sysconfdir}/droidos
    install -m 0644 ${S}/config/droidos.yaml ${D}${sysconfdir}/droidos/droidos.yaml
    install -m 0644 ${S}/config/body.yaml    ${D}${sysconfdir}/droidos/body.yaml
    install -m 0644 ${S}/config/users.yaml   ${D}${sysconfdir}/droidos/users.yaml
}

FILES:${PN} += "${systemd_system_unitdir} ${nonarch_libdir}/sysusers.d \
                ${sysconfdir}/droidos ${localstatedir}/lib/droidos ${localstatedir}/log/droidos"
