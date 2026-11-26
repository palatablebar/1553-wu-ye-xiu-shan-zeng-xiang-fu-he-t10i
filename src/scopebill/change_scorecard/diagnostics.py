from math import exp, log, fsum, sqrt
from statistics import median, mean, quantiles

from .monotone_model import score_kernel



def explain_change_scorecard(fit, calibration, replay, live):
    prior, tables = fit.parameters
    exposures = ('增项占比','改量频率','见证缺口','报价等待','未见证暴露')
    check = []
    for name, levels in zip(exposures,tables,strict=True):
        lower = None
        previous = 0.0
        for step, (threshold, success, mass) in enumerate(levels):
            score = success / mass
            if score + 1e-12 < previous:
                raise ArithmeticError('增项评分保序约束失效')
            check.append({'增项特征':name, '保序层':step+1,'入层标准值':lower,'出层标准值':round(threshold,3),
                          '本层风险':round(score,4),'相对预估':round(score-prior,4),'平滑样本':mass})
            previous = score
            lower = round(threshold,3)
    return check
