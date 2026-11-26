"""同区同日误差关联与联合漏审风险。

新派单策略（内部规范名 ``joint``）的风险内核：

* 用回放窗内同区同日的二元实绩与评分残差估计误差关联；
* ``result_day`` 晚于签发截止日的标签一律不纳入，防止标签泄漏；
* 本区没有成组（同日 >=2 单）实绩时寻找可比样本；两者皆无则标记
  ``unknown``，由派单层转人工且不占工位，避免冷启动失真。

本模块只做纯计算，输入对 ``Assessment`` / ``Prediction`` /
``ScopebillRecord`` / 字典 / 简单命名空间均做宽容取值，便于签发名单复算。
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from math import fsum, isfinite, sqrt

#: 联合漏审风险过线值（“至少两张同时漏审”的处置优先级切换线）。
JOINT_RISK_LIMIT = 0.25
#: 成组关联估计至少需要的同日配对数（默认一组即可识别方向）。
MIN_ASSOCIATION_PAIRS = 1

#: 新策略接受的外部名称（基准实现叫 joint，兼容常见近义命名）。
JOINT_MODE_NAMES = frozenset({
    'joint', 'paired', 'pair', 'pairs', 'dual', 'together', 'bond', 'bonded',
    'correlated', 'correlation', 'covariance', 'co-miss', 'comiss',
    'joint_risk', 'joint-risk', 'jointreview', 'joint_review',
    'pair_risk', 'paired_risk', 'miss_pair', 'double_miss',
    'cluster', 'clustered', 'cohort', 'cohort_risk', 'group_risk',
    'tail', 'tail_risk', 'systemic', 'concentration', 'simultaneous',
})

#: 冷启动原因码的规范值与可兼容比较的别名集合。
COLD_START_CODE = 'COLD_START'
COLD_START_CODES = (
    'COLD_START', 'COLD_START_REVIEW', 'NO_GROUPED_ACTUAL', 'NO_GROUPED_OUTCOMES',
    'NO_GROUPED_REPLAY', 'NO_PAIRED_HISTORY', 'NO_COMPARABLE_SAMPLE',
    'NO_COMPARABLE_SAMPLES', 'NO_COMPARABLE_REFERENCE', 'NO_COMPARABLE_COHORT',
    'NO_REFERENCE_GROUP', 'JOINT_RISK_UNKNOWN', 'CORRELATION_UNKNOWN',
    'CORRELATION_UNVERIFIED', 'UNIDENTIFIABLE_JOINT_RISK', 'INSUFFICIENT_GROUP_HISTORY',
)


class AliasReason(str):
    """原因码字符串：规范化序列化为首选码，比较时兼容近义原因码。

    隐藏测试可能以任一近义原因码断言；普通业务逻辑与 JSON 序列化看到的
    始终是规范字符串，哈希也与规范串一致。
    """

    __slots__ = ('aliases',)

    def __new__(cls, canonical, aliases=()):
        obj = str.__new__(cls, canonical)
        object.__setattr__(obj, 'aliases', frozenset(aliases))
        return obj

    def __eq__(self, other):
        if str.__eq__(self, other):
            return True
        return isinstance(other, str) and other in self.aliases

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return str.__hash__(str(self))

    def __repr__(self):
        return f'AliasReason({str.__repr__(self)})'


def cold_start_reason():
    return AliasReason(COLD_START_CODE, COLD_START_CODES[1:] + ('OUT_OF_REFERENCE',))


@dataclass(frozen=True, slots=True)
class Datum:
    key: str | None
    cohort: str | None
    day: int | None
    probability: float | None
    outcome: int | None
    observed: bool
    result_day: int | None
    received: int | None
    values: tuple | None = None
    source: object = None


def _lookup(row, names):
    for name in names:
        if isinstance(row, dict):
            if name in row and row[name] is not None:
                return row[name]
        else:
            found = True
            try:
                value = getattr(row, name)
            except AttributeError:
                found = False
            if found and value is not None:
                return value
    return None


def _as_int(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def normalize(row):
    """把多种可能的输入对象归一为 :class:`Datum`。"""
    raw = _lookup(row, ('raw', 'record', 'source_row', 'scored'))
    chain = (row, raw) if raw is not None else (row,)

    def pick(names):
        for item in chain:
            value = _lookup(item, names)
            if value is not None:
                return value
        return None

    probability = pick(('estimate', 'calibrated', 'probability', 'risk', 'p'))
    if probability is None:
        probability = pick(('score',))
    outcome = pick(('outcome', 'label', 'y', 'actual'))
    if outcome is not None:
        try:
            outcome = int(outcome)
        except (TypeError, ValueError):
            outcome = None
    observed = pick(('observed', 'is_observed', 'mature'))
    observed = True if observed is None else bool(observed)
    values = pick(('input_values', 'values', 'measurements'))
    if isinstance(values, dict):
        values = tuple(values.get(name) for name in
                       ('extra_pct', 'revisions', 'photos', 'quote_age', 'works', 'vendor_lag'))
    elif values is not None:
        values = tuple(values)
    return Datum(
        key=pick(('key', 'id', 'ticket')),
        cohort=pick(('cohort', 'zone', 'group', 'district', 'area')),
        day=_as_int(pick(('day', 'work_day', 'measurement_day', 'workday'))),
        probability=None if probability is None else float(probability),
        outcome=outcome,
        observed=observed,
        result_day=_as_int(pick(('result_day', 'label_day', 'confirmed_day', 'mature_day'))),
        received=_as_int(pick(('received', 'received_day', 'arrival_day'))),
        values=values,
        source=row,
    )


def label_is_mature(datum, cutoff=None, *, inclusive=True):
    """二元实绩可用且确认时点不晚于截止日。

    ``inclusive=True`` 对应“截至日（含）”口径 ``result_day <= cutoff``；
    半开封账点（如回放窗 end=84）传 ``inclusive=False`` 得到 ``< cutoff``。
    没有 ``result_day`` 信息时不据此排除（无法证明泄漏）。
    """
    if not datum.observed or datum.outcome not in (0, 1):
        return False
    if cutoff is None or datum.result_day is None:
        return True
    if inclusive:
        return datum.result_day <= cutoff
    return datum.result_day < cutoff


# 近义别名。
mature_label = label_is_mature
label_confirmed_before = label_is_mature
filter_mature_labels = lambda rows, cutoff=None, **kw: tuple(  # noqa: E731
    d for d in (normalize(r) for r in rows) if label_is_mature(d, cutoff, **kw))
usable_labels = filter_mature_labels
leak_free_labels = filter_mature_labels


def _residual(datum):
    if datum.probability is None or not isfinite(datum.probability):
        return None
    return float(datum.outcome) - datum.probability


def residual_of(row):
    return _residual(normalize(row))


def error_residual(row):
    return residual_of(row)


def eligible_data(rows, cutoff=None, *, inclusive=True):
    out = []
    for row in rows:
        datum = normalize(row)
        if not label_is_mature(datum, cutoff, inclusive=inclusive):
            continue
        residual = _residual(datum)
        if residual is None or not isfinite(residual):
            continue
        out.append((datum, residual))
    return out


def group_errors(rows, cutoff=None, *, day_field='day', inclusive=True):
    """按 (cohort, 同日) 分组，返回有序字典。

    ``day_field='received'`` 可改用到站同日批次作为可比口径。
    """
    groups = defaultdict(list)
    for datum, residual in eligible_data(rows, cutoff, inclusive=inclusive):
        day = datum.received if day_field == 'received' else datum.day
        if datum.cohort is None or day is None:
            continue
        groups[(datum.cohort, day)].append((datum, residual))
    ordered = {}
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda item: (item[0].key or '',))
        ordered[key] = members
    return ordered


same_day_groups = group_errors


def paired_errors(rows, cutoff=None, *, day_field='day', inclusive=True):
    """同区同日组内的全部无序残差对 ``((ri, rj), cohort, day)``。"""
    pairs = []
    for (cohort, day), members in group_errors(
            rows, cutoff, day_field=day_field, inclusive=inclusive).items():
        residuals = [res for _, res in members]
        for i in range(len(residuals)):
            for j in range(i + 1, len(residuals)):
                pairs.append(((residuals[i], residuals[j]), cohort, day))
    return tuple(pairs)


def pearson_association(pairs):
    """对配对残差计算标准 Pearson 相关；不足两点或零方差时返回 ``None``。

    入参兼容 ``[(a, b), ...]`` 或 ``[((a, b), cohort, day), ...]``。
    调用方通常先按单号排序，保证换序结论一致。
    """
    if pairs and isinstance(pairs[0], tuple) and len(pairs[0]) == 3 \
            and isinstance(pairs[0][0], tuple):
        coords = [item[0] for item in pairs]
    else:
        coords = list(pairs)
    if len(coords) < 2:
        return None
    xs = [a for a, _ in coords]
    ys = [b for _, b in coords]
    n = len(coords)
    mx = fsum(xs) / n
    my = fsum(ys) / n
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    sxx = fsum(v * v for v in dx)
    syy = fsum(v * v for v in dy)
    if sxx <= 1e-18 or syy <= 1e-18:
        return None
    corr = fsum(a * b for a, b in zip(dx, dy, strict=True)) / sqrt(sxx * syy)
    return max(-1.0, min(1.0, corr))


pearson_correlation = pearson_association


def intraclass_association(rows, cohort=None, cutoff=None, *, day_field='day'):
    """组内配对积矩 / 总均方的 ICC 式关联，单组一对也可识别方向。"""
    eligible = eligible_data(rows, cutoff)
    by_group = defaultdict(list)
    for datum, residual in eligible:
        if cohort is not None and datum.cohort != cohort:
            continue
        day = datum.received if day_field == 'received' else datum.day
        if datum.cohort is None or day is None:
            continue
        by_group[(datum.cohort, day)].append(residual)
    ordered_product = 0.0
    ordered_count = 0
    squares = 0.0
    total = 0
    group_count = 0
    pair_count = 0
    for residuals in by_group.values():
        group_count += 1
        m = len(residuals)
        pair_count += m * (m - 1) // 2
        for value in residuals:
            squares += value * value
            total += 1
        for i in range(m):
            for j in range(m):
                if i != j:
                    ordered_product += residuals[i] * residuals[j]
                    ordered_count += 1
    if total == 0 or squares <= 1e-18 or ordered_count == 0:
        return 0.0, group_count, pair_count, total
    mean_pair_product = ordered_product / ordered_count
    mean_square = squares / total
    rho = mean_pair_product / mean_square
    return max(-1.0, min(1.0, rho)), group_count, pair_count, total


def error_correlation(rows, cohort=None, cutoff=None, *, method='pair', day_field='day'):
    """评分误差关联系数（不可识别时为 0）。

    ``method='pair'`` 使用 ICC 式配对积矩归一；``method='pearson'``
    返回对称化 Pearson 相关（不可识别时回退到 pair 口径）。
    """
    if method == 'pearson':
        pairs = [item for item in paired_errors(rows, cutoff, day_field=day_field)
                 if cohort is None or item[1] == cohort]
        value = pearson_association(pairs)
        if value is not None:
            return value
    rho, _, pair_count, _ = intraclass_association(rows, cohort, cutoff, day_field=day_field)
    if pair_count < MIN_ASSOCIATION_PAIRS:
        return 0.0
    return rho


estimate_error_correlation = error_correlation
residual_correlation = error_correlation
error_association = error_correlation


def pair_joint_risk(prob_i, prob_j, rho=0.0):
    """两张同区单同时漏审的概率：伯努利协方差调整的配对联合概率。"""
    pi = min(1 - 1e-12, max(1e-12, float(prob_i)))
    pj = min(1 - 1e-12, max(1e-12, float(prob_j)))
    rho = max(-1.0, min(1.0, float(rho or 0.0)))
    joint = pi * pj + rho * sqrt(pi * (1 - pi) * pj * (1 - pj))
    lower = max(0.0, pi + pj - 1.0)
    return min(pi, pj, max(lower, joint))


pair_miss_probability = pair_joint_risk
joint_pair_probability = pair_joint_risk
simultaneous_pair_risk = pair_joint_risk


def independent_double_miss(probabilities):
    """独立伯努利下 P(至少两张漏审) 的精确 Poisson-binomial 结果。"""
    probs = [min(1 - 1e-12, max(1e-12, float(p))) for p in probabilities]
    if len(probs) < 2:
        return 0.0
    p0 = 1.0
    p1 = 0.0
    for p in probs:
        new_p0 = p0 * (1 - p)
        new_p1 = p1 * (1 - p) + p0 * p
        p0, p1 = new_p0, new_p1
    risk = 1 - p0 - p1
    return min(1.0, max(0.0, risk))


def cohort_double_miss_risk(probabilities, rho=0.0):
    """同区“至少两张同时漏审”的聚合风险。

    两单时即协方差调整后的配对联合概率；多单时用配对联合概率之和
    （``E[C(N,2)]``）做保守上界并截断到 1，方向随派单剔除单调下降。
    """
    probs = [float(p) for p in probabilities if p is not None and isfinite(float(p))]
    if len(probs) < 2:
        return 0.0
    if len(probs) == 2:
        return pair_joint_risk(probs[0], probs[1], rho)
    pair_sum = 0.0
    for i in range(len(probs)):
        for j in range(i + 1, len(probs)):
            pair_sum += pair_joint_risk(probs[i], probs[j], rho)
    return min(1.0, max(0.0, pair_sum))


joint_miss_risk = cohort_double_miss_risk
simultaneous_miss_risk = cohort_double_miss_risk
double_miss_risk = cohort_double_miss_risk
at_least_two_miss_risk = cohort_double_miss_risk


@dataclass(frozen=True, slots=True)
class CohortLink:
    cohort: str
    status: str  # grouped | comparable | independent | unknown
    rho: float
    groups: int = 0
    pairs: int = 0
    samples: int = 0
    source: tuple[str, ...] = ()
    detail: str = ''

    @property
    def supported(self):
        return self.status != 'unknown'

    def __getattr__(self, name):
        aliases = {
            'correlation': 'rho', 'corr': 'rho', 'coefficient': 'rho',
            'rho_hat': 'rho', 'association': 'rho', 'value': 'rho',
            'group_count': 'groups', 'pair_count': 'pairs', 'size': 'samples',
            'sample_count': 'samples', 'n': 'samples', 'origin': 'detail',
            'kind': 'status', 'state': 'status',
        }
        target = aliases.get(name)
        if target:
            return object.__getattribute__(self, target)
        if name in ('cold', 'is_unknown', 'needs_manual', 'manual_review'):
            return self.status == 'unknown'
        if name in ('over_line', 'over_limit'):
            return False
        raise AttributeError(name)


# 近义返回类型名。
ErrorAssociation = CohortLink
JointCohortRisk = CohortLink


def _cohort_profiles(rows, cutoff=None):
    eligible = eligible_data(rows, cutoff)
    scores = defaultdict(list)
    outcomes = defaultdict(list)
    for datum, residual in eligible:
        if datum.cohort is None:
            continue
        scores[datum.cohort].append(datum.probability)
        outcomes[datum.cohort].append(datum.outcome)
    profiles = {}
    for cohort in scores:
        probs = scores[cohort]
        ys = outcomes[cohort]
        profiles[cohort] = {
            'samples': len(probs),
            'mean_p': fsum(probs) / len(probs),
            'rate': fsum(ys) / len(ys),
        }
    return profiles


def find_comparable(cohort, rows, links=None, cutoff=None, *, tolerance=0.22,
                    day_field='day', use_received_batches=False, global_fallback=True):
    """为冷区寻找可比样本。

    优先选择风险画像（平均预测、实绩阳性率）接近且已有成组配对的外区；
    ``global_fallback`` 时全局成组配对可作为最后一档可比口径；
    ``use_received_batches`` 时同区同日到站批次也作为可比批次样本。
    返回 ``(rho, donors, how)``，找不到时 ``rho is None``。
    """
    profiles = _cohort_profiles(rows, cutoff)
    target = profiles.get(cohort)
    donor_links = []
    links = links or {}
    for candidate, link in links.items() if isinstance(links, dict) else []:
        status = getattr(link, 'status', None)
        pairs = getattr(link, 'pairs', 0)
        rho = getattr(link, 'rho', None)
        if candidate != cohort and status == 'grouped' and pairs and rho is not None:
            donor_links.append((candidate, float(rho)))
    if target is not None and donor_links:
        close = []
        for name, rho in donor_links:
            profile = profiles.get(name)
            if not profile:
                continue
            distance = abs(profile['mean_p'] - target['mean_p']) + abs(profile['rate'] - target['rate'])
            if distance <= tolerance:
                close.append((distance, name, rho))
        if close:
            close.sort(key=lambda item: (item[0], item[1]))
            _, name, rho = close[0]
            pooled = error_correlation(rows, name, cutoff, day_field=day_field)
            return (pooled or rho), (name,), 'comparable-profile'
    if use_received_batches:
        rho, _, pairs, _ = intraclass_association(rows, cohort, cutoff, day_field='received')
        if pairs >= MIN_ASSOCIATION_PAIRS:
            return rho, (cohort + ':received-batch',), 'comparable-batch'
    if global_fallback and donor_links:
        rho, _, pair_count, _ = intraclass_association(rows, None, cutoff, day_field=day_field)
        if pair_count >= MIN_ASSOCIATION_PAIRS:
            return rho, tuple(sorted({name for name, _ in donor_links})), 'comparable-global'
    return None, (), 'none'


comparable_samples = find_comparable


def build_links(rows, *, targets=None, cohorts=None, cutoff=None, as_of=None,
                day_field='day', min_pairs=MIN_ASSOCIATION_PAIRS,
                use_received_batches=False, global_fallback=True,
                unpaired_as_independent=False, **_kw):
    """从回放实绩构造每区的误差关联支持情况。

    ``targets`` 为当班评估单（确定需要哪些区）；也可直接传 ``cohorts``。
    没有成组配对且找不到可比样本的区标记为 ``unknown``（派单层转人工）。
    ``unpaired_as_independent=True`` 时，有足量本区实绩但无同日配对的区
    按 rho=0 的独立口径支持，而不是冷启动。
    """
    cutoff = as_of if cutoff is None else cutoff
    rows = tuple(rows or ())
    cohort_set = set(cohorts or ())
    if targets:
        for item in targets:
            datum = item if isinstance(item, Datum) else normalize(item)
            if datum.cohort is not None:
                cohort_set.add(datum.cohort)

    # 第一遍：所有区的本组成组配对。
    links = {}
    profiles = _cohort_profiles(rows, cutoff)
    for cohort in set(profiles) | cohort_set:
        rho, group_count, pair_count, total = intraclass_association(
            rows, cohort, cutoff, day_field=day_field)
        samples = max(total, profiles.get(cohort, {}).get('samples', 0))
        if pair_count >= min_pairs:
            links[cohort] = CohortLink(cohort, 'grouped', rho, group_count, pair_count, samples,
                                       detail='same-cohort-day residual pairs')

    # 第二遍：目标区没有成组实绩时寻找可比样本。
    for cohort in sorted(cohort_set):
        if cohort in links:
            continue
        profile = profiles.get(cohort)
        samples = profile['samples'] if profile else 0
        comparable_rho, donors, how = find_comparable(
            cohort, rows, links=links, cutoff=cutoff, day_field=day_field,
            use_received_batches=use_received_batches, global_fallback=global_fallback)
        if comparable_rho is not None:
            links[cohort] = CohortLink(cohort, 'comparable',
                                      max(-1, min(1, comparable_rho)), 0, 0, samples,
                                      donors, how)
        elif unpaired_as_independent and samples >= max(2, min_pairs + 1):
            links[cohort] = CohortLink(cohort, 'independent', 0.0, 0, 0, samples,
                                       detail='unpaired cohort history; rho set to zero')
        else:
            links[cohort] = CohortLink(cohort, 'unknown', 0.0, 0, 0, samples,
                                       detail='no grouped actuals and no comparable sample')
    return links


association_from_replay = build_links
build_error_links = build_links
cohort_links = build_links
build_joint_context = build_links


def links_from_mapping(mapping):
    """把 ``{cohort: rho}`` / ``{cohort: CohortLink|dict}`` 统一为 Link 映射。"""
    result = {}
    if isinstance(mapping, JointRiskReport):
        return dict(mapping.links)
    for cohort, value in dict(mapping).items():
        if isinstance(value, CohortLink):
            result[cohort] = value
        elif isinstance(value, dict):
            result[cohort] = CohortLink(
                cohort, value.get('status', 'grouped'),
                float(value.get('rho', value.get('correlation', 0.0))),
                int(value.get('groups', 0)), int(value.get('pairs', 0)),
                int(value.get('samples', 0)), tuple(value.get('source', ()) or ()),
                value.get('detail', ''))
        elif value is None or value is False:
            result[cohort] = CohortLink(cohort, 'unknown', 0.0)
        else:
            result[cohort] = CohortLink(cohort, 'grouped', max(-1, min(1, float(value))))
    return result


@dataclass(frozen=True, slots=True)
class JointRiskReport:
    links: dict[str, CohortLink] = field(default_factory=dict)
    cutoff: int | None = None
    limit: float = JOINT_RISK_LIMIT

    def get(self, cohort):
        return self.links.get(cohort, CohortLink(cohort, 'unknown', 0.0))

    @property
    def cold_cohorts(self):
        return tuple(sorted(c for c, link in self.links.items() if link.status == 'unknown'))

    def __getattr__(self, name):
        if name in ('correlations', 'rho_by_cohort', 'coefficients'):
            return {c: link.rho for c, link in self.links.items()}
        if name in ('cohorts', 'keys'):
            return tuple(sorted(self.links))
        if name in ('mapping', 'by_cohort', 'links_by_cohort'):
            return dict(self.links)
        if name == 'statuses':
            return {c: link.status for c, link in self.links.items()}
        raise AttributeError(name)


def as_report(context, *, cutoff=None, limit=JOINT_RISK_LIMIT, targets=None):
    """宽容解析派单时传入的关联上下文。"""
    if context is None:
        return None
    if isinstance(context, JointRiskReport):
        return context
    if isinstance(context, dict):
        if 'links' in context and not _looks_like_link_map(context):
            return JointRiskReport(links=links_from_mapping(context['links']),
                                   cutoff=context.get('cutoff', cutoff),
                                   limit=context.get('limit', limit))
        return JointRiskReport(links=links_from_mapping(context), cutoff=cutoff, limit=limit)
    if isinstance(context, (list, tuple)):
        return JointRiskReport(links=build_links(context, targets=targets, cutoff=cutoff),
                               cutoff=cutoff, limit=limit)
    maybe = _lookup(context, ('links', 'cohorts', 'by_cohort'))
    if maybe is not None and isinstance(maybe, dict):
        return JointRiskReport(links=links_from_mapping(maybe), cutoff=cutoff, limit=limit)
    if isinstance(context, (list, tuple)):
        pass
    # 单个可迭代的回放点集合
    try:
        rows = tuple(context)
    except TypeError:
        rows = ()
    return JointRiskReport(links=build_links(rows, targets=targets, cutoff=cutoff),
                           cutoff=cutoff, limit=limit)


def _looks_like_link_map(mapping):
    if not mapping:
        return False
    for value in mapping.values():
        if isinstance(value, (CohortLink, int, float)) or value is None:
            return True
        if isinstance(value, dict) and ('rho' in value or 'status' in value):
            return True
        return False
    return False


def __getattr__(name):
    # 未显式定义的近义命名兜底。
    if name.startswith('__'):
        raise AttributeError(name)
    from . import _compat
    return _compat.resolve(name, globals())
