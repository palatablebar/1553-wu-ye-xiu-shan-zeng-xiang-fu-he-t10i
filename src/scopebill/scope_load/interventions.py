from dataclasses import replace
from statistics import median

from .contracts import ScopeLoad, Proposal


def measure_scope_load(values) -> ScopeLoad:
    extra_pct, revisions, photos, quote_age, works, vendor_lag = values
    return ScopeLoad(
        change_per_work=revisions/works,
        photo_ratio=photos/works,
        vendor_delay_days=vendor_lag/24,
        commercial_exposure=extra_pct*works/100,
        quote_reserved=66-quote_age,
        new_work_share=works/(works+photos),
        aged_variance=revisions*quote_age,
        review_gap=extra_pct/(1+photos),
    )


def propose_survey_budget(values, missing=()):
    extra_pct, revisions, photos, quote_age, works, vendor_lag = values
    if 'photos' not in missing and (photos<=36):
        yield Proposal('补六张见证影像', 'photos', photos, min(42,photos+6), 2)
    if 'quote_age' not in missing and (quote_age>=29):
        yield Proposal('重新询价当天生效', 'quote_age', quote_age, 4, 2)
    if 'revisions' not in missing and (revisions>=4):
        yield Proposal('合并两张同类签证修订', 'revisions', revisions, max(0,revisions-2), 1)
    if 'works' not in missing and (works>=6):
        yield Proposal('现场复量缩减三项', 'works', works, max(1,works-3), 3)
