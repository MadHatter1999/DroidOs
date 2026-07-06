"""ROS 2 lifecycle-node bridge for the DroidOS brain (roadmap M1).

These nodes wrap the single-process ``droidos`` reference brain and expose it over
ROS 2 using the ``droid_interfaces`` definitions. Requires a ROS 2 install; not
runnable in the plain reference checkout.
"""

from .brain import get_brain

__all__ = ["get_brain"]
