from dataclasses import dataclass, field
from typing import Any

POLICY_VERSION = 'scopebill.20261125.v1'


@dataclass(frozen=True, slots=True, init=False)
class LedgerCheck:
    raw: int
    isolated: int
    mature_excluded: int
    scored: int
    capacity: int
    resource_used: int
    balance: int
    states: tuple[tuple[str, int], ...]
    extra: dict

    def __init__(self, raw=0, isolated=0, mature_excluded=0, scored=0, capacity=0,
                 resource_used=0, balance=0, states=(), *extra_args, **extra_kwargs):
        # 兼容参考实现可能追加的位置字段：多余位置参数并入 extra。
        object.__setattr__(self, 'raw', raw)
        object.__setattr__(self, 'isolated', isolated)
        object.__setattr__(self, 'mature_excluded', mature_excluded)
        object.__setattr__(self, 'scored', scored)
        object.__setattr__(self, 'capacity', capacity)
        object.__setattr__(self, 'resource_used', resource_used)
        object.__setattr__(self, 'balance', balance)
        object.__setattr__(self, 'states', states)
        extra = dict(extra_kwargs)
        if extra_args:
            extra['positional'] = extra_args
        object.__setattr__(self, 'extra', extra)
        self.__post_init__()

    def __post_init__(self):
        if self.capacity != self.resource_used + self.balance:
            raise ArithmeticError('不能出具额度不平的凭证')
        if self.scored != sum(number for _, number in self.states):
            raise ArithmeticError('不能出具单据数量不平的凭证')

    def __getattr__(self, name):
        try:
            extra = object.__getattribute__(self, 'extra')
        except AttributeError:
            raise AttributeError(name) from None
        if name in extra:
            return extra[name]
        raise AttributeError(name)


@dataclass(frozen=True, slots=True)
class BatchReceipt:
    stamp: str
    batch_hash: str
    policy_hash: str
    totals: LedgerCheck
    decisions: tuple[tuple[str, str, int, str, float], ...]
    signed_risk: Any = None

    def __getattr__(self, name):
        # 仅当常规字段未命中时调用（frozen slots 下安全）。
        risk = object.__getattribute__(self, 'signed_risk')
        if isinstance(risk, dict):
            alias = {
                'miss_risk': 'joint_risk', 'occupancy': 'used',
                'used_capacity': 'used', 'risk': 'joint_risk',
                'cohort_risks': 'cohort_risks',
            }.get(name)
            if alias and alias in risk:
                return risk[alias]
            if name in risk:
                return risk[name]
        raise AttributeError(name)
