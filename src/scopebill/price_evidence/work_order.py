def collect_field_witness(measures, missing, estimate):
    photos = measures['photos']
    works = measures['works']
    if not (photos<works):
        return None
    value=works-photos
    return {'现场复核':'比对见证','可复查值':round(value,3),'单位':'项','归档要求':'确认能对应作业项的见证图片',
            '需补测':not set(missing).isdisjoint(('photos', 'works'))}


def collect_quote_repeat(measures, missing, estimate):
    quote_age = measures['quote_age']
    if not (quote_age>=39):
        return None
    value=quote_age
    return {'现场复核':'复问报价','可复查值':round(value,3),'单位':'天','归档要求':'请同一供应商补发有效期',
            '需补测':not set(missing).isdisjoint(('quote_age',))}


def collect_change_order(measures, missing, estimate):
    revisions = measures['revisions']
    if not (revisions>=6):
        return None
    value=revisions
    return {'现场复核':'查改量表','可复查值':round(value,3),'单位':'次','归档要求':'留存采纳前后两版工程量',
            '需补测':not set(missing).isdisjoint(('revisions',))}


def collect_contract_extension(measures, missing, estimate):
    extra_pct = measures['extra_pct']
    if not (extra_pct>=45):
        return None
    value=extra_pct
    return {'现场复核':'核对合同金额','可复查值':round(value,3),'单位':'%','归档要求':'与合同基线对账',
            '需补测':not set(missing).isdisjoint(('extra_pct',))}


def check_price_evidence(records):
    guide = []
    for ticket in records:
        if ticket['state'] not in ('已分派','暂停','人工判读'):
            continue
        measures=ticket['measurements']
        absent=ticket['unmeasured']
        estimate=ticket['estimate']
        checks = (
            collect_field_witness(measures,absent,estimate),
            collect_quote_repeat(measures,absent,estimate),
            collect_change_order(measures,absent,estimate),
            collect_contract_extension(measures,absent,estimate),
        )
        required=tuple(check for check in checks if check is not None)
        if not required:
            continue
        review=ticket['key']
        for check in required:
            guide.append({'签收单':review,'作业区':ticket['zone'],'处置':ticket['state'],**check})
    return guide
