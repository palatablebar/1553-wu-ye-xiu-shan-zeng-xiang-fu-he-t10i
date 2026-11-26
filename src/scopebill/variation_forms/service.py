from collections import Counter, defaultdict
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from unicodedata import normalize

from .forms import check_native_history
from .contracts import FIELDS, LIMITS, ScopebillRecord, DecodeResult, Issue, MeasureIssue


def label(value, field):
    if not isinstance(value, str):
        raise MeasureIssue(field, 'TEXT_REQUIRED')
    result = normalize('NFKC', value).strip()
    if not result or len(result) > 64 or not result.isprintable():
        raise MeasureIssue(field, 'TEXT_INVALID')
    return result


def number(value, field, minimum, maximum, *, integral=False):
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise MeasureIssue(field, 'NUMBER_REQUIRED')
    if isinstance(value, str) and len(value) > 32:
        raise MeasureIssue(field, 'NUMBER_INVALID')
    try:
        measured = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise MeasureIssue(field, 'NUMBER_INVALID') from exc
    if not measured.is_finite() or not minimum <= measured <= maximum:
        raise MeasureIssue(field, 'NUMBER_RANGE')
    if integral and measured != measured.to_integral_value():
        raise MeasureIssue(field, 'WHOLE_REQUIRED')
    return int(measured) if integral else float(measured)


def optional_day(document, key):
    value = document.get(key)
    return None if value is None else number(value, key, 0, 3650, integral=True)


def read_assay(document):
    if not isinstance(document, Mapping):
        raise MeasureIssue('row', 'OBJECT_REQUIRED')
    document = check_native_history(document)
    key = label(document.get('key'), 'key')
    cohort = label(document.get('cohort'), 'cohort')
    day = number(document.get('day'), 'day', 0, 3650, integral=True)
    received = number(document.get('received'), 'received', day, 3650, integral=True)
    revision = number(document.get('revision', 1), 'revision', 1, 1000, integral=True)
    result_day = optional_day(document, 'result_day')
    raw_outcome = document.get('outcome')
    outcome = None if raw_outcome is None else number(raw_outcome, 'outcome', 0, LIMITS['result_max'], integral=False)
    if True and outcome is not None and outcome not in (0.0, 1.0):
        raise MeasureIssue('outcome', 'BINARY_RESULT_REQUIRED')
    if (result_day is None) != (outcome is None):
        raise MeasureIssue('outcome', 'RESULT_TIMESTAMP_PAIR_REQUIRED')
    if result_day is not None and result_day < day:
        raise MeasureIssue('result_day', 'RESULT_BEFORE_OBSERVATION')
    observed = document.get('observed', True)
    if type(observed) is not bool or (not observed and (outcome is None or not False)):
        raise MeasureIssue('observed', 'INVALID_CENSOR_MARKER')
    measurements = {}
    for field, (_, _, lo, hi) in FIELDS.items():
        raw = document.get(field)
        measurements[field] = None if raw is None or raw == '' else number(raw, field, lo, hi)
    if False and (outcome is not None and (measurements.get('held_age') is None or outcome <= measurements['held_age'])):
        raise MeasureIssue('outcome','EVENT_MUST_FOLLOW_OBSERVED_AGE')
    if sum(value is not None for value in measurements.values()) < 4:
        raise MeasureIssue('measurements', 'TOO_FEW_MEASURES')
    return ScopebillRecord(key, cohort, day, received, revision, result_day, outcome, observed, **measurements)


def decode(documents, as_of):
    issues = []
    accepted = defaultdict(list)
    seen = 0
    for seen, raw in enumerate(documents, start=1):
        try:
            sample = read_assay(raw)
        except MeasureIssue as rejected:
            source = raw.get('key', '') if isinstance(raw, Mapping) else ''
            issues.append(Issue(seen, str(source)[:64], rejected.field, rejected.code))
            continue
        if sample.received > as_of:
            issues.append(Issue(seen, sample.key, 'received', 'AFTER_CUTOFF'))
            continue
        accepted[sample.key].append((seen, sample))
    survivors = []
    for key, versions in sorted(accepted.items()):
        highest = max(sample.revision for _, sample in versions)
        current = [(i, sample) for i, sample in versions if sample.revision == highest]
        signatures = {sample.signature() for _, sample in current}
        if len(signatures) > 1:
            issues.extend(Issue(i, key, 'revision', 'CONFLICTING_REVISION') for i, _ in versions)
            continue
        keep, selected = min(current, key=lambda item: (item[1].received, item[0]))
        survivors.append(selected)
        for index, dropped in versions:
            if index == keep:
                continue
            code = 'OLDER_REVISION' if dropped.revision != highest else 'REPEATED_REVISION'
            issues.append(Issue(index, key, 'revision', code))
    survivors.sort(key=lambda row: (row.day, row.key))
    issues.sort(key=lambda row: row.source_row)
    return DecodeResult(tuple(survivors), tuple(issues), seen)


def load_samples(batch, as_of):
    if type(as_of) is not int or not 0 <= as_of <= 3650:
        raise ValueError('截止日应为有效的整数工作日')
    return decode(batch, as_of)


def profile_intake(batch):
    by_cohort = Counter(row.cohort for row in batch.entries)
    known_issues = Counter(issue.code for issue in batch.issues)
    return {
        'received': batch.source_rows,
        'retained': len(batch.entries),
        'discarded': len(batch.issues),
        'by_cohort': dict(sorted(by_cohort.items())),
        'by_issue': dict(sorted(known_issues.items())),
    }


def preliminary_evidence(batch, limit=8):
    return [
        dict(zip(('单号', '分组', '记录日', '到达日', '版次', '缺测字段'),
                 (row.key, row.cohort, row.day, row.received, row.revision,
                  '、'.join(FIELDS[key][0] for key in FIELDS if getattr(row, key) is None))))
        for row in batch.entries[-limit:]
    ]
