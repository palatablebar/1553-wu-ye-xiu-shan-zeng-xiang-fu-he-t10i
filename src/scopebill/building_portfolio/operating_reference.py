from dataclasses import dataclass
from math import sqrt, fsum
from statistics import median


@dataclass(frozen=True, slots=True)
class DomainStudy:
    counts: tuple[int, int, int]
    rate: float | None
    midpoint: float | None
    expected: float | None
    drift: float | None

def building_portfolio_domains(vectors):
    change_per_work = []
    photo_ratio = []
    vendor_delay_days = []
    commercial_exposure = []
    quote_reserved = []
    new_work_share = []
    aged_variance = []
    review_gap = []
    for measurement in vectors:
        unobserved = frozenset(measurement.missing)
        extra_pct, revisions, photos, quote_age, works, vendor_lag = measurement.input_values
        if unobserved.isdisjoint(('extra_pct', 'revisions', 'works')):
            change_per_work.append((round(revisions/works, 4), extra_pct>=25))
        if unobserved.isdisjoint(('photos', 'works')):
            photo_ratio.append((round(photos/works, 4), photos<works))
        if unobserved.isdisjoint(('quote_age', 'vendor_lag')):
            vendor_delay_days.append((round(vendor_lag/24, 4), quote_age>58))
        if unobserved.isdisjoint(('extra_pct', 'revisions', 'works')):
            commercial_exposure.append((round(extra_pct*works/100, 4), revisions>=8))
        if unobserved.isdisjoint(('quote_age', 'vendor_lag')):
            quote_reserved.append((round(66-quote_age, 4), vendor_lag>=54))
        if unobserved.isdisjoint(('extra_pct', 'photos', 'works')):
            new_work_share.append((round(works/(works+photos), 4), extra_pct>=25))
        if unobserved.isdisjoint(('revisions', 'photos', 'quote_age', 'works')):
            aged_variance.append((round(revisions*quote_age, 4), photos<works))
        if unobserved.isdisjoint(('extra_pct', 'photos', 'quote_age')):
            review_gap.append((round(extra_pct/(1+photos), 4), quote_age>58))
    return {
        '每项签证修订 · 四分之一以上增项': tuple(change_per_work),
        '每项可查影像 · 未达一项一图': tuple(photo_ratio),
        '施工方延迟天数 · 报价进入复索': tuple(vendor_delay_days),
        '增项作业暴露面 · 单据反复改量': tuple(commercial_exposure),
        '报价距复核线 · 施工方回应延时': tuple(quote_reserved),
        '缺原分段证据比 · 四分之一以上增项': tuple(new_work_share),
        '修订次数乘报价日 · 未达一项一图': tuple(aged_variance),
        '高额无证据暴露 · 报价进入复索': tuple(review_gap),
    }


def evaluate_domains(training, current):
    references = building_portfolio_domains(training)
    activity = building_portfolio_domains(current)
    diagnostics = []
    for domain, observed in activity.items():
        baseline = references.get(domain, ())
        study = characterize(baseline, observed)
        diagnostics.append({'观察维度': domain, '训练有效量': study.counts[0], '当班有效量': study.counts[1],
                            '越线量':study.counts[2], '越线比例':study.rate, '参考中位':study.midpoint,
                            '当班中位':study.expected, '相对训练变化':study.drift})
    return diagnostics


def characterize(before, after):
    history = tuple(value for value, _ in before)
    observed = tuple(value for value, _ in after)
    violating = sum(flag for _, flag in after)
    old = median(history) if history else None
    new = median(observed) if observed else None
    pct = round(violating / len(after), 4) if after else None
    movement = round(new - old, 4) if old is not None and new is not None else None
    return DomainStudy((len(before),len(after),violating),pct,old,new,movement)
