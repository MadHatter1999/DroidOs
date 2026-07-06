SUMMARY = "DroidOS ROS 2 runtime packagegroup (spec §10, §12)"
DESCRIPTION = "ROS 2 middleware and the robotics stacks DroidOS integrates: \
lifecycle nodes, ros2_control, Nav2 and the diagnostics stack. Uses the ROS 2 \
LTS validated with this Yocto + BSP set (Lyrical Luth)."
LICENSE = "Apache-2.0 & BSD-3-Clause"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

inherit packagegroup

RDEPENDS:${PN} = " \
    ros-core \
    lifecycle \
    ros2-control \
    ros2-controllers \
    navigation2 \
    nav2-collision-monitor \
    diagnostic-aggregator \
    diagnostic-updater \
    droid-interfaces \
"
