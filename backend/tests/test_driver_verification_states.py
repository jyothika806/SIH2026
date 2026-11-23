from datetime import date

import pytest

from backend.app.api.v1.admin import LicenceReviewRequest


@pytest.mark.parametrize(
    "outcome", ["pending", "approved", "rejected", "unavailable"]
)
def test_licence_review_distinguishes_all_verification_outcomes(outcome):
    review = LicenceReviewRequest(
        licence_number="DL-12345",
        holder_name="Test Driver",
        date_of_birth="1990-01-01",
        expiry_date=date(2030, 1, 1),
        outcome=outcome,
        verification_reference="case-123",
    )

    assert review.outcome == outcome
