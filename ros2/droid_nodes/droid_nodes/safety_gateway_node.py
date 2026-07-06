"""droid_safety_gateway ROS 2 node (spec §12.2, §24).

Publishes SafetyState and offers an emergency-stop service. The e-stop service is
always available and never requires confirmation.
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger

from droid_interfaces.msg import SafetyState
from .brain import get_brain


class SafetyGatewayNode(Node):
    def __init__(self) -> None:
        super().__init__("droid_safety_gateway")
        self.brain = get_brain()
        self._pub = self.create_publisher(SafetyState, "~/safety", 10)
        self.create_timer(0.1, self._publish)  # 10 Hz
        self.create_service(Trigger, "~/estop", self._estop_cb)
        self.create_service(Trigger, "~/reset", self._reset_cb)

    def _publish(self) -> None:
        st = self.brain.rt.safety.controller.status()
        msg = SafetyState()
        msg.alive = st.alive
        msg.estop_engaged = st.estop_engaged
        msg.power_enabled = st.power_enabled
        msg.watchdog_ok = st.watchdog_ok
        msg.movement_permitted = st.movement_permitted()
        msg.faults = list(st.faults)
        msg.last_host_contact_age_s = float(st.last_host_contact_age_s)
        self._pub.publish(msg)

    def _estop_cb(self, request, response):
        self.brain.rt.safety.engage_estop("ros_service")
        response.success = True
        response.message = "emergency stop engaged; motor power removed"
        return response

    def _reset_cb(self, request, response):
        self.brain.rt.safety.reset_estop()
        response.success = True
        response.message = "e-stop latch cleared; reboot to re-arm"
        return response


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SafetyGatewayNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
