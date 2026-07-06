"""Walking-policy support (spec §25).

Training happens off-board; the installed image performs *inference* using the
exported policy. This package loads, validates and runs a gait policy, rejecting
one that does not match the body, has a bad checksum, has an incompatible
observation layout, needs missing sensors, or is not approved for physical use.
"""

from .policy import GaitPolicy, GaitPolicyError, load_for_body

__all__ = ["GaitPolicy", "GaitPolicyError", "load_for_body"]
