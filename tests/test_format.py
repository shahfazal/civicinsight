"""
Tests for app.core.format.

Each test asserts behavior the Gradio UI (app.io.demo) renders directly to the
user. Confidence math, per-value details, and the verified/partial/unverified
states are all user-facing.
"""

from dataclasses import dataclass

import pandas as pd

from app.core.extract import extract
from app.core.format import format_output
from app.core.validator import MARKER, validate
from app.grounding.match import match_records
from app.grounding.source import SourceData


# A representative held-out output for the happy path.
_DESCRIPTION = (
    f"{MARKER} This line chart shows tourist arrivals in Auvergne. "
    "Total arrivals reached 14.6M visitors in 2023, up from 12.0M in 2020."
)


def _source_with_arrivals(values: list[float]) -> SourceData:
    return SourceData.from_dataframe(pd.DataFrame({
        "region": ["Auvergne"] * len(values),
        "arrivals": values,
    }))


def test_marker_is_preserved_in_aria_label():
    # The marker is intentionally kept in the displayed description as
    # proof-of-provenance for judges and sighted users inspecting output.
    # Screen-reader noise (literal "[civicinsight-v1]" being read aloud) is
    # an accepted tradeoff. See the comment in app/core/format.py.
    validation = validate(_DESCRIPTION)
    out = format_output(_DESCRIPTION, validation)
    assert out.aria_label.startswith(MARKER)


def test_image_only_path_returns_unverified_with_none_confidence():
    # No CSV provided: data_status is unverified, confidence is None
    # (not 0.0 or 1.0; we have no basis for either).
    validation = validate(_DESCRIPTION)
    out = format_output(_DESCRIPTION, validation, match_results=None)
    assert out.data_status == "unverified"
    assert out.confidence is None
    assert "no source data" in out.verification_summary.lower()
    assert out.verification_details == []


def test_all_confirmed_yields_verified_with_full_confidence():
    # Every value record matches a source cell -> confidence 1.0, status verified.
    records = extract(_DESCRIPTION, locale="en")
    source = _source_with_arrivals([14_600_000, 12_000_000])
    matches = match_records(records, source)
    validation = validate(_DESCRIPTION)
    out = format_output(_DESCRIPTION, validation, match_results=matches)
    assert out.data_status == "verified"
    assert out.confidence == 1.0
    assert all(d.startswith("Verified") for d in out.verification_details)


def test_partial_match_yields_partial_status_with_fractional_confidence():
    # Two values, one in source, one not -> confidence 0.5, status partial.
    records = extract(_DESCRIPTION, locale="en")
    source = _source_with_arrivals([14_600_000])  # only the first value present
    matches = match_records(records, source)
    validation = validate(_DESCRIPTION)
    out = format_output(_DESCRIPTION, validation, match_results=matches)
    assert out.data_status == "partial"
    assert out.confidence == 0.5
    statuses = [d.split(":")[0] for d in out.verification_details]
    assert statuses.count("Verified") == 1
    assert statuses.count("Unverified") == 1


def test_zero_confirmed_with_csv_yields_unverified():
    # CSV provided but no values matched anything -> confidence 0.0, status unverified.
    records = extract(_DESCRIPTION, locale="en")
    source = _source_with_arrivals([1_000_000])  # values that match nothing
    matches = match_records(records, source)
    validation = validate(_DESCRIPTION)
    out = format_output(_DESCRIPTION, validation, match_results=matches)
    assert out.data_status == "unverified"
    assert out.confidence == 0.0


def test_missing_marker_short_circuits_to_structural_issue():
    # Without the marker, the agent must NOT proceed to grounding even if
    # match_results were somehow computed. format_output returns an honest signal.
    description = "Some text without our marker. The image is not a chart."
    validation = validate(description)
    out = format_output(description, validation, match_results=None)
    assert out.data_status == "structural-issue"
    assert out.confidence == 0.0
    assert any("CivicInsight" in s for s in [out.verification_summary])
    # Structural issues are surfaced for the UI to display.
    assert len(out.structural_issues) > 0


def test_no_value_records_with_csv_reports_nothing_to_verify():
    # If the description contained only years, no value records reach the
    # matcher. format_output must still produce a coherent output.
    description = f"{MARKER} This line chart spans the years 2009 to 2023 across all regions."
    records = extract(description, locale="en")
    source = _source_with_arrivals([14_600_000])
    matches = match_records(records, source)
    assert matches == []  # all years filtered, no value records
    validation = validate(description)
    out = format_output(description, validation, match_results=matches)
    assert out.data_status == "unverified"
    assert out.confidence is None
    assert "no numeric values eligible" in out.verification_summary.lower()


def test_ambiguous_match_appears_in_details():
    # Ambiguous outcomes are user-visible: the details line tells the user
    # what was found and why disambiguation failed.
    description = f"{MARKER} This bar chart shows arrivals reached 14.6M total."
    records = extract(description, locale="en")
    source = SourceData.from_dataframe(pd.DataFrame({
        "region": ["Auvergne", "Brittany"],
        "arrivals": [14_600_000, 14_600_000],
    }))
    matches = match_records(records, source)
    validation = validate(description)
    out = format_output(description, validation, match_results=matches)
    [detail] = out.verification_details
    assert detail.startswith("Ambiguous")
    assert "2 cells" in detail
