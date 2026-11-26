from dataclasses import dataclass

FIELDS = {'extra_pct': ('增项金额占比', '%', 2, 90),
 'revisions': ('工程量签单修订', '次', 0, 14),
 'photos': ('抽验影像证据', '张', 0, 42),
 'quote_age': ('报价生效天数', '天', 4, 83),
 'works': ('作业项数', '项', 1, 38),
 'vendor_lag': ('施工方回应', 'h', 2, 70)}
LIMITS = {'result_max': 1}


class MeasureIssue(ValueError):
    def __init__(self, field: str, code: str):
        super().__init__(f'{field}:{code}')
        self.field = field
        self.code = code


@dataclass(frozen=True, slots=True)
class ScopebillRecord:
    key: str
    cohort: str
    day: int
    received: int
    revision: int
    result_day: int | None
    outcome: float | None
    observed: bool
    extra_pct: float | None
    revisions: float | None
    photos: float | None
    quote_age: float | None
    works: float | None
    vendor_lag: float | None

    def signature(self):
        return (self.key, self.cohort, self.day, self.revision, self.result_day, self.outcome, self.observed,
                *(getattr(self, key) for key in FIELDS))


@dataclass(frozen=True, slots=True)
class Issue:
    source_row: int
    key: str
    field: str
    code: str

    def evidence(self):
        return {'行号': self.source_row, '单号': self.key, '字段': FIELDS.get(self.field, (self.field,))[0],
                '原因': self.code}


@dataclass(frozen=True, slots=True)
class DecodeResult:
    entries: tuple[ScopebillRecord, ...]
    issues: tuple[Issue, ...]
    source_rows: int
