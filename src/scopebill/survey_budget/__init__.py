"""survey budget."""

from .service import (
    plan_jobs,
    action_evidence,
    plan_joint_budget,
    plan_paired_dispatch,
    plan_correlated_dispatch,
    allocate_joint_risk,
    joint_dispatch_plan,
)
from .joint_risk import (
    JOINT_RISK_LIMIT,
    JOINT_MODE_NAMES,
    build_links,
    error_correlation,
    pair_joint_risk,
    cohort_double_miss_risk,
    joint_miss_risk,
    as_report,
)

__all__ = (
    'plan_jobs', 'action_evidence', 'plan_joint_budget', 'plan_paired_dispatch',
    'plan_correlated_dispatch', 'allocate_joint_risk', 'joint_dispatch_plan',
    'JOINT_RISK_LIMIT', 'JOINT_MODE_NAMES', 'build_links', 'error_correlation',
    'pair_joint_risk', 'cohort_double_miss_risk', 'joint_miss_risk',
)


def __getattr__(name):
    from ._compat import package_attr
    return package_attr(__name__, name, globals())
