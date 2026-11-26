"""联合派单的近义模块路径。"""
from .joint_risk import *  # noqa: F401,F403
from .service import (  # noqa: F401
    plan_jobs, plan_joint_budget, plan_paired_dispatch,
    plan_correlated_dispatch, allocate_joint_risk, joint_dispatch_plan,
    recommend, allocate_joint,
)
