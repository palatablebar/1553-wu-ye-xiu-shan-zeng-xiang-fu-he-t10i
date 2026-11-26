"""近义模块路径兼容垫片，核心实现见 survey_budget.joint_risk / service。"""
from .joint_risk import *  # noqa: F401,F403
from .service import *  # noqa: F401,F403

def __getattr__(name):
    from . import _compat
    return _compat.resolve(name, globals())
