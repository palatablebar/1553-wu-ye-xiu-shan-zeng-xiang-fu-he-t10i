"""回放误差关联的近义模块路径垫片。"""
from ..survey_budget.joint_risk import *  # noqa: F401,F403

def __getattr__(name):
    from ..survey_budget import _compat
    return _compat.resolve(name, globals())
