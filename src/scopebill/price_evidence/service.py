from .work_order import check_price_evidence as site_checklist
from collections import Counter, defaultdict
from dataclasses import asdict
from hashlib import blake2s, sha256
from json import dumps

from .control import accountable_plan, document_control
from .contracts import BatchReceipt, LedgerCheck, POLICY_VERSION
from ..survey_budget.joint_risk import (
    JOINT_RISK_LIMIT, as_report, cohort_double_miss_risk, links_from_mapping,
)


def emit_bytes(value):
    return dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()


def data_fingerprint(records):
    per_record = Counter(sha256(emit_bytes(row)).hexdigest() for row in records)
    return sha256(emit_bytes(sorted(per_record.items()))).hexdigest()


def policy_fingerprint(capacity, mode, feature_id, model_kind):
    contract = {'rule':POLICY_VERSION,'strategy':mode,'quantity':capacity,'features':feature_id,'model':model_kind}
    return blake2s(emit_bytes(contract),digest_size=8).hexdigest()


def check_flow(intake, windows, dispatched):
    expected = Counter(note.key for note in windows.live)
    outcome = Counter(entry.key for entry in dispatched.jobs)
    if expected != outcome:
        raise ArithmeticError('当班单据和执行单不一致')
    actual_used = defaultdict(int)
    phases = Counter()
    for item in dispatched.jobs:
        phases[item.state] += 1
        if item.state=='已分派':
            actual_used[item.cohort] += item.cost
    if actual_used != dict(dispatched.used_by_group):
        raise ArithmeticError('各区记录的任务工位数不一致')
    spend = sum(actual_used.values())
    if sum(len(rows) for _,rows in windows.partitions()) + len(windows.excluded) != len(intake.entries):
        raise ArithmeticError('成熟窗口记录和进站单据数不同')
    if len(intake.entries) + len(intake.issues) != intake.source_rows:
        raise ArithmeticError('进站隔离行缺失')
    return LedgerCheck(intake.source_rows,len(intake.issues),len(windows.excluded),len(expected),
                       dispatched.capacity,spend,dispatched.balance,tuple(sorted(phases.items())))


def close_batch(dataset,intake,windows,dispatched,feature_id,model_kind,mode,
                links=None, **options):
    summarized=check_flow(intake,windows,dispatched)
    origin=data_fingerprint(dataset)
    policy=policy_fingerprint(dispatched.capacity,mode,feature_id,model_kind)
    entries=tuple((row.key,row.state,row.cost,row.reason,row.estimate) for row in dispatched.jobs)
    with_rows=tuple(sha256(emit_bytes(row)).hexdigest() for row in entries)
    signed_risk = options.pop('signed_risk', None)
    if signed_risk is None:
        try:
            signed_risk = recompute_signed_risk(dispatched, links=links)
        except Exception:
            signed_risk = None
    stamp=blake2s(emit_bytes((origin,policy,with_rows,asdict(summarized))),digest_size=8).hexdigest()
    return BatchReceipt(stamp,origin,policy,summarized,entries,signed_risk)


def compare(before, after):
    old = {row[0]: row[1:] for row in before.decisions}
    current = {row[0]: row[1:] for row in after.decisions}
    new = current.keys() - old.keys()
    obsolete = old.keys() - current.keys()
    changed = {key for key in old.keys() & current.keys() if old[key] != current[key]}
    return {'新增': tuple(sorted(new)), '移出': tuple(sorted(obsolete)), '变更': tuple(sorted(changed)),
            '策略变化': before.policy_hash != after.policy_hash, '样本变化': before.batch_hash != after.batch_hash}


def reconciliation_evidence(receipt):
    ledger = receipt.totals
    rows = [{'核对项': '原始记录', '数量': ledger.raw}, {'核对项': '入站隔离', '数量': ledger.isolated},
            {'核对项': '窗口隔离', '数量': ledger.mature_excluded}, {'核对项': '当班对象', '数量': ledger.scored},
            {'核对项': '已用额度', '数量': ledger.resource_used}, {'核对项': '额度结余', '数量': ledger.balance}]
    rows.extend({'核对项': state, '数量': count} for state, count in ledger.states)
    return rows


def sign_field_evidence(rows, allocation):
    counts, spent = accountable_plan(rows, allocation.balance, allocation.capacity)
    if dict(counts) != dict(Counter(job.state for job in allocation.jobs)):
        raise ArithmeticError('展示单据和签发方案的处置统计不符')
    selected = {row['key']: row['cost'] for row in rows if row['state'] == '已分派'}
    original = {job.key: job.cost for job in allocation.jobs if job.state == '已分派'}
    if selected != original:
        raise ArithmeticError('分派凭证与作业单互相矛盾')
    return {'工位使用':spent, '执行业务单':document_control(rows)}


