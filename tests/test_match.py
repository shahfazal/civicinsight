"""
Tests for app.grounding.match.

Each test asserts behavior the formatter (app.core.format) and agent
(app.agent) actually depend on.
"""

import pandas as pd

from app.core.extract import extract
from app.grounding.match import MatchResult, match_records
from app.grounding.source import SourceData


def _source(rows: dict) -> SourceData:
    """Helper: build a SourceData from a dict-of-columns."""
    return SourceData.from_dataframe(pd.DataFrame(rows))


def test_single_value_with_unique_source_cell_is_confirmed():
    records = extract("Auvergne arrivals were 14.6M visitors.", locale="en")
    source = _source({
        "region": ["Auvergne", "Brittany"],
        "arrivals": [14_600_000, 8_500_000],
    })
    [result] = match_records(records, source)
    assert result.status == "confirmed"
    assert result.cell is not None
    assert result.cell.value == 14_600_000.0
    assert result.cell.row_context["region"] == "Auvergne"


def test_value_with_no_matching_cell_is_unmatched():
    records = extract("Auvergne arrivals were 14.6M visitors.", locale="en")
    source = _source({"region": ["Brittany"], "arrivals": [8_500_000]})
    [result] = match_records(records, source)
    assert result.status == "unmatched"
    assert result.cell is None
    assert result.candidates == []


def test_disambiguation_picks_correct_cell_via_context_overlap():
    # Two cells both match 14.6M numerically. Only one row contains "Auvergne",
    # which is also in the model's context_phrase. Disambiguator must pick that one.
    records = extract("Auvergne tourist arrivals were 14.6M visitors.", locale="en")
    source = _source({
        "region": ["Auvergne", "Brittany"],
        "arrivals": [14_600_000, 14_600_000],
    })
    [result] = match_records(records, source)
    assert result.status == "confirmed"
    assert result.cell.row_context["region"] == "Auvergne"
    # Both candidates were considered, even though only one was picked.
    assert len(result.candidates) == 2


def test_multiple_matches_with_no_context_overlap_is_ambiguous():
    # Both cells match 14.6M; neither row contains anything from the prose.
    # Disambiguator cannot pick, must return ambiguous.
    records = extract("The headline figure was 14.6M last year.", locale="en")
    source = _source({
        "region": ["Auvergne", "Brittany"],
        "arrivals": [14_600_000, 14_600_000],
    })
    [result] = match_records(records, source)
    assert result.status == "ambiguous"
    assert result.cell is None
    assert len(result.candidates) == 2
    assert result.reason is not None


def test_multiple_matches_with_equal_overlap_is_ambiguous():
    # Both rows contain "tourist" (the only meaningful context token).
    # Equal overlap -> cannot pick a winner.
    records = extract("Tourist arrivals reached 14.6M.", locale="en")
    source = _source({
        "region": ["Auvergne", "Brittany"],
        "label": ["tourist count", "tourist count"],
        "arrivals": [14_600_000, 14_600_000],
    })
    [result] = match_records(records, source)
    assert result.status == "ambiguous"


def test_year_records_are_filtered_out():
    # Years (2009, 2023) are not data values to verify; matcher must not return
    # MatchResults for them, even if a CSV cell happens to equal the year.
    records = extract("From 2009 to 2023, growth was steady.", locale="en")
    source = _source({"col": [2009, 2023]})
    results = match_records(records, source)
    assert results == []


def test_code_records_are_filtered_out():
    # INSEE-classified codes are skipped, even if the CSV has a matching value.
    records = extract("INSEE 75056 (Paris).", locale="fr")
    source = _source({"insee_code": [75056]})
    results = match_records(records, source)
    assert results == []


def test_default_tolerance_catches_display_rounding():
    # Model says "14.6M" -> 14_600_000. CSV holds 14_580_231 (0.13% off).
    # Default 0.5% tolerance must accept this as a match.
    records = extract("Sales were 14.6M total.", locale="en")
    source = _source({"sales": [14_580_231]})
    [result] = match_records(records, source)
    assert result.status == "confirmed"
    assert result.cell.value == 14_580_231.0


def test_default_tolerance_rejects_distinct_values():
    # 14.6M vs 14.5M is 0.685% off; must NOT match at default 0.5% tolerance.
    records = extract("Sales were 14.6M total.", locale="en")
    source = _source({"sales": [14_500_000]})
    [result] = match_records(records, source)
    assert result.status == "unmatched"


def test_tolerance_can_be_overridden():
    # Caller (agent) may pass a looser tolerance. 14.6M vs 14.5M passes at 1%.
    records = extract("Sales were 14.6M total.", locale="en")
    source = _source({"sales": [14_500_000]})
    [result] = match_records(records, source, tolerance=0.01)
    assert result.status == "confirmed"


def test_candidates_field_carries_all_numeric_matches():
    # Format.py uses .candidates to build a "we matched 3 cells but couldn't
    # disambiguate" verification report. All numeric matches must be present
    # regardless of whether disambiguation succeeded.
    records = extract("Tourist arrivals reached 14.6M.", locale="en")
    source = _source({
        "region": ["Auvergne", "Brittany", "Normandy"],
        "arrivals": [14_600_000, 14_600_000, 14_600_000],
    })
    [result] = match_records(records, source)
    assert len(result.candidates) == 3


def test_empty_inputs_produce_empty_results():
    # Boundary: no records, or no source cells, both should yield no errors.
    source = _source({"col": [1, 2, 3]})
    assert match_records([], source) == []

    records = extract("Sales were 14.6M total.", locale="en")
    empty_source = SourceData(cells=[])
    [result] = match_records(records, empty_source)
    assert result.status == "unmatched"
