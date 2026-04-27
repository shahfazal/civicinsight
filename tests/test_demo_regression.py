"""
Regression tests against the real income-vs-life-exp held-out output.

This is the demo dashboard for Beat 2 of the video. The model's actual prose
contains a fabrication ("Ireland at (83, 115k)") that the grounder must catch
when the user provides the source CSV. These tests lock in that behavior so
later code changes cannot silently regress the demo's wow moment.

Source data: examples/raw/dw-life-expectancy.csv (gitignored, recoverable
from the Modal volume archive).
"""

from pathlib import Path

import pytest

from app.agent import run
from app.core.validator import MARKER


# Verbatim from notebook 07-experiment-4.ipynb, held-out sweep cell, on
# image income-vs-life-exp.png. Keep this string stable across edits; tests
# below assume these specific values.
EXP4B_HELD_OUT = (
    f"{MARKER} This untitled scatter plot shows GDP per capita against life "
    "expectancy at birth for countries in 2021. The X-axis labeled "
    "'Life expectancy at birth' has a range 50 to 85, in steps of 5. The "
    "Y-axis labeled 'GDP per capita' shows values from 0 to 100k, in steps "
    "of 25k. Individual countries are shown as dots. A country tooltip is "
    "visible, showing Qatar at (78, 90k) and Ireland at (83, 115k). Brunei "
    "is marked at (70, 55k), Spain at (80, 35k) and the Maldives at (80, 15k). "
    "No country is selected, and no tooltip is visible."
)

CSV = Path(__file__).resolve().parent.parent / "examples" / "raw" / "dw-life-expectancy.csv"


pytestmark = pytest.mark.skipif(
    not CSV.exists(),
    reason="dw-life-expectancy.csv missing locally; recover from Modal volume",
)


def test_ireland_115k_is_not_silently_confirmed():
    """
    THE headline regression: model says 'Ireland at (83, 115k)'. Ireland's
    real GDP is $102,496 (12.2% off). At any reasonable tolerance the
    fabricated 115k must NOT be confirmed against the Ireland row. Acceptable
    outcomes: unmatched (no candidate within tolerance) OR ambiguous (multiple
    candidates with no clear winner). Auto-confirming silently is the bug
    this test exists to catch.
    """
    out = run(
        image_bytes=b"any",
        csv_path=CSV,
        infer_fn=lambda _: EXP4B_HELD_OUT,
    )

    ireland_record = next(
        d for d in out.verification_details if "115k" in d
    )
    assert not ireland_record.startswith("Verified"), (
        f"Ireland 115k fabrication was silently confirmed: {ireland_record!r}"
    )


def test_qatar_90k_is_verified_at_adaptive_default():
    """
    Counterpart to the Ireland test: Qatar's actual GDP is $92,862, model
    said 90k (3.1% off, within the scaled 5% adaptive tolerance). This must
    confirm. Validates that the tolerance is loose enough for legitimate
    1-2 sig fig display rounding.
    """
    out = run(
        image_bytes=b"any",
        csv_path=CSV,
        infer_fn=lambda _: EXP4B_HELD_OUT,
    )
    qatar_record = next(d for d in out.verification_details if "90k" in d)
    assert qatar_record.startswith("Verified"), (
        f"Qatar 90k (legitimate display rounding) was not verified: {qatar_record!r}"
    )


def test_axis_metadata_does_not_appear_in_verification_details():
    """
    The model's prose includes axis cues: 'X-axis labeled... range 50 to 85,
    in steps of 5. Y-axis... 0 to 100k, in steps of 25k.' These six numbers
    are chart-scale metadata, not data values. They must NOT pollute the
    per-value verification report.
    """
    out = run(
        image_bytes=b"any",
        csv_path=CSV,
        infer_fn=lambda _: EXP4B_HELD_OUT,
    )
    raw_values_in_details = {d.split("'")[1] for d in out.verification_details if "'" in d}
    axis_values = {"50", "85", "5", "0", "100k", "25k"}
    leaked = raw_values_in_details & axis_values
    assert not leaked, f"Axis metadata leaked into verification details: {leaked}"


def test_data_status_is_partial_not_verified_with_fabrications():
    """
    Document-level status must NOT be 'verified' for an output containing the
    Ireland fabrication. 'partial' is the correct outcome - some values
    match, others (the fabrications) do not.
    """
    out = run(
        image_bytes=b"any",
        csv_path=CSV,
        infer_fn=lambda _: EXP4B_HELD_OUT,
    )
    assert out.data_status == "partial"
    assert out.confidence is not None and out.confidence < 1.0
