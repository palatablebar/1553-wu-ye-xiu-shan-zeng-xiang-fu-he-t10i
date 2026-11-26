from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JointAction:
    case: str
    work_units: int
    notes: str
    changes: dict[str, tuple[float, float]]

    def evidence(self, old_value, new_value, extrapolates):
        return {'联动推演':self.case, '用量':self.work_units, '先决条件':self.notes,
                '原预测':round(old_value,4), '替换预测':round(new_value,4),
                '变化':round(new_value-old_value,4), '超训练域':bool(extrapolates),
                '联动量测':{item:{'原值':before,'替换值':after} for item,(before,after) in self.changes.items()}}


def simulate_collect_evidence(readings, invalid):
    revisions, photos = readings[1], readings[2]
    if invalid.intersection(('revisions', 'photos')):
        return None
    if not (photos<=34 and revisions>=4):
        return None
    photos_adjusted = photos+7
    revisions_adjusted = revisions-3
    inspected = {
        'photos': (photos, photos_adjusted),
        'revisions': (revisions, revisions_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('补证并归并签证', 2, '逐项贴现场复量证明', inspected)
    return None


def simulate_recap_quotation(readings, invalid):
    extra_pct, quote_age = readings[0], readings[3]
    if invalid.intersection(('extra_pct', 'quote_age')):
        return None
    if not (quote_age>=32 and extra_pct>=18):
        return None
    quote_age_adjusted = 4
    extra_pct_adjusted = extra_pct-12
    inspected = {
        'quote_age': (quote_age, quote_age_adjusted),
        'extra_pct': (extra_pct, extra_pct_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('更新报价并重新计价', 3, '由供应方按同含项重新报价', inspected)
    return None


def simulate_split_contract(readings, invalid):
    works, vendor_lag = readings[4], readings[5]
    if invalid.intersection(('works', 'vendor_lag')):
        return None
    if not (works>=8 and vendor_lag>=15):
        return None
    works_adjusted = works-5
    vendor_lag_adjusted = vendor_lag-11
    inspected = {
        'works': (works, works_adjusted),
        'vendor_lag': (vendor_lag, vendor_lag_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('分开劳务结构与响应', 2, '单列应急作业后再评估价款', inspected)
    return None


def simulate_signed_survey(readings, invalid):
    revisions, photos = readings[1], readings[2]
    if invalid.intersection(('revisions', 'photos')):
        return None
    if not (revisions>=4 and photos<=37):
        return None
    revisions_adjusted = revisions-2
    photos_adjusted = photos+5
    inspected = {
        'revisions': (revisions, revisions_adjusted),
        'photos': (photos, photos_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('改量签证改日见证', 2, '记录复查日期和两人签认', inspected)
    return None


def simulate_revalue_subset(readings, invalid):
    quote_age, works = readings[3], readings[4]
    if invalid.intersection(('quote_age', 'works')):
        return None
    if not (works>=9 and quote_age>=40):
        return None
    works_adjusted = works-4
    quote_age_adjusted = 20
    inspected = {
        'works': (works, works_adjusted),
        'quote_age': (quote_age, quote_age_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('校准报价和新增项', 3, '仅复核高值作业单', inspected)
    return None


def options(values, missing):
    measurements=tuple(values)
    unobserved=frozenset(missing)
    cases=(
        simulate_collect_evidence(measurements, unobserved),
        simulate_recap_quotation(measurements, unobserved),
        simulate_split_contract(measurements, unobserved),
        simulate_signed_survey(measurements, unobserved),
        simulate_revalue_subset(measurements, unobserved),
    )
    return tuple(action for action in cases if action is not None)
