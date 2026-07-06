"""droid_language ROS 2 node (spec §12.11, §14).

Exposes the command broker as a ``ValidateIntent`` service and the executive as an
``ExecuteTask`` action. The LLM only proposes; validation and execution stay behind
these typed boundaries.
"""

from __future__ import annotations

import json

import rclpy
from rclpy.action import ActionServer
from rclpy.node import Node

from droid_interfaces.srv import ValidateIntent
from droid_interfaces.action import ExecuteTask
from droidos.language.intent import StructuredIntent
from .brain import get_brain


class LanguageNode(Node):
    def __init__(self) -> None:
        super().__init__("droid_language")
        self.brain = get_brain()
        self.create_service(ValidateIntent, "~/validate_intent", self._validate_cb)
        self._action = ActionServer(self, ExecuteTask, "~/execute_task", self._execute_cb)

    def _to_intent(self, m) -> StructuredIntent:
        return StructuredIntent(
            intent=m.intent,
            arguments=json.loads(m.arguments_json or "{}"),
            requires_motion=m.requires_motion,
            requested_speed=m.requested_speed or "normal",
            source=m.source or "llm",
        )

    def _validate_cb(self, request, response):
        lang = self.brain.rt.language
        user = lang.authorizer.resolve(request.user)
        decision = lang.broker.validate(self._to_intent(request.intent), user,
                                        confirmed=request.confirmed)
        response.outcome = decision.outcome.value
        response.reason = decision.reason
        response.confirm_prompt = decision.confirm_prompt
        response.failed_checks = [c.name for c in decision.checks if not c.ok]
        return response

    def _execute_cb(self, goal_handle):
        req = goal_handle.request
        lang = self.brain.rt.language
        user = lang.authorizer.resolve(req.user)
        decision = lang.broker.validate(self._to_intent(req.intent), user, confirmed=True)
        result = ExecuteTask.Result()
        if not decision.approved:
            result.ok = False
            result.error = decision.reason
            goal_handle.abort()
            return result
        task_result = self.brain.rt.executive.run_intent(decision, user.name)
        result.ok = task_result.ok
        result.result_json = json.dumps(task_result.data)
        result.error = task_result.error
        goal_handle.succeed()
        return result


def main(args=None) -> None:
    rclpy.init(args=args)
    node = LanguageNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
