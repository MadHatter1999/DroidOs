"""droid_supervisor ROS 2 lifecycle node (spec §11, §12.1).

Publishes the authoritative DroidState and drives the boot sequence through the
managed lifecycle. Requires rclpy + droid_interfaces.
"""

from __future__ import annotations

import rclpy
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn

from droid_interfaces.msg import DroidState
from .brain import get_brain


class SupervisorNode(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("droid_supervisor")
        self._pub = None
        self._timer = None

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.brain = get_brain()
        self._pub = self.create_lifecycle_publisher(DroidState, "~/state", 10)
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self._timer = self.create_timer(0.5, self._publish_state)
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        if self._timer:
            self._timer.cancel()
        return super().on_deactivate(state)

    def _publish_state(self) -> None:
        rt = self.brain.rt
        readiness = self.brain.supervisor.assess_readiness()
        msg = DroidState()
        msg.state = rt.state.state.value
        msg.body_id = rt.body.body_id if rt.body else ""
        msg.backend = rt.body.backend_kind if rt.body else ""
        msg.motion_permitted = rt.state.motion_permitted()
        msg.inhibit_reasons = readiness.inhibit_reasons
        msg.battery_percent = float(rt.backend.battery().percent) if rt.backend else 0.0
        self._pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SupervisorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
