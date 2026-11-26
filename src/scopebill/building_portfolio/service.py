from collections import Counter
from math import fsum
from statistics import median, quantiles

from .contracts import ShiftReport, ReferenceProfile
from .operating_reference import evaluate_domains


def seven_grid(raw):
    if len(raw)==1:
        return tuple(raw)*7
    return tuple(quantiles(raw,n=8,method='inclusive'))


def fit_baseline(features, signature):
    if not features:
        raise ValueError('缺少参考表格量测')
    bands = tuple(seven_grid(column) for column in zip(*(row.values for row in features),strict=True))
    zones = {entry.cohort for entry in features}
    return ReferenceProfile(signature,bands,zones,len(features))


def distribution_movement(old, later):
    total = fsum(abs(left-right) for left,right in zip(old,later,strict=True))
    span = max(.25,old[5]-old[1])
    return total / (7*span)


def scan_current(reference, prediction, signature):
    if reference.signature!=signature:
        raise ValueError('分位格已陈旧，需重建历史基准')
    day = list(prediction)
    if not day:
        return ShiftReport(0,(),(),(),'NO_CURRENT_RECORDS')
    current = tuple(seven_grid(row) for row in zip(*(item.values for item in day),strict=True))
    gap = [(label,distribution_movement(old,new)) for label,old,new in zip(('增项占比', '单位作业的改量频率', '每份证据对应作业', '报价与交割延迟', '未复核工作量'),reference.bands,current,strict=True)]
    new_places = {row.cohort for row in day} - reference.cohorts
    split = [row.key for row in day if row.cohort in new_places or len(row.excursions)>=2 or len(row.missing)>=2]
    return ShiftReport(len(day),tuple(sorted(gap,key=lambda item:-item[1])),tuple(sorted(new_places)),tuple(sorted(split)),
                       'SHIFT_REVIEW' if new_places or any(change>.58 for _,change in gap) else 'STABLE')



def coverage_by_group(calibration, validation):
    past = Counter(item.cohort for item in calibration)
    current = Counter(item.cohort for item in validation)
    return tuple((key,past[key],current[key]) for key in sorted(past.keys()|current.keys()))


def shift_evidence(current, coverage):
    names = dict(zip(('price_pressure', 'quantity_change', 'evidence_gap', 'late_offer', 'unconfirmed_scope'),('增项占比', '单位作业的改量频率', '每份证据对应作业', '报价与交割延迟', '未复核工作量'),strict=True))
    new = set(current.novel)
    table = [{'检测项':names.get(field,field), '分位位移':round(evidence,4)} for field,evidence in current.signals]
    table.extend({'检测项':unit, '校准单数':old,'本班单数':seen,'现场': '未登记' if unit in new else '已登记'}
                 for unit,old,seen in coverage)
    return table


def shop_floor_shift(reference, current):
    measures = evaluate_domains(reference,current)
    return sorted(measures,key=lambda line:(-line['越线量'],line['观察维度']))
