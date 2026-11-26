from collections import defaultdict
from math import fabs, fsum
from statistics import mean, median

from .monotone_model import score_kernel


def sample_change_count(forms):
    details=defaultdict(list)
    for change in forms:
        details[change.cohort].append((change.day,change.outcome))
    return details


def contract_check_rate(historical,order):
    seen=sorted(historical.get(order.cohort,()))[-15:]
    if not seen:
        seen=[entry for book in historical.values() for entry in book]
    return (sum(change for _,change in seen)+.8)/(len(seen)+1.6)


def baseline_review(fit, training, replay):
    control = sample_change_count(training)
    by_cohort = defaultdict(list)
    for result in replay:
        if result.observed and result.outcome in (0,1):
            forecast, _ = score_kernel(fit.parameters,result)
            local = contract_check_rate(control, result)
            error_a, error_b = (forecast-result.outcome)**2, (local-result.outcome)**2
            by_cohort[result.cohort].append((error_a,error_b,int(result.outcome),forecast,local))
    report = []
    for location, comparisons in sorted(by_cohort.items()):
        samples = len(comparisons)
        expected = fsum(row[3] for row in comparisons)
        confirmed = sum(row[2] for row in comparisons)
        misses = sum(row[2] and row[3] < 0.5 for row in comparisons)
        base_misses = sum(row[2] and row[4] < 0.5 for row in comparisons)
        before = fsum(row[1] for row in comparisons) / samples
        after = fsum(row[0] for row in comparisons) / samples
        report.append({'回放组':location,'实绩数':samples,'估计代价':round(after,4),'业务基线代价':round(before,4),
                       '基线':'同类片区上一周期核减率','预测阳性总量':round(expected,3),'实绩阳性数':confirmed,
                       '模型漏判':misses,'基线漏判':base_misses,
                       '相对 Brier 改善':round(1-after/before,4) if before else None})
    return report
