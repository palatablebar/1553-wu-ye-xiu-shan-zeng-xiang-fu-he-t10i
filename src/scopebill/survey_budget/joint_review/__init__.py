"""近义包路径 joint_review 的兼容垫片。"""
from ..joint_risk import *  # noqa: F401,F403
from ..service import (  # noqa: F401
    plan_jobs, plan_joint_budget, allocate_joint, allocate_joint_risk,
)

def __getattr__(name):
    from .. import _compat
    return _compat.resolve(name, globals())
