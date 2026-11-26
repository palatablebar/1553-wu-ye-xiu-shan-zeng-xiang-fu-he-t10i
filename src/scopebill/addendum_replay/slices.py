from math import sqrt, fsum
from collections import defaultdict


def groups_for_addendum_replay(raw):
    extra_pct, revisions, photos, quote_age, works, vendor_lag = raw
    if extra_pct>=25:
        yield '四分之一以上增项'
    if photos<works:
        yield '未达一项一图'
    if quote_age>58:
        yield '报价进入复索'
    if revisions>=8:
        yield '单据反复改量'
    if vendor_lag>=54:
        yield '施工方回应延时'

def matured_observations(predictions):
    groups = defaultdict(list)
    for result in predictions:
        sample = result.raw
        if not sample.observed or sample.outcome is None:
            continue
        for label in groups_for_addendum_replay(sample.input_values):
            groups[label].append((result.estimate,int(sample.outcome)))
    return groups


def wilson(positives, size):
    if not size:
        return None, None
    z = 1.959964
    expected = positives / size
    centre = (expected + z*z/(2*size)) / (1 + z*z/size)
    distance = z * sqrt((expected*(1-expected) + z*z/(4*size))/size) / (1+z*z/size)
    return round(max(0,centre-distance),4),round(min(1,centre+distance),4)


def replay_slices(points, threshold, *, risk_model=True):
    by_segment = matured_observations(points)
    scorecards = []
    for label in ('四分之一以上增项', '未达一项一图', '报价进入复索', '单据反复改量', '施工方回应延时'):
        cases = by_segment[label]
        n = len(cases)
        if n==0:
            scorecards.append({'难点':label,'实绩数':n,'状态':'未取得二元实绩'})
            continue
        alarms = [(p,y) for p,y in cases if p>=threshold]
        hit = sum(y for _,y in alarms)
        positive = sum(y for _,y in cases)
        lower,upper = wilson(hit,len(alarms))
        coverage = hit/positive if positive else None
        scorecards.append({'难点':label,'实绩数':n,'复核命中':hit,'漏判':positive-hit,'复核过量':len(alarms)-hit,
                           '命中率区间下界':lower,'命中率区间上界':upper,'阳性召回':coverage,
                           'Brier 均分':round(fsum((p-y)**2 for p,y in cases)/n,4)})
    return scorecards
