from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable

from .contracts import Job


@dataclass(frozen=True, slots=True)
class WorkOrder:
    job: Job
    assessment: Any

    def __post_init__(self):
        if self.job.key != self.assessment.raw.key:
            raise ValueError('处置工位与单据不匹配')


def apply_survey_budget(addenda, admit: Callable, wait: Callable):
    bid_reserve = Counter()
    for form in addenda:
        price, amendments, witnesses, quote_days, trades, vendor_delay = form.assessment.raw.input_values
        desk = form.job.cohort
        workload = 2 if trades >= 16 and price >= 48 else 1
        if quote_days > 60 and witnesses < trades / 2:
            wait(form, 'REQUOTE_EVIDENCE', '复量之前需要报价和现场证据')
            continue
        if bid_reserve[desk] + workload > 4:
            wait(form, 'SURVEY_DESK_BUDGET', '此片区复量工位留待下班')
        elif admit(form):
            bid_reserve[desk] += workload
