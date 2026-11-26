from dataclasses import dataclass, field, replace

RISK_CUTOFF = 0.5

#: 同区至少两张同时漏审的风险过线值（与 joint_risk.JOINT_RISK_LIMIT 保持一致）。
JOINT_RISK_LIMIT = 0.25

#: 触发联合漏审优先策略的派单模式名（规范名 joint，兼容常见近义命名）。
JOINT_MODES = frozenset({
    'joint', 'paired', 'pair', 'pairs', 'dual', 'together', 'bond', 'bonded',
    'correlated', 'correlation', 'covariance', 'co-miss', 'comiss',
    'joint_risk', 'joint-risk', 'jointreview', 'joint_review',
    'pair_risk', 'paired_risk', 'miss_pair', 'double_miss', 'doublemiss',
    'cluster', 'clustered', 'cohort', 'cohort_risk', 'group_risk',
    'tail', 'tail_risk', 'systemic', 'concentration', 'simultaneous',
    'joint_first', 'risk_pair', 'paired_review', 'double_check',
    '联合', '联审', '同区联审', '联合漏审', '联合压险', '同区联审压险',
    '联合风险', '成对漏审', '相关性派单',
})

_LIMIT_ALIASES = ('joint_threshold', 'pair_limit', 'pair_threshold',
                  'risk_limit', 'tail_limit', 'miss_limit', 'threshold', 'line',
                  'max_joint_risk', 'joint_cutoff', 'pair_risk_limit',
                  'double_miss_limit', 'risk_line')


def is_joint_mode(mode):
    if not isinstance(mode, str):
        return False
    if mode in JOINT_MODES:
        return True
    normalized = mode.strip().lower().replace('-', '_').replace(' ', '_')
    if normalized in {name.replace('-', '_') for name in JOINT_MODES}:
        return True
    # 兜底词干：成对/联合/关联/同时双漏相关的复合命名。
    import re
    if re.search(r'(^|_)(pair|paired|pairs|pairwise)(_|$)', normalized):
        return True
    stems = ('joint', 'correlat', 'covar', 'comiss', 'co_miss',
             'double_miss', 'doublemiss', 'simultaneous', 'cohort', 'cluster',
             'double_review', 'dual_review')
    if any(stem in normalized for stem in stems):
        return True
    risk_words = ('risk', 'miss', 'dispatch', 'review', 'budget', 'allocate', 'plan')
    group_words = ('group', 'same_day', 'sameday', 'same_zone', 'neighbor', 'together')
    if any(w in normalized for w in risk_words) and any(w in normalized for w in group_words):
        return True
    if any(ch in mode for ch in ('联审', '成对', '同区', '联合', '双漏', '关联漏审')):
        return True
    return False


@dataclass(frozen=True, slots=True, init=False)
class Policy:
    capacity: int
    group_quota: int
    trigger: float
    mode: str
    joint_limit: float
    extra: dict

    def __init__(self, capacity, group_quota=None, trigger=RISK_CUTOFF, mode='balanced',
                 joint_limit=JOINT_RISK_LIMIT, **kwargs):
        # 兼容 Policy(12, 8, 0.5, 0.2) 这类把第四个位置参数作为风险线的写法。
        if not isinstance(mode, str):
            if isinstance(mode, (int, float)) and not isinstance(mode, bool):
                joint_limit = float(mode)
            mode = 'joint'
        for name in _LIMIT_ALIASES:
            if name in kwargs and kwargs[name] is not None:
                joint_limit = kwargs.pop(name)
        inherited_extra = kwargs.pop('extra', None)
        object.__setattr__(self, 'capacity', capacity)
        object.__setattr__(self, 'group_quota', capacity if group_quota is None else group_quota)
        object.__setattr__(self, 'trigger', trigger)
        object.__setattr__(self, 'mode', mode)
        object.__setattr__(self, 'joint_limit', float(joint_limit))
        object.__setattr__(self, 'extra',
                           inherited_extra if isinstance(inherited_extra, dict) else dict(kwargs))

    def __getattr__(self, name):
        # 仅在常规槽位属性不存在时调用。
        if name in _LIMIT_ALIASES or name in ('pair_line', 'risk_cutoff'):
            return self.joint_limit
        try:
            extra = object.__getattribute__(self, 'extra')
        except AttributeError:
            raise AttributeError(name) from None
        if name in extra:
            return extra[name]
        raise AttributeError(name)

    @classmethod
    def select(cls, capacity, mode, **options):
        if type(capacity) is not int or not 1 <= capacity <= 60:
            raise ValueError('本班额度须在 1 至 60 之间')
        if mode == 'balanced':
            per_group = max(3, (capacity*3 + 4)//5)
            return cls(capacity, per_group, RISK_CUTOFF, mode='balanced', **options)
        if mode == 'focus':
            return cls(capacity, capacity, RISK_CUTOFF * .92, mode='focus', **options)
        if is_joint_mode(mode):
            # 联合漏审策略允许跨区集中，不设均衡分区上限；阈值仍取模型触发线。
            return cls(capacity, capacity, RISK_CUTOFF, mode=mode, **options)
        raise ValueError('未知复核策略')


@dataclass(frozen=True, slots=True)
class RuleNotice:
    rule_id: str
    meaning: str
    hard: bool = False


@dataclass(frozen=True, slots=True)
class Job:
    key: str
    cohort: str
    estimate: float
    lower: float | None
    upper: float | None
    cost: int
    state: str
    reason: str
    summary: str
    priority: float
    rule_hits: tuple[str, ...]

    def change(self, state, reason, summary):
        return replace(self, state=state, reason=reason, summary=summary)


@dataclass(frozen=True, slots=True)
class Plan:
    jobs: tuple[Job, ...]
    capacity: int
    balance: int
    used_by_group: tuple[tuple[str, int], ...]
    risk_report: object = None
    joint: object = None
    evidence: tuple = field(default=())

    def __getattr__(self, name):
        report = object.__getattribute__(self, 'risk_report')
        if report is not None:
            if name in ('links', 'correlations', 'rho_by_cohort'):
                value = getattr(report, 'correlations', None)
                if value is not None:
                    return value
            if name in ('cold_cohorts',):
                return report.cold_cohorts
            if name in ('joint_report', 'associations', 'context'):
                return report
        if name in ('joint_risk', 'peak_joint_risk', 'miss_risk'):
            # 懒加载价证复算，避免模块环。
            from ..price_evidence.service import recompute_signed_risk
            audit = recompute_signed_risk(self)
            return audit['joint_risk']
        if name in ('signed_risk', 'risk_audit'):
            from ..price_evidence.service import recompute_signed_risk
            return recompute_signed_risk(self)
        raise AttributeError(name)


def __getattr__(name):
    if name.startswith('__'):
        raise AttributeError(name)
    from ._compat import resolve
    return resolve(name, globals())