def intervention_summary(rows):
    actions = {}
    for record in rows:
        for sample in record['alternatives']:
            label = sample['情形']
            observed = actions.setdefault(label,[0,0,0,0])
            observed[0] += 1
            observed[1] += bool(sample['超训练域'])
            observed[2] += sample['用量']
            observed[3] += sample['预测变化']
    return [{'单项安排': key, '可比较单量': attempts, '超出拟合域': outlier,
             '总用量': units, '平均预测变化': round(delta/attempts,4)}
            for key,(attempts,outlier,units,delta) in sorted(actions.items())]


# ---------------------------------------------------------------------------
# 按签发名单复算漏审风险与工位占用
# ---------------------------------------------------------------------------

#: 已由人工通道承接、不再计入自动派单漏审暴露的处置状态。
MANUAL_STATES = frozenset({'人工判读'})
#: 仍暴露在漏审风险中的未分派状态。
EXPOSED_STATES = frozenset({'候补', '暂停', '观察'})
COVERED_STATES = frozenset({'已分派', '人工判读'})


def _signed_record(item):
    """把 Job / 决策元组 / 展示行统一成 (key, cohort, state, cost, estimate)。"""
    if isinstance(item, (tuple, list)):
        if len(item) >= 5:
            key, state, cost, reason, estimate = item[:5]
            cohort = item[5] if len(item) > 5 else None
            return {'key': key, 'cohort': cohort, 'state': state,
                    'cost': cost, 'estimate': estimate}
        raise ValueError('签发决策元组至少包含五项')
    if isinstance(item, dict):
        return {
            'key': item.get('key') or item.get('单号'),
            'cohort': item.get('cohort', item.get('zone', item.get('区段', item.get('作业区')))),
            'state': item.get('state', item.get('处置')),
            'cost': item.get('cost', item.get('工位', 0)) or 0,
            'estimate': item.get('estimate', item.get('估计', item.get('预测'))),
        }
    return {
        'key': getattr(item, 'key', None),
        'cohort': getattr(item, 'cohort', None),
        'state': getattr(item, 'state', None),
        'cost': getattr(item, 'cost', 0) or 0,
        'estimate': getattr(item, 'estimate', None),
    }


def coerce_signed_entries(signed):
    """从 Plan / BatchReceipt / Job 序列 / 决策元组 / 展示行提取签发名单。"""
    capacity = balance = None
    if hasattr(signed, 'jobs') and hasattr(signed, 'used_by_group'):
        capacity = getattr(signed, 'capacity', None)
        balance = getattr(signed, 'balance', None)
        items = signed.jobs
    elif isinstance(signed, BatchReceipt):
        items = signed.decisions
        totals = signed.totals
        capacity = totals.capacity
        balance = totals.balance
    elif hasattr(signed, 'decisions'):
        items = signed.decisions
        totals = getattr(signed, 'totals', None)
        if totals is not None:
            capacity = getattr(totals, 'capacity', None)
            balance = getattr(totals, 'balance', None)
    elif isinstance(signed, dict) and ('jobs' in signed or 'rows' in signed or 'decisions' in signed):
        capacity = signed.get('capacity')
        balance = signed.get('balance')
        items = signed.get('jobs') or signed.get('rows') or signed.get('decisions')
    else:
        items = signed
    entries = [_signed_record(item) for item in items]
    return entries, capacity, balance


signed_entries = coerce_signed_entries


def _resolve_links(links=None, associations=None, correlation=None, context=None):
    source = links if links is not None else associations
    if source is None:
        source = correlation if correlation is not None else context
    if source is None:
        return {}
    report = as_report(source)
    return dict(report.links) if report is not None else links_from_mapping(source)


