from scopebill.pipeline import preview
from scopebill.survey_budget.service import operating_ledger


def note(key, measures, *, zone='甲区', state='已分派', estimate=0, hits=(), missing=()):
    return {'key':key,'zone':zone,'state':state,'estimate':estimate,'hits':hits,
            'unmeasured':missing,'measurements':dict(zip(('extra_pct', 'revisions', 'photos', 'quote_age', 'works', 'vendor_lag'),measures,strict=True))}


def test_field_plan_is_visible_and_references_real_tickets():
    desk = preview()
    plan = desk['sections'][6]
    assert plan['operating_title'] == '增项附件核对单'
    assert plan['operating_rows']
    scoped = {item['关联单据'] for item in plan['operating_rows'] if '关联单据' in item}
    assert scoped and scoped <= {row['key'] for row in desk['rows']}
    assert all(item['业务安排'] for item in plan['operating_rows'])


def test_expired_quote_requires_reissue_with_no_payment_claim():
    document = note('SC-1',(49,6,8,73,11,45),estimate=.73)
    action, total = operating_ledger([document])
    assert action['业务安排']=='比价文件过期，发询价复核'
    assert action['询核剩余小时']==3 and not action['增项支付授权']
    assert total['过期报价单量']==1
