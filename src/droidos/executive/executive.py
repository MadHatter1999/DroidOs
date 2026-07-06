"""``droid-executive`` (spec §12.10).

Executes complete tasks from approved intents: builds or selects a behaviour tree,
coordinates subsystems, monitors progress, performs recovery, can cancel, reports
results and preserves an auditable task history. It never generates motor current
and never bypasses the broker or the safety gateway.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from ..backends.base import Pose
from ..core.models import BodyVelocity
from ..core.states import DroidState
from ..services.lifecycle import ManagedService
from .behaviour_tree import Action, Sequence, Status, run
from .tasks import Task, TaskResult, TaskState

if TYPE_CHECKING:
    from ..language.broker import BrokerDecision
    from ..system import Runtime

DRIVE_DT = 0.1
ARRIVAL_M = 0.15
MAX_DRIVE_TICKS = 3000


class Executive(ManagedService):
    requires = ("safety_gateway", "motion", "navigation", "state_estimator")

    def __init__(self, rt: "Runtime") -> None:
        super().__init__("executive", rt)
        self.current_task: Task | None = None
        self.history: list[Task] = []
        self._cancel = False
        self._handlers: dict[str, Callable[[Task], TaskResult]] = {}
        self._register_handlers()

    # public entry point --------------------------------------------------- #
    def run_intent(self, decision: "BrokerDecision", user: str) -> TaskResult:
        intent = decision.intent
        task = Task(intent=intent.intent, user=user, arguments=dict(intent.arguments))
        self.current_task = task
        self._cancel = False
        task.start()
        self.rt.audit.emit(
            "task", user=user, request_text=intent.raw_text, intent=intent.intent,
            arguments=intent.arguments, approval="approved", task_id=task.task_id, outcome="started",
        )
        handler = self._handlers.get(intent.intent, self._unhandled)
        try:
            result = handler(task)
        except Exception as exc:  # noqa: BLE001 - a task failure must not crash the brain
            result = TaskResult(False, intent.intent, error=f"{type(exc).__name__}: {exc}")
        result.task_id = task.task_id
        task.finish(TaskState.SUCCEEDED if result.ok else
                    (TaskState.CANCELLED if result.kind == "task.cancel" and result.ok else TaskState.FAILED))
        self.history.append(task)
        self.rt.audit.emit(
            "task", user=user, intent=intent.intent, task_id=task.task_id,
            outcome=task.state.value, reason=result.error or "",
            safety_state=self.rt.state.state.value,
        )
        self.current_task = None
        return result

    def cancel(self) -> None:
        self._cancel = True

    def last_task(self) -> Task | None:
        return self.history[-1] if self.history else None

    # handler registry ----------------------------------------------------- #
    def _register_handlers(self) -> None:
        h = self._handlers
        h["robot.get_status"] = self._h_status
        h["robot.get_battery"] = self._h_battery
        h["robot.get_temperature"] = self._h_temperature
        h["diagnostics.summary"] = self._h_diagnostics
        h["robot.explain"] = self._h_explain
        h["perception.describe_scene"] = self._h_describe
        h["navigation.list_places"] = self._h_list_places
        h["help"] = self._h_help
        h["motion.stop"] = self._h_stop
        h["motion.emergency_stop"] = self._h_estop
        h["task.cancel"] = self._h_cancel
        h["voice.silence"] = self._h_silence
        h["robot.return_safe_idle"] = self._h_safe_idle
        h["navigation.navigate_to"] = self._h_navigate
        h["navigation.go_charge"] = self._h_go_charge
        h["inspect.named_target"] = self._h_inspect
        h["memory.remember"] = self._h_remember
        h["memory.store_place"] = self._h_store_place
        h["memory.forget"] = self._h_forget
        h["system.set_body"] = self._h_set_body
        h["system.install_update"] = self._h_install_update
        h["system.request_reboot"] = self._h_reboot
        h["system.shutdown"] = self._h_shutdown

    # information handlers ------------------------------------------------- #
    def _h_status(self, task: Task) -> TaskResult:
        rt = self.rt
        battery = rt.backend.battery() if rt.backend else None
        supervisor = getattr(rt, "supervisor", None)
        readiness = supervisor.assess_readiness() if supervisor else None
        hottest = rt.diagnostics.hottest_actuator() if rt.diagnostics else None
        data = {
            "name": self._name(),
            "state": rt.state.state.value,
            "body": rt.body.body_id if rt.body else None,
            "battery_percent": battery.percent if battery else None,
            "motion_permitted": rt.state.motion_permitted(),
            "inhibit_reasons": readiness.inhibit_reasons if readiness else [],
            "safety": rt.safety.status() if rt.safety else {},
            "hottest_motor": hottest.to_dict() if hottest else None,
            "language_degraded": getattr(rt, "language_degraded", False),
        }
        return TaskResult(True, "robot.get_status", data)

    def _h_battery(self, task: Task) -> TaskResult:
        b = self.rt.backend.battery()
        minimum = self.rt.body.limits.battery_motion_minimum()
        return TaskResult(True, "robot.get_battery", {
            "percent": b.percent, "charging": b.charging,
            "motion_minimum": minimum, "safe_to_move": b.percent >= minimum,
        })

    def _h_temperature(self, task: Task) -> TaskResult:
        acts = self.rt.backend.read_all_actuators()
        warn = self.rt.body.limits.motor_warn_temp()
        fault = self.rt.body.limits.motor_fault_temp()
        temps = sorted(
            ({"name": a.name, "temp_c": round(a.temperature_c, 1)} for a in acts.values()),
            key=lambda d: d["temp_c"], reverse=True,
        )
        return TaskResult(True, "robot.get_temperature", {
            "hottest": temps[0] if temps else None, "all": temps,
            "warn_c": warn, "fault_c": fault,
        })

    def _h_diagnostics(self, task: Task) -> TaskResult:
        summary = self.rt.diagnostics.summary()
        return TaskResult(True, "diagnostics.summary", summary)

    def _h_explain(self, task: Task) -> TaskResult:
        topic = task.arguments.get("topic", "why")
        rt = self.rt
        if topic == "current_task":
            last = self.last_task()
            return TaskResult(True, "robot.explain", {
                "topic": "current_task",
                "last_task": last.to_dict() if last else None,
            })
        supervisor = getattr(rt, "supervisor", None)
        readiness = supervisor.assess_readiness() if supervisor else None
        reasons = readiness.inhibit_reasons if readiness else []
        return TaskResult(True, "robot.explain", {
            "topic": "why",
            "state": rt.state.state.value,
            "inhibit_reasons": reasons,
            "estop": rt.safety.estop_engaged() if rt.safety else False,
        })

    def _h_describe(self, task: Task) -> TaskResult:
        scene = self.rt.perception.describe()
        return TaskResult(scene.get("camera_ok", False) or "summary" in scene,
                          "perception.describe_scene", scene)

    def _h_list_places(self, task: Task) -> TaskResult:
        wm = self.rt.world_model
        return TaskResult(True, "navigation.list_places", {
            "places": wm.place_names() if wm else [],
            "detail": wm.places() if wm else {},
        })

    def _h_help(self, task: Task) -> TaskResult:
        reg = getattr(self.rt, "tool_registry", None)
        tools = reg.all() if reg else []
        return TaskResult(True, "help", {
            "tools": [{"name": t.name, "description": t.description, "risk": t.risk.value} for t in tools]
        })

    # safety / control handlers -------------------------------------------- #
    def _h_stop(self, task: Task) -> TaskResult:
        self.rt.motion.stop()
        return TaskResult(True, "motion.stop", {"stopped": True})

    def _h_estop(self, task: Task) -> TaskResult:
        self.rt.safety.engage_estop("voice_or_text_command")
        return TaskResult(True, "motion.emergency_stop", {"estop": True})

    def _h_cancel(self, task: Task) -> TaskResult:
        self.cancel()
        self.rt.motion.stop()
        return TaskResult(True, "task.cancel", {"cancelled": True})

    def _h_silence(self, task: Task) -> TaskResult:
        return TaskResult(True, "voice.silence", {"silenced": True})

    def _h_safe_idle(self, task: Task) -> TaskResult:
        if self.rt.safety:
            self.rt.safety.release_motion_permission()
        st = self.rt.state
        if st.state in (DroidState.READY, DroidState.ACTIVE, DroidState.DEGRADED):
            st.transition(DroidState.SAFE_IDLE, "operator requested safe idle")
        return TaskResult(True, "robot.return_safe_idle", {"state": st.state.value})

    # motion handlers ------------------------------------------------------ #
    def _h_navigate(self, task: Task) -> TaskResult:
        dest = task.arguments.get("destination", "")
        goal = self.rt.navigation.resolve(dest)
        if goal is None:
            return TaskResult(False, "navigation.navigate_to", error=f"{dest!r} is not a known place")
        ok, data, err = self._drive_to(goal, dest, task)
        data["destination"] = dest
        return TaskResult(ok, "navigation.navigate_to", data, err)

    def _h_go_charge(self, task: Task) -> TaskResult:
        goal = self.rt.navigation.resolve("charging station")
        if goal is None:
            return TaskResult(False, "navigation.go_charge", error="no charging station is known")
        ok, data, err = self._drive_to(goal, "charging station", task)
        if ok and self.rt.backend is not None and hasattr(self.rt.backend, "set_charging"):
            self.rt.backend.set_charging(True)
            data["docked"] = True
        return TaskResult(ok, "navigation.go_charge", data, err)

    def _h_inspect(self, task: Task) -> TaskResult:
        dest = task.arguments.get("destination")
        target = task.arguments.get("target", "")
        drive_data: dict[str, Any] = {}
        if dest:
            goal = self.rt.navigation.resolve(dest)
            if goal is None:
                return TaskResult(False, "inspect.named_target", error=f"{dest!r} is not a known place")
            ok, drive_data, err = self._drive_to(goal, dest, task)
            if not ok:
                return TaskResult(False, "inspect.named_target", drive_data, err)
        task.step(f"inspect {target}")
        try:
            findings = self.rt.perception.inspect(target)
        except Exception as exc:  # noqa: BLE001 - honest failure (spec §39)
            return TaskResult(False, "inspect.named_target", drive_data, str(exc))
        findings["destination"] = dest
        findings.update({"drive": drive_data} if drive_data else {})
        return TaskResult(True, "inspect.named_target", findings)

    def _drive_to(self, goal: Pose, label: str, task: Task) -> tuple[bool, dict[str, Any], str]:
        """Behaviour-tree driven navigation with a live collision monitor (spec §12.8, §39)."""
        rt = self.rt
        task.step("check health")
        task.step(f"navigate to {label}")
        data: dict[str, Any] = {"label": label}

        permission = {"held": False}

        def acquire() -> bool:
            perm = rt.safety.request_motion_permission()
            data["motion_permission"] = perm.to_dict()
            permission["held"] = perm.granted
            return perm.granted

        def enter_active() -> bool:
            if rt.state.state in (DroidState.READY, DroidState.DEGRADED):
                rt.state.transition(DroidState.ACTIVE, f"navigate to {label}")
            return True

        def drive() -> Status:
            for _ in range(MAX_DRIVE_TICKS):
                if self._cancel:
                    data["result"] = "cancelled"
                    return Status.FAILURE
                if not rt.navigation.localization_ok():
                    data["result"] = "localization_lost"
                    return Status.FAILURE
                blocked, dist = rt.navigation.is_path_blocked()
                if blocked:
                    data["result"] = "blocked"
                    data["stopped_distance_m"] = round(dist, 1) if dist else None
                    if dist is not None and rt.world_model:
                        rt.world_model.set_obstacle(rt.backend.pose().x + dist, rt.backend.pose().y)
                    return Status.FAILURE
                vel, remaining = rt.motion.velocity_toward(goal, rt.backend.pose())
                data["remaining_m"] = round(remaining, 2)
                if remaining <= ARRIVAL_M:
                    data["result"] = "arrived"
                    return Status.SUCCESS
                rt.motion.drive(vel, DRIVE_DT)
            data["result"] = "timeout"
            return Status.FAILURE

        tree = Sequence("navigate", [
            Action("acquire_motion_permission", acquire),
            Action("enter_active", enter_active),
            Action("drive_to_goal", drive),
        ])
        status = run(tree)

        # always release power and settle state (spec §9)
        if permission["held"]:
            rt.safety.release_motion_permission()
        if rt.state.state == DroidState.ACTIVE:
            rt.state.transition(DroidState.READY, "task complete")

        if status == Status.SUCCESS:
            return True, data, ""
        reason = {
            "blocked": f"the route to {label} is blocked; I stopped "
                       f"{data.get('stopped_distance_m', '?')} m from the obstruction",
            "localization_lost": "I am no longer sufficiently certain of my position to continue",
            "cancelled": "the task was cancelled",
            "timeout": f"I could not reach {label} within the movement budget",
        }.get(data.get("result", ""), tree.last_failed or "navigation failed")
        if not permission["held"]:
            reason = data.get("motion_permission", {}).get("reason", reason)
        return False, data, reason

    # memory handlers ------------------------------------------------------ #
    def _h_remember(self, task: Task) -> TaskResult:
        text = task.arguments.get("text", "")
        if not text:
            return TaskResult(False, "memory.remember", error="nothing to remember")
        entry = self.rt.memory.remember(text)
        return TaskResult(True, "memory.remember", {"remembered": entry["text"]})

    def _h_store_place(self, task: Task) -> TaskResult:
        a = task.arguments
        name = a.get("name")
        if not name:
            return TaskResult(False, "memory.store_place", error="no place name given")
        x = float(a.get("x", self.rt.backend.pose().x))
        y = float(a.get("y", self.rt.backend.pose().y))
        self.rt.world_model.add_place(name, x, y, a.get("kind", "room"))
        self.rt.memory.remember(f"{name} is a place at ({x:.1f}, {y:.1f})", category="place")
        return TaskResult(True, "memory.store_place", {"place": name, "x": x, "y": y})

    def _h_forget(self, task: Task) -> TaskResult:
        query = task.arguments.get("query", "")
        removed = self.rt.memory.forget(query)
        also_place = self.rt.world_model.remove_place(query) if self.rt.world_model else False
        return TaskResult(True, "memory.forget", {"removed": removed, "place_removed": also_place})

    # administrative handlers ---------------------------------------------- #
    def _h_set_body(self, task: Task) -> TaskResult:
        body_id = task.arguments.get("body_id", "")
        backend = task.arguments.get("backend")
        try:
            sel = self.rt.body_manager.set_active(body_id, backend)
        except Exception as exc:  # noqa: BLE001
            return TaskResult(False, "system.set_body", error=str(exc))
        return TaskResult(True, "system.set_body", {"selection": sel, "applies": "next boot"})

    def _h_install_update(self, task: Task) -> TaskResult:
        updater = self.rt.update
        bundle = task.arguments.get("bundle")
        if updater is None:
            return TaskResult(False, "system.install_update", error="update service unavailable")
        if not bundle:
            st = updater.status()
            return TaskResult(True, "system.install_update", {
                "note": "no update bundle specified", "status": st,
            })
        result = updater.install(bundle)
        return TaskResult(result.get("ok", False), "system.install_update", result,
                          error="" if result.get("ok") else result.get("reason", "install failed"))

    def _h_reboot(self, task: Task) -> TaskResult:
        return TaskResult(True, "system.request_reboot", {"note": "reboot requested (reference stub)"})

    def _h_shutdown(self, task: Task) -> TaskResult:
        supervisor = getattr(self.rt, "supervisor", None)
        if supervisor is not None:
            supervisor.request_shutdown()
        return TaskResult(True, "system.shutdown", {"state": self.rt.state.state.value})

    def _unhandled(self, task: Task) -> TaskResult:
        return TaskResult(False, task.intent, error="no executive handler for this intent")

    def _name(self) -> str:
        return self.rt.config.identity.get("name", "droid")
