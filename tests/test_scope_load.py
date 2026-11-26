from dataclasses import replace
import pytest
from scopebill.scope_load.service import fit_features, spread, transform, transform_all
from scopebill.variation_forms.service import read_assay


def test_cancellation_safe_scaling():
    # TRAP-32
    centre, deviation = spread([1e9-.25,1e9,1e9+.25])
    assert centre == 1e9
    assert .20 <= deviation <= .38
    # E[X²] − E[X]² rounds away the finite variance at this magnitude.
    shifted = [1e9-.25,1e9,1e9+.25]
    naive = sum(point*point for point in shifted)/3-centre*centre
    assert naive < .01


def test_constant_column_stays_finite(observation):
    entry = read_assay(observation)
    fitted = fit_features((entry,))
    assert fitted.scales == (1.,)*5
    assert transform(entry,fitted).values == (0.,)*5


def test_fitted_fill_does_not_depend_on_current_batch(observation):
    assay = read_assay(observation)
    missing = replace(assay,key='absent',extra_pct=None)
    reference = fit_features([assay])
    assert transform(missing, reference).values == transform(assay, reference).values
    assert transform(missing, reference).missing == ('extra_pct',)


def test_permuted_history_has_same_reference(observation):
    row = read_assay(observation)
    alternate = replace(row,key='other',extra_pct=row.extra_pct+.1)
    assert fit_features([row,alternate]) == fit_features([alternate,row])


def test_extreme_outside_reference_is_located(observation):
    row = read_assay(observation)
    new = replace(row,key='out',extra_pct=row.extra_pct+176)
    assert transform(new,fit_features([row])).excursions


def test_all_missing_training_measure_is_clear(observation):
    row = replace(read_assay(observation),extra_pct=None)
    with pytest.raises(ValueError,match='extra_pct'):
        fit_features([row])


def test_feature_outputs_do_not_depend_on_inference_group(observation):
    assay = read_assay(observation)
    second = replace(assay,key='separate',extra_pct=assay.extra_pct+1)
    source = fit_features([assay])
    assert transform_all([assay,second], source) == (transform(assay,source),transform(second,source))