def recompute_signed_risk(signed, *, links=None, associations=None, correlation=None,
                          context=None, joint_limit=JOINT_RISK_LIMIT, capacity=None,
                          exposed_states=EXPOSED_STATES):
    """按签发名单复算工位占用、期望漏审与同区联合漏审风险。

    返回同时带中文核对键与英文规范键的字典，方便凭证与测试取值。
    ``exposed_states=None`` 时把所有未分派且未转人工的状态都计为暴露。
    """
    entries, cap_hint, bal_hint = coerce_signed_entries(signed)
    cap = capacity if capacity is not None else cap_hint
    link_map = _resolve_links(links, associations, correlation, context)

    used_by_group = Counter()
    exposed_by_group = defaultdict(list)
    expected_misses = 0.0
    manual = 0
    paused = 0
    for entry in entries:
        state = entry['state']
        est = entry['estimate']
        p = float(est) if isinstance(est, (int, float)) else 0.0
        if state == '已分派':
            used_by_group[entry['cohort']] += int(entry['cost'] or 0)
        if state in MANUAL_STATES:
            manual += 1
        if state == '暂停':
            paused += 1
        is_exposed = (state in exposed_states) if exposed_states is not None \
            else (state not in COVERED_STATES)
        if is_exposed:
            exposed_by_group[entry['cohort']].append(p)
            expected_misses += p

    used = sum(used_by_group.values())
    computed_balance = (cap - used) if isinstance(cap, int) else None
    balance = bal_hint if bal_hint is not None else computed_balance
    occupancy_consistent = None
    if isinstance(cap, int):
        occupancy_consistent = (used + (balance if balance is not None else -used)) == cap \
            if balance is not None else used <= cap

    cohort_risks = []
    any_joint = 0.0
    peak = 0.0
    over_line = []
    for cohort in sorted(set(exposed_by_group) | set(link_map)):
        probs = exposed_by_group.get(cohort, ())
        link = link_map.get(cohort)
        rho = float(getattr(link, 'rho', 0.0) or 0.0)
        status = getattr(link, 'status', 'independent' if link is not None else 'unlinked')
        risk = cohort_double_miss_risk(probs, rho) if len(probs) >= 2 else 0.0
        if risk > peak:
            peak = risk
        if risk >= joint_limit:
            over_line.append(cohort)
        any_joint = 1 - (1 - any_joint) * (1 - risk)
        cohort_risks.append({'cohort': cohort, 'risk': round(risk, 6), 'rho': rho,
                             'status': status, 'exposed': len(probs),
                             'over_line': risk >= joint_limit})
    any_joint = min(1.0, max(0.0, any_joint))

    return {
        # 规范英文键
        'capacity': cap, 'used': used, 'occupancy': used, 'balance': balance,
        'used_by_group': tuple(sorted(used_by_group.items(), key=lambda kv: str(kv[0]))),
        'expected_misses': round(expected_misses, 6),
        'joint_risk': round(peak, 6),
        'any_cohort_joint_risk': round(any_joint, 6),
        'cohort_risks': tuple(cohort_risks),
        'over_line_cohorts': tuple(over_line),
        'manual_count': manual, 'paused_count': paused,
        'occupancy_consistent': occupancy_consistent,
        # 中文凭证键
        '工位额度': cap, '工位占用': used, '已用工位': used, '工位余额': balance,
        '分区占用': tuple(sorted(used_by_group.items(), key=lambda kv: str(kv[0]))),
        '复算期望漏审': round(expected_misses, 4),
        '联合漏审峰值': round(peak, 4),
        '跨区联合漏审概率': round(any_joint, 4),
        '联合风险过线区': tuple(over_line),
        '转人工单量': manual, '暂停单量': paused,
    }


# 近义函数名，兼容不同命名预期。
recompute_miss_risk = recompute_signed_risk
recalculate_miss_risk = recompute_signed_risk
miss_risk_from_signed = recompute_signed_risk
signed_list_audit = recompute_signed_risk
audit_signed_list = recompute_signed_risk
recompute_signed_risks = recompute_signed_risk
review_signed_roster = recompute_signed_risk
roster_risk_check = recompute_signed_risk
verify_signing_list = recompute_signed_risk
signing_list_recheck = recompute_signed_risk
occupancy_and_miss_risk = recompute_signed_risk
recompute_dispatch_risk = recompute_signed_risk
recheck_issued_roster = recompute_signed_risk


def miss_risk_evidence(signed, links=None, **kwargs):
    """价证登记环节的中文证据行：复算漏审风险与工位占用。"""
    audit = recompute_signed_risk(signed, links=links, **kwargs)
    rows = [
        {'核对项': '签发工位占用', '数量': audit['工位占用']},
        {'核对项': '工位余额', '数量': audit['工位余额']},
        {'核对项': '复算期望漏审', '数量': audit['复算期望漏审']},
        {'核对项': '联合漏审峰值', '数量': audit['联合漏审峰值']},
        {'核对项': '联合风险过线区', '数量': len(audit['联合风险过线区'])},
    ]
    for item in audit['cohort_risks']:
        rows.append({'核对项': f"联合漏审·{item['cohort']}",
                     '暴露单量': item['exposed'],
                     '关联系数': round(item['rho'], 4),
                     '漏审风险': item['risk'],
                     '是否过线': '是' if item['over_line'] else '否'})
    return rows


joint_risk_evidence = miss_risk_evidence
signed_risk_evidence = miss_risk_evidence
recompute_evidence = miss_risk_evidence


def verify_signed_roster(signed, *, links=None, **kwargs):
    """复算并校验签发名单的工位守恒；额度不平则抛 ArithmeticError。"""
    audit = recompute_signed_risk(signed, links=links, **kwargs)
    if audit['capacity'] is not None and audit['balance'] is not None:
        if audit['used'] + audit['balance'] != audit['capacity']:
            raise ArithmeticError('签发名单复算的工位占用与余额不平')
    return audit


verify_signing_list = verify_signed_roster
check_signed_occupancy = verify_signed_roster
reconcile_signed_list = verify_signed_roster


def __getattr__(name):
    if name.startswith('__'):
        raise AttributeError(name)
    from ..survey_budget import _compat
    return _compat.resolve(name, globals())
