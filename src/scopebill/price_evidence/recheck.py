"""价证登记复算的近义模块路径垫片。"""
from .service import *  # noqa: F401,F403

def __getattr__(name):
    from ..survey_budget import _compat
    return _compat.resolve(name, globals())
