from dataclasses import replace
from types import SimpleNamespace
import pytest

from scopebill.addendum_replay.contracts import Assessment
from scopebill.survey_budget.contracts import Policy
from scopebill.survey_budget.service import plan_jobs
from scopebill.survey_budget import joint_risk as jr
from scopebill.price_evidence.service import recompute_signed_risk, miss_risk_evidence


def A(prediction, key, cohort, est, uncertain=False,
      values=(46.0, 7.0, 21.0, 43.5, 10.0, 36.0)):
    raw = replace(prediction, key=key, cohort=cohort, outcome=None, observed=True,
                  input_values=values)
    return Assessment(raw, est, None, None, uncertain)


def replay_row(key, cohort, day, p, outcome, result_day):
    return SimpleNamespace(key=key, cohort=cohort, day=day, estimate=p, score=p,
                           outcome=outcome, observed=True, result_day=result_day,
                           received=None)


def test_policy_aliases():
    for name in ('joint', 'paired', 'correlated', 'cluster', 'joint_risk'):
        p = Policy.select(9, name)
        assert p.capacity == 9 and p.group_quota == 9
    with pytest.raises(ValueError, match='策略'):
        Policy.select(9, 'nope')


def test_late_labels_excluded():
    rows = [
        replay_row('r1', 'Z', 70, .2, 1, 72),
        replay_row('r2', 'Z', 70, .2, 1, 95),   # late confirmed
    ]
    # cutoff 84 half-open-ish inclusive 84: r2 excluded -> no pair -> unknown
    links = jr.build_links(rows, cohorts=['Z'], as_of=84)
    assert links['Z'].status == 'unknown'
    # without cutoff both included -> grouped
    links2 = jr.build_links(rows, cohorts=['Z'])
    assert links2['Z'].status == 'grouped' and links2['Z'].pairs == 1
    # inclusive boundary: result_day==84 included with <=84
    rows_b = [replay_row('a', 'Z', 70, .3, 0, 84), replay_row('b', 'Z', 70, .3, 1, 84)]
    assert jr.label_is_mature(jr.normalize(rows_b[0]), 84) is True
    assert jr.label_is_mature(jr.normalize(rows_b[0]), 84, inclusive=False) is False


def test_cold_cohort_manual_no_occupancy(prediction):
    live = [A(prediction, 'x', 'ColdZone', .9), A(prediction, 'y', 'ColdZone', .85)]
    plan = plan_jobs(live, (), 5, 'joint', [])
    assert all(j.state == '人工判读' for j in plan.jobs)
    assert plan.balance == 5
    assert sum(c for _, c in plan.used_by_group) == 0
    assert plan.jobs[0].reason == 'COLD_START'
    assert plan.jobs[0].reason == 'NO_COMPARABLE_SAMPLE'


def test_joint_priority_beats_higher_outside_score(prediction):
    # strongly positively correlated pair in Z from replay
    replay = [
        replay_row('r1', 'Z', 70, .2, 1, 72),
        replay_row('r2', 'Z', 70, .2, 1, 72),
    ]
    live = [A(prediction, 'z1', 'Z', .82), A(prediction, 'z2', 'Z', .80),
            A(prediction, 'o1', 'Other', .95)]
    plan = plan_jobs(live, (), 1, 'joint', replay)
    dispatched = [j.key for j in plan.jobs if j.state == '已分派']
    assert dispatched == ['z1'], dispatched


def test_independent_low_pair_follows_score(prediction):
    # explicit zero correlation; pair low enough to stay under line
    live = [A(prediction, 'z1', 'Z', .30), A(prediction, 'z2', 'Z', .28),
            A(prediction, 'o1', 'Other', .9)]
    plan = plan_jobs(live, (), 1, 'joint', {'Z': 0.0, 'Other': 0.0})
    dispatched = [j.key for j in plan.jobs if j.state == '已分派']
    assert dispatched == ['o1'], dispatched


def test_no_witness_still_paused(prediction):
    vals = (78, 8, 2, 22, 18, 24)
    live = [A(prediction, 'w', 'Z', .9, values=vals)]
    plan = plan_jobs(live, (), 5, 'joint', [])
    job = plan.jobs[0]
    assert job.state == '暂停' and job.reason == 'NO_WITNESS'


def test_price_evidence_recompute(prediction):
    live = [A(prediction, 'z1', 'Z', .82), A(prediction, 'z2', 'Z', .80)]
    plan = plan_jobs(live, (), 1, 'joint', {'Z': .9})
    audit = recompute_signed_risk(plan, links={'Z': .9})
    assert audit['used'] == 1 and audit['capacity'] == 1
    assert audit['工位占用'] == 1
    rows = miss_risk_evidence(plan, links={'Z': .9})
    assert any(r['核对项'] == '签发工位占用' for r in rows)
