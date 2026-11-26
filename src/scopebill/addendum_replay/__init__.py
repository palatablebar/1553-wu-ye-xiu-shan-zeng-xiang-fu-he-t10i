"""addendum replay."""

from .service import prepare_verification, validate_predictions, performance, calibration_evidence

__all__ = ('prepare_verification', 'validate_predictions', 'performance', 'calibration_evidence')


def __getattr__(name):
    from ..survey_budget._compat import package_attr
    return package_attr(__name__, name, globals())
