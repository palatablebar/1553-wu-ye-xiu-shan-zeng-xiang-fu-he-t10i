from bisect import bisect_right
from collections import defaultdict
from math import exp, fsum, isfinite, log, log1p
from statistics import mean

from .contracts import Verification, Assessment, CalibrationRow, ModelReport
from .slices import replay_slices



def clip_risk(probability):
    return min(1-1e-12,max(1e-12,probability))


def sigmoid(log_odds):
    if log_odds < 0:
        factor = exp(log_odds)
        return factor / (1+factor)
    return 1/(1+exp(-log_odds))


def logit(probability):
    clipped = clip_risk(probability)
    return log(clipped)-log1p(-clipped)


def stable_loss(probability, outcome):
    estimate = clip_risk(probability)
    return -log(estimate) if outcome else -log1p(-estimate)





def scorecard_shrinkage(checks):
    base = (sum(mark.outcome for mark in checks) + 1) / (len(checks)+2)
    spread = fsum((mark.score-base)**2 for mark in checks)
    margin = fsum((mark.score-base)*(mark.outcome-base) for mark in checks)
    gain = min(1.,max(.08,margin/(spread+.08*len(checks))))
    return (base,gain)


def calibrated_scorecard_shrinkage(model, p):
    centre, trust = model
    return p*trust+centre*(1-trust)


def prepare_verification(pairs, *, coverage=.85):
    mature = [entry for entry in pairs if entry.observed and entry.outcome is not None]
    if any(not isfinite(entry.score) or entry.outcome not in (0,1) for entry in mature):
        raise ValueError('风险校准要求有限预测和二元实绩')
    positives = sum(entry.outcome == 1 for entry in mature)
    if len(mature) < 8 or positives in (0,len(mature)):
        return Verification('sparse-risk', (), len(mature), positives)
    return Verification('scorecard_shrinkage', scorecard_shrinkage(mature), len(mature), positives)


def check_point(scored, anchor):
    if not isfinite(scored.score):
        raise ValueError('预测风险必须有限')
    value = clip_risk(scored.score)
    if not anchor.parameters:
        return Assessment(scored,value,None,None,True)
    return Assessment(scored, calibrated_scorecard_shrinkage(anchor.parameters,value),None,None,False)


def validate_predictions(scored, prepared):
    return tuple(check_point(sample, prepared) for sample in scored)


def reliability_rows(cases):
    groups = defaultdict(list)
    for raw, label in cases:
        groups[min(3,int(raw*4))].append((raw,label))
    for position in range(4):
        group = groups[position]
        yield CalibrationRow(position, mean(x[0] for x in group) if group else None,
                             mean(x[1] for x in group) if group else None, len(group))


def performance(assessments):
    review = [(point.estimate,point.raw.outcome) for point in assessments if point.raw.observed and point.raw.outcome is not None]
    if not review:
        return ModelReport('NO_MATURE_RESULT',0,None,None,(),None)
    error = mean(abs(estimate-outcome) for estimate,outcome in review)
    positive = sum(outcome==1 for _,outcome in review)
    return ModelReport('READY' if positive else 'NO_POSITIVES',len(review),error,
                       mean(stable_loss(*item) for item in review),tuple(reliability_rows(review)),positive)


def calibration_evidence(report):
    reads = [{'核验':report.status,'样本':report.count,'平均绝对误差':report.mae,'对数损失':report.error,'阳性例':report.auxiliary}]
    reads += [{'分箱':f'{row.index*25}–{(row.index+1)*25}%', '样本':row.count,
               '预测均值':row.predicted,'实绩均值':row.observed} for row in report.buckets]
    return reads


def sector_replay(checked, line):
    return replay_slices(checked,line,risk_model=True)


def boundary_diagnostics(checks, threshold):
    points = [(row.estimate>=threshold,row.raw.outcome==1) for row in checks if row.raw.observed and row.raw.outcome is not None]
    return {'临界判断':'增项核减', '实绩超线':sum(label for _,label in points),
            '估计超线':sum(pred for pred,_ in points), '额外复测':sum(p and not y for p,y in points),
            '漏查':sum(y and not p for p,y in points)}
