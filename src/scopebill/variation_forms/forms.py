from collections.abc import Mapping
from decimal import Decimal

from .contracts import MeasureIssue


from dataclasses import dataclass


def form_number(form, sheet, name, minimum, maximum):
    from .service import number

    table = form.get(sheet)
    if not isinstance(table, Mapping):
        raise MeasureIssue(sheet, 'FORM_SECTION_REQUIRED')
    return Decimal(str(number(table.get(name), name, minimum, maximum)))


@dataclass(frozen=True, slots=True)
class VariationFormsSheet:
    scope_diff_basis_points: Decimal
    rewrites: Decimal
    inspection_photos: Decimal
    quote_age_hours: Decimal
    changed_operations: Decimal
    vendor_respond_minutes: Decimal

    def fields(self):
        return {
            'extra_pct': float(self.scope_diff_basis_points) / 100,
            'revisions': float(self.rewrites),
            'photos': float(self.inspection_photos),
            'quote_age': float(self.quote_age_hours) / 24,
            'works': float(self.changed_operations),
            'vendor_lag': float(self.vendor_respond_minutes) / 60,
        }

    def validation(self):
        fields = self.fields()
        extra_pct = fields['extra_pct']
        revisions = fields['revisions']
        photos = fields['photos']
        quote_age = fields['quote_age']
        works = fields['works']
        vendor_lag = fields['vendor_lag']
        work_without_photos = max(0,works-photos)
        revision_density = revisions/works
        contract_delay_hours = quote_age*24+vendor_lag
        changed_exposure = extra_pct*work_without_photos
        alerts = []
        if revision_density>12:
            alerts.append(('rewrites', 'DUPLICATE_CHANGE_SLIP'))
        if contract_delay_hours>1870 and extra_pct>=81:
            alerts.append(('quote_age_hours', 'QUOTE_REAPPROVAL_MISSING'))
        if changed_exposure>2900:
            alerts.append(('inspection_photos', 'COUNT_WITNESS_ITEMS_AGAIN'))
        return tuple(alerts)


def read_variation_forms(form):
    return VariationFormsSheet(
        scope_diff_basis_points=form_number(form, '增项结算', 'scope_diff_basis_points', 200, 9000),
        rewrites=form_number(form, '增项结算', 'rewrites', 0, 14),
        inspection_photos=form_number(form, '工程量签证', 'inspection_photos', 0, 42),
        quote_age_hours=form_number(form, '工程量签证', 'quote_age_hours', 96, 1992),
        changed_operations=form_number(form, '复核证据', 'changed_operations', 1, 38),
        vendor_respond_minutes=form_number(form, '复核证据', 'vendor_respond_minutes', 120, 4200),
    )


def explicit_rows(form):
    if not isinstance(form, Mapping):
        raise MeasureIssue('form', 'FORM_OBJECT_REQUIRED')
    note = read_variation_forms(form)
    return note.fields(), note.validation()


def check_native_history(source):
    if not isinstance(source, Mapping) or 'form' not in source:
        return source
    if any(key in source for key in ('extra_pct', 'revisions', 'photos', 'quote_age', 'works', 'vendor_lag')):
        raise MeasureIssue('form','MIXED_FORM_AND_FLAT_READING')
    converted, flags = explicit_rows(source['form'])
    if flags:
        raise MeasureIssue(*flags[0])
    return {**source, **converted}
