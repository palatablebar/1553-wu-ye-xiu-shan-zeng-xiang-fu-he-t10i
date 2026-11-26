from dataclasses import dataclass
from math import isfinite
from ..variation_forms.contracts import ScopebillRecord as RawObservation

RAW_KEYS = ('extra_pct', 'revisions', 'photos', 'quote_age', 'works', 'vendor_lag')
FEATURE_KEYS = ('price_pressure', 'quantity_change', 'evidence_gap', 'late_offer', 'unconfirmed_scope')
FEATURE_NAMES = ('增项占比', '单位作业的改量频率', '每份证据对应作业', '报价与交割延迟', '未复核工作量')


@dataclass(frozen=True, slots=True)
class FeatureState:
    fill: tuple[float, ...]
    offsets: tuple[float, ...]
    scales: tuple[float, ...]
    floor: tuple[float, ...]
    ceil: tuple[float, ...]
    fingerprint: str

    def __post_init__(self):
        if len(self.fill) != len(RAW_KEYS):
            raise ValueError('补值向量维数与字段表不匹配')
        if any(len(column) != len(FEATURE_KEYS) for column in (self.offsets, self.scales, self.floor, self.ceil)):
            raise ValueError('特征状态维数不匹配')
        if min(self.scales) <= 0:
            raise ValueError('特征尺度必须为正')


@dataclass(frozen=True, slots=True)
class FeatureVector:
    key: str
    cohort: str
    day: int
    values: tuple[float, ...]
    factors: tuple[float, ...]
    missing: tuple[str, ...]
    excursions: tuple[str, ...]
    outcome: float | None
    observed: bool
    input_values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class PreparedRuns:
    train: tuple[FeatureVector, ...]
    calibration: tuple[FeatureVector, ...]
    replay: tuple[FeatureVector, ...]
    live: tuple[FeatureVector, ...]

    def segments(self):
        return tuple((name, getattr(self, name)) for name in ('train', 'calibration', 'replay', 'live'))


@dataclass(frozen=True, slots=True)
class Proposal:
    name: str
    field: str
    before: float
    after: float
    work: int

    def __post_init__(self):
        if self.before == self.after or not isfinite(self.after) or self.work < 0:
            raise ValueError('推演动作需要实质变动和有效额度')

    def evidence(self):
        return {'情形': self.name, '变更项': self.field, '原值': self.before,
                '置换值': self.after, '用量': self.work}

@dataclass(frozen=True, slots=True)
class ScopeLoad:
    change_per_work: float
    photo_ratio: float
    vendor_delay_days: float
    commercial_exposure: float
    quote_reserved: float
    new_work_share: float
    aged_variance: float
    review_gap: float

    def __post_init__(self):
        if not all(isfinite(amount) for amount in (self.change_per_work, self.photo_ratio, self.vendor_delay_days, self.commercial_exposure, self.quote_reserved, self.new_work_share, self.aged_variance, self.review_gap)):
            raise ValueError('增项签单存在无效的作业量测')

    def explain(self, labels=None):
        return (
            ('每项签证修订', round(self.change_per_work, 4)),
            ('每项可查影像', round(self.photo_ratio, 4)),
            ('施工方延迟天数', round(self.vendor_delay_days, 4)),
            ('增项作业暴露面', round(self.commercial_exposure, 4)),
            ('报价距复核线', round(self.quote_reserved, 4)),
            ('缺原分段证据比', round(self.new_work_share, 4)),
            ('修订次数乘报价日', round(self.aged_variance, 4)),
            ('高额无证据暴露', round(self.review_gap, 4)),
        )
