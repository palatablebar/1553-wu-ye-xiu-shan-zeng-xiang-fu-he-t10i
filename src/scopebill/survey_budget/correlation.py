"""误差关联估计的近义模块路径，实现见 :mod:`joint_risk`。"""
from .joint_risk import *  # noqa: F401,F403
from .joint_risk import (  # noqa: F401
    error_correlation, estimate_error_correlation, residual_correlation,
    paired_errors, pearson_association, intraclass_association, build_links,
    association_from_replay, find_comparable, pair_joint_risk,
    cohort_double_miss_risk, joint_miss_risk,
)
from .service import plan_jobs, plan_joint_budget  # noqa: F401
