from dataclasses import replace
from statistics import mean, median
from collections import Counter
from math import fsum

from .contracts import FEATURE_NAMES, FEATURE_KEYS, RAW_KEYS


def current_change_per_work(vector):
    revisions = vector.input_values[1]
    works = vector.input_values[4]
    return float(revisions/works)


def compare_change_per_work(training, target):
    usual_change_per_work = take_sample(training, current_change_per_work)
    recent_change_per_work = take_sample(target, current_change_per_work)
    if len(usual_change_per_work) < 4 or not recent_change_per_work:
        return {'作业量': '每项签证修订', '有效读数': len(recent_change_per_work), '判断': '参考不足'}
    anchor_change_per_work = median(usual_change_per_work)
    measured_change_per_work = median(recent_change_per_work)
    ordered_change_per_work = sorted(usual_change_per_work)
    low_change_per_work, high_change_per_work = ordered_change_per_work[len(ordered_change_per_work)//10], ordered_change_per_work[(len(ordered_change_per_work)*9)//10]
    change_change_per_work = measured_change_per_work-anchor_change_per_work
    outside_change_per_work = sum(value<low_change_per_work or value>high_change_per_work for value in recent_change_per_work)
    return {'作业量': '每项签证修订', '训练参考': round(anchor_change_per_work, 4), '现场中位': round(measured_change_per_work, 4),
            '变动': round(change_change_per_work, 4), '越界量': outside_change_per_work, '有效读数': len(recent_change_per_work)}


def current_photo_ratio(vector):
    photos = vector.input_values[2]
    works = vector.input_values[4]
    return float(photos/works)


def compare_photo_ratio(training, target):
    usual_photo_ratio = take_sample(training, current_photo_ratio)
    recent_photo_ratio = take_sample(target, current_photo_ratio)
    if len(usual_photo_ratio) < 4 or not recent_photo_ratio:
        return {'作业量': '每项可查影像', '有效读数': len(recent_photo_ratio), '判断': '参考不足'}
    anchor_photo_ratio = median(usual_photo_ratio)
    measured_photo_ratio = median(recent_photo_ratio)
    ordered_photo_ratio = sorted(usual_photo_ratio)
    low_photo_ratio, high_photo_ratio = ordered_photo_ratio[len(ordered_photo_ratio)//10], ordered_photo_ratio[(len(ordered_photo_ratio)*9)//10]
    change_photo_ratio = measured_photo_ratio-anchor_photo_ratio
    outside_photo_ratio = sum(value<low_photo_ratio or value>high_photo_ratio for value in recent_photo_ratio)
    return {'作业量': '每项可查影像', '训练参考': round(anchor_photo_ratio, 4), '现场中位': round(measured_photo_ratio, 4),
            '变动': round(change_photo_ratio, 4), '越界量': outside_photo_ratio, '有效读数': len(recent_photo_ratio)}


def current_vendor_delay_days(vector):
    vendor_lag = vector.input_values[5]
    return float(vendor_lag/24)


def compare_vendor_delay_days(training, target):
    usual_vendor_delay_days = take_sample(training, current_vendor_delay_days)
    recent_vendor_delay_days = take_sample(target, current_vendor_delay_days)
    if len(usual_vendor_delay_days) < 4 or not recent_vendor_delay_days:
        return {'作业量': '施工方延迟天数', '有效读数': len(recent_vendor_delay_days), '判断': '参考不足'}
    anchor_vendor_delay_days = median(usual_vendor_delay_days)
    measured_vendor_delay_days = median(recent_vendor_delay_days)
    band_vendor_delay_days = max(1.0, abs(anchor_vendor_delay_days)*.2, median(abs(value-anchor_vendor_delay_days) for value in usual_vendor_delay_days))
    change_vendor_delay_days = (measured_vendor_delay_days-anchor_vendor_delay_days) / band_vendor_delay_days
    outside_vendor_delay_days = sum(abs(value-anchor_vendor_delay_days)>2.5*band_vendor_delay_days for value in recent_vendor_delay_days)
    return {'作业量': '施工方延迟天数', '训练参考': round(anchor_vendor_delay_days, 4), '现场中位': round(measured_vendor_delay_days, 4),
            '变动': round(change_vendor_delay_days, 4), '越界量': outside_vendor_delay_days, '有效读数': len(recent_vendor_delay_days)}


def current_commercial_exposure(vector):
    extra_pct = vector.input_values[0]
    works = vector.input_values[4]
    return float(extra_pct*works/100)


def compare_commercial_exposure(training, target):
    usual_commercial_exposure = take_sample(training, current_commercial_exposure)
    recent_commercial_exposure = take_sample(target, current_commercial_exposure)
    if len(usual_commercial_exposure) < 4 or not recent_commercial_exposure:
        return {'作业量': '增项作业暴露面', '有效读数': len(recent_commercial_exposure), '判断': '参考不足'}
    anchor_commercial_exposure = median(usual_commercial_exposure)
    measured_commercial_exposure = median(recent_commercial_exposure)
    band_commercial_exposure = max(1.0, abs(anchor_commercial_exposure)*.2, median(abs(value-anchor_commercial_exposure) for value in usual_commercial_exposure))
    change_commercial_exposure = (measured_commercial_exposure-anchor_commercial_exposure) / band_commercial_exposure
    outside_commercial_exposure = sum(abs(value-anchor_commercial_exposure)>2.5*band_commercial_exposure for value in recent_commercial_exposure)
    return {'作业量': '增项作业暴露面', '训练参考': round(anchor_commercial_exposure, 4), '现场中位': round(measured_commercial_exposure, 4),
            '变动': round(change_commercial_exposure, 4), '越界量': outside_commercial_exposure, '有效读数': len(recent_commercial_exposure)}


def current_quote_reserved(vector):
    quote_age = vector.input_values[3]
    return float(66-quote_age)


def compare_quote_reserved(training, target):
    usual_quote_reserved = take_sample(training, current_quote_reserved)
    recent_quote_reserved = take_sample(target, current_quote_reserved)
    if len(usual_quote_reserved) < 4 or not recent_quote_reserved:
        return {'作业量': '报价距复核线', '有效读数': len(recent_quote_reserved), '判断': '参考不足'}
    anchor_quote_reserved = median(usual_quote_reserved)
    measured_quote_reserved = median(recent_quote_reserved)
    ordered_quote_reserved = sorted(usual_quote_reserved)
    low_quote_reserved, high_quote_reserved = ordered_quote_reserved[len(ordered_quote_reserved)//10], ordered_quote_reserved[(len(ordered_quote_reserved)*9)//10]
    change_quote_reserved = measured_quote_reserved-anchor_quote_reserved
    outside_quote_reserved = sum(value<low_quote_reserved or value>high_quote_reserved for value in recent_quote_reserved)
    return {'作业量': '报价距复核线', '训练参考': round(anchor_quote_reserved, 4), '现场中位': round(measured_quote_reserved, 4),
            '变动': round(change_quote_reserved, 4), '越界量': outside_quote_reserved, '有效读数': len(recent_quote_reserved)}


def current_new_work_share(vector):
    photos = vector.input_values[2]
    works = vector.input_values[4]
    return float(works/(works+photos))


def compare_new_work_share(training, target):
    usual_new_work_share = take_sample(training, current_new_work_share)
    recent_new_work_share = take_sample(target, current_new_work_share)
    if len(usual_new_work_share) < 4 or not recent_new_work_share:
        return {'作业量': '缺原分段证据比', '有效读数': len(recent_new_work_share), '判断': '参考不足'}
    anchor_new_work_share = median(usual_new_work_share)
    measured_new_work_share = median(recent_new_work_share)
    ordered_new_work_share = sorted(usual_new_work_share)
    low_new_work_share, high_new_work_share = ordered_new_work_share[len(ordered_new_work_share)//10], ordered_new_work_share[(len(ordered_new_work_share)*9)//10]
    change_new_work_share = measured_new_work_share-anchor_new_work_share
    outside_new_work_share = sum(value<low_new_work_share or value>high_new_work_share for value in recent_new_work_share)
    return {'作业量': '缺原分段证据比', '训练参考': round(anchor_new_work_share, 4), '现场中位': round(measured_new_work_share, 4),
            '变动': round(change_new_work_share, 4), '越界量': outside_new_work_share, '有效读数': len(recent_new_work_share)}


def current_aged_variance(vector):
    revisions = vector.input_values[1]
    quote_age = vector.input_values[3]
    return float(revisions*quote_age)


def compare_aged_variance(training, target):
    usual_aged_variance = take_sample(training, current_aged_variance)
    recent_aged_variance = take_sample(target, current_aged_variance)
    if len(usual_aged_variance) < 4 or not recent_aged_variance:
        return {'作业量': '修订次数乘报价日', '有效读数': len(recent_aged_variance), '判断': '参考不足'}
    anchor_aged_variance = median(usual_aged_variance)
    measured_aged_variance = median(recent_aged_variance)
    band_aged_variance = max(1.0, abs(anchor_aged_variance)*.2, median(abs(value-anchor_aged_variance) for value in usual_aged_variance))
    change_aged_variance = (measured_aged_variance-anchor_aged_variance) / band_aged_variance
    outside_aged_variance = sum(abs(value-anchor_aged_variance)>2.5*band_aged_variance for value in recent_aged_variance)
    return {'作业量': '修订次数乘报价日', '训练参考': round(anchor_aged_variance, 4), '现场中位': round(measured_aged_variance, 4),
            '变动': round(change_aged_variance, 4), '越界量': outside_aged_variance, '有效读数': len(recent_aged_variance)}


def current_review_gap(vector):
    extra_pct = vector.input_values[0]
    photos = vector.input_values[2]
    return float(extra_pct/(1+photos))


def compare_review_gap(training, target):
    usual_review_gap = take_sample(training, current_review_gap)
    recent_review_gap = take_sample(target, current_review_gap)
    if len(usual_review_gap) < 4 or not recent_review_gap:
        return {'作业量': '高额无证据暴露', '有效读数': len(recent_review_gap), '判断': '参考不足'}
    anchor_review_gap = median(usual_review_gap)
    measured_review_gap = median(recent_review_gap)
    band_review_gap = max(1.0, abs(anchor_review_gap)*.2, median(abs(value-anchor_review_gap) for value in usual_review_gap))
    change_review_gap = (measured_review_gap-anchor_review_gap) / band_review_gap
    outside_review_gap = sum(abs(value-anchor_review_gap)>2.5*band_review_gap for value in recent_review_gap)
    return {'作业量': '高额无证据暴露', '训练参考': round(anchor_review_gap, 4), '现场中位': round(measured_review_gap, 4),
            '变动': round(change_review_gap, 4), '越界量': outside_review_gap, '有效读数': len(recent_review_gap)}


def take_sample(vectors, measure):
    return tuple(measure(record) for record in vectors if not record.missing)


def measure_scope_load_band(history, daybook):
    yield compare_change_per_work(history, daybook)
    yield compare_photo_ratio(history, daybook)
    yield compare_vendor_delay_days(history, daybook)
    yield compare_commercial_exposure(history, daybook)
    yield compare_quote_reserved(history, daybook)
    yield compare_new_work_share(history, daybook)
    yield compare_aged_variance(history, daybook)
    yield compare_review_gap(history, daybook)


def evaluate_shift(training, current):
    return list(measure_scope_load_band(training, current))
