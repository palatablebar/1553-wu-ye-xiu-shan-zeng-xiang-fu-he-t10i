from collections import defaultdict
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True, slots=True)
class ContractReview:
    photographs_due: int
    remeasured: int
    notice_within: int
    quotation_stale: bool
    index: float
    clause: str


def commercial_evidence(change):
    facts = change['measurements']
    works = int(facts['works'])
    proof = min(works, int(facts['photos'])//2)
    evidence_gap = works-proof
    high_value = facts['extra_pct'] >= 32
    stale = facts['quote_age'] > 66 and high_value
    timeline = max(0,48-ceil(facts['vendor_lag']))
    gain = (facts['extra_pct']/100)*max(1,works) * (1+change['estimate'])
    if 'NO_WITNESS' in change['hits']:
        clause = '现场签证附件欠缺，退核'
        remeasure = works
    elif stale:
        clause = '比价文件过期，发询价复核'
        remeasure = ceil(evidence_gap/2)
    elif facts['revisions']>=9 and works>=13:
        clause = '核对双签工程量分项'
        remeasure = max(3,min(works,ceil(works/2)))
    else:
        clause = '补完影像台账' if evidence_gap else '单据存档待班组确认'
        remeasure = ceil(evidence_gap/2) if high_value else 0
    return ContractReview(max(0,2*works-int(facts['photos'])),remeasure,timeline,stale,gain,clause)


def operating_ledger(rows):
    buildings = defaultdict(list)
    findings = []
    for change in rows:
        if change['unmeasured']:
            findings.append({'业务安排':'退补计量清单和报价标记','关联单据':change['key'],'增项支付授权':False})
            continue
        assessment = commercial_evidence(change)
        buildings[change['zone']].append(assessment)
        if assessment.remeasured or assessment.quotation_stale or assessment.photographs_due:
            findings.append({'业务安排':assessment.clause,'关联单据':change['key'],'项目区':change['zone'],
                             '复量分项':assessment.remeasured,'补照片数':assessment.photographs_due,
                             '询核剩余小时':assessment.notice_within,'增项支付授权':False})
    for property_name, clauses in sorted(buildings.items()):
        budget = sum(check.remeasured for check in clauses)
        expired = sum(check.quotation_stale for check in clauses)
        priority = sum(check.index for check in clauses if check.notice_within<=8)
        findings.append({'业务安排':'修缮附件对账','项目区':property_name,'复量需求项数':budget,
                         '过期报价单量':expired,'临近催办复核指数':round(priority,2),
                         '归档变更单量':len(clauses)})
    return findings
