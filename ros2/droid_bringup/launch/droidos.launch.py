"""Bring up the DroidOS ROS 2 bridge nodes (roadmap M1).

    ros2 launch droid_bringup droidos.launch.py
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        # Safety gateway comes up first; nothing moves until it is healthy (spec §8).
        Node(package="droid_nodes", executable="droid_safety_gateway",
             name="droid_safety_gateway", output="screen"),
        Node(package="droid_nodes", executable="droid_supervisor",
             name="droid_supervisor", output="screen"),
        Node(package="droid_nodes", executable="droid_language",
             name="droid_language", output="screen"),
    ])
