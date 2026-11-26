from bisect import bisect_left
from math import exp


def monotone_blocks(samples):
    intervals = []
    for cut, risk, size in samples:
        intervals.append((cut, risk, size))
        while len(intervals) > 1:
            edge, success, count = intervals[-1]
            _, previous, mass = intervals[-2]
            if previous * count <= success * mass:
                break
            intervals[-2:] = [(edge, previous + success, mass + count)]
    return tuple(intervals)


def bucketize(rows, coordinate, prior):
    ordered = sorted((item.values[coordinate], item.outcome) for item in rows)
    unique = sorted({value for value, _ in ordered})
    cutpoints = sorted({unique[index * (len(unique)-1)//6] for index in range(1, 7)})
    by_interval = [[0.0, 0] for _ in cutpoints]
    for value, result in ordered:
        box = by_interval[bisect_left(cutpoints, value)]
        box[0] += result
        box[1] += 1
    return monotone_blocks((marker, score+3*prior, size+3) for marker, (score, size) in zip(cutpoints, by_interval, strict=True))


def fit_kernel(rows):
    prior = (sum(item.outcome for item in rows) + 2) / (len(rows) + 4)
    boxes = tuple(bucketize(rows, field, prior) for field in (0, 1, 2, 3, 4))
    return (prior, boxes), (('基准异常率', prior), ('保序箱数', sum(len(buckets) for buckets in boxes)),
                             ('票据总数', len(rows)))


def score_kernel(card, sample):
    base, cards = card
    adjustments = []
    for value, band in zip(sample.values, cards, strict=True):
        idx = min(len(band)-1, bisect_left(tuple(marker for marker, _, _ in band), value))
        adjustment = band[idx][1] / band[idx][2] - base
        adjustments.append(adjustment)
    score = base + sum(weight * value for weight, value in zip((.30,.12,.14,.12,.32), adjustments, strict=True))
    return score, tuple(adjustments)
