from collections import Counter
from math import isfinite


def accountable_plan(rows, actual_balance, starting_capacity):
    seen = set()
    counts = Counter()
    total = 0
    for row in rows:
        if row['key'] in seen:
            raise ArithmeticError('复核凭证的关联单号不唯一')
        key = row['key']
        seen.add(key)
        state = row['state']
        counts[state] += 1
        if state == '已分派':
            total += row['cost']
        if not isfinite(row['estimate']):
            raise ArithmeticError('非有限估计不能签发')
    if total + actual_balance != starting_capacity:
        raise ArithmeticError('处置清册与工位余额不符')
    return counts, total


def register_price_evidence(measurements, estimate):
    extra_pct = measurements['extra_pct']
    revisions = measurements['revisions']
    photos = measurements['photos']
    quote_age = measurements['quote_age']
    works = measurements['works']
    vendor_lag = measurements['vendor_lag']
    return {
        '每项签证修订': round(revisions/works, 3),
        '施工方延迟天数': round(vendor_lag/24, 3),
        '修订次数乘报价日': round(revisions*quote_age, 3),
        '高额无证据暴露': round(extra_pct/(1+photos), 3),
        '复核代价指标': round(extra_pct/60 + works/(1+photos)/11 + revisions/31, 4),
    }


def document_control(rows):
    register = []
    for row in rows:
        if row['state'] not in {'已分派', '暂停', '人工判读'}:
            continue
        note = register_price_evidence(row['measurements'], row['estimate'])
        register.append({'单号': row['key'], '区段': row['zone'], '处置': row['state'], **note})
    return register
