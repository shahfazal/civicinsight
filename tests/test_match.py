"""
Tests for app.grounding.match.

Each test asserts behavior the formatter (app.core.format) and agent
(app.agent) actually depend on.
"""

import pandas as pd

from app.core.extract import NumberRecord, extract
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


def test_scaled_default_tolerance_catches_display_rounding():
    # "14.6M" with scale "M" gets the scaled adaptive tolerance (5%). Source
    # value 14_580_231 is 0.13% off. Confirmed.
    records = extract("Sales were 14.6M total.", locale="en")
    source = _source({"sales": [14_580_231]})
    [result] = match_records(records, source)
    assert result.status == "confirmed"
    assert result.cell.value == 14_580_231.0


def test_scaled_default_tolerance_rejects_far_off_values():
    # 14.6M vs 12M is 17.8% off; even the scaled 5% tolerance must reject.
    # Documents the upper bound of the default tolerance for scaled values.
    records = extract("Sales were 14.6M total.", locale="en")
    source = _source({"sales": [12_000_000]})
    [result] = match_records(records, source)
    assert result.status == "unmatched"


def test_unscaled_default_tolerance_is_strict():
    # Raw integers (no K/M/B/T suffix) get the strict 0.5% adaptive tolerance.
    # 100 vs 99 is 1% off, must NOT match at default. Validates that the
    # scale-aware logic uses a tighter threshold for unscaled values.
    records = extract("The score was 100 today.", locale="en")
    source = _source({"score": [99]})
    [result] = match_records(records, source)
    assert result.status == "unmatched"


def test_tolerance_can_be_overridden():
    # Explicit override applies to ALL records regardless of scale. 14.6M vs
    # 14.5M = 0.685% off, default scaled tolerance (5%) would match it; but
    # an explicit 0.005 (0.5%) override rejects.
    records = extract("Sales were 14.6M total.", locale="en")
    source = _source({"sales": [14_500_000]})
    [result] = match_records(records, source, tolerance=0.005)
    assert result.status == "unmatched"


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


def test_n1_with_no_context_overlap_does_not_auto_confirm():
    # The Spain/Poland coincidence: model says "Spain at 35k", CSV happens
    # to have Poland at $34,915 (within 5% of 35k). Single numeric match,
    # but the row context says Poland not Spain, so the matcher must NOT
    # silently confirm. This is the headline regression: single-cell
    # auto-confirm was the bug; context check is the fix.
    records = extract("Spain GDP per capita reached 35k in 2021.", locale="en")
    source = _source({
        "country": ["Poland"],
        "gdp_per_capita": [34_915],
    })
    [result] = match_records(records, source)
    assert result.status == "unmatched"
    assert "fabrication" in (result.reason or "").lower()


def test_n1_with_empty_context_phrase_still_confirms():
    # When the description contains no meaningful context tokens (e.g. a bare
    # "14.6M" with nothing around it), there is nothing to disagree with. The
    # single numeric match is the best we can do. Confirm rather than reject.
    records = extract("14.6M", locale="en")
    source = _source({"col": [14_600_000]})
    [result] = match_records(records, source)
    assert result.status == "confirmed"


def test_axis_records_are_filtered_out():
    # Numbers preceded by axis cues ("X-axis range 50 to 85, in steps of 5...")
    # should be classified as kind="axis" and skipped by the matcher. Without
    # this filter, axis ticks pollute the verification report.
    description = "The X-axis labeled 'Year' shows values from 0 to 100 in steps of 25."
    records = extract(description, locale="en")
    # All extracted numbers in this description should be axis-classified, not values.
    value_records = [r for r in records if r.kind == "value"]
    assert value_records == []
    # match_records skips non-value kinds entirely.
    source = _source({"col": [0, 25, 50, 75, 100]})
    assert match_records(records, source) == []


def test_n1_column_name_overlap_confirms():
    # When the prose mentions a CSV column name (e.g. "sales"), that overlap
    # alone is enough to confirm a single numeric match. Validates that
    # column headers are searchable tokens, not just cell values.
    records = extract("Sales were 14.6M total.", locale="en")
    source = _source({"sales": [14_580_231]})
    [result] = match_records(records, source)
    assert result.status == "confirmed"


# --- Precision-aware tolerance for raw decimal display values ---

def test_raw_decimal_match_tolerates_chart_rounding():
    # OWID agricultural-area-per-capita regression: "0.79 ha" (display, 2 decimals)
    # must verify against the CSV's 0.7943 raw value. Drift is 0.55% — outside the
    # old 0.5% relative window, inside the half-last-decimal window of ±0.005.
    rec = NumberRecord(
        raw="0.79", value=0.79, scale=None, kind="value",
        is_percent=False, is_currency=False, currency=None,
        context_phrase="The Africa bar is labeled with 0.79 ha",
        char_start=0, char_end=4, display_decimals=2,
    )
    source = SourceData.from_dataframe(pd.DataFrame({
        "Entity": ["Africa"],
        "Agricultural land per capita": [0.7943493],
    }))
    [result] = match_records([rec], source)
    assert result.status == "confirmed"


def test_raw_decimal_match_tolerates_smaller_value_rounding():
    # "0.59 ha" against CSV 0.5931 — drift is 0.53%, the original 0.5% relative
    # would fail; precision-aware ±0.005 absolute covers it.
    rec = NumberRecord(
        raw="0.59", value=0.59, scale=None, kind="value",
        is_percent=False, is_currency=False, currency=None,
        context_phrase="The World bar is labeled with 0.59 ha",
        char_start=0, char_end=4, display_decimals=2,
    )
    source = SourceData.from_dataframe(pd.DataFrame({
        "Entity": ["World"],
        "Agricultural land per capita": [0.5931124],
    }))
    [result] = match_records([rec], source)
    assert result.status == "confirmed"


def test_raw_decimal_match_still_rejects_unrelated_value():
    # The widened precision window must not admit a clearly different value.
    # "0.79" with ±0.005 abs window: CSV 0.85 is way outside.
    rec = NumberRecord(
        raw="0.79", value=0.79, scale=None, kind="value",
        is_percent=False, is_currency=False, currency=None,
        context_phrase="0.79 ha",
        char_start=0, char_end=4, display_decimals=2,
    )
    source = SourceData.from_dataframe(pd.DataFrame({
        "Entity": ["Africa"],
        "Agricultural land per capita": [0.85],
    }))
    [result] = match_records([rec], source)
    assert result.status == "unmatched"


def test_raw_integer_tolerance_unchanged():
    # display_decimals=0 must keep the existing 0.5% relative tolerance,
    # not balloon to ±0.5 absolute. Value 1.0 must NOT match 1.4.
    rec = NumberRecord(
        raw="1", value=1.0, scale=None, kind="value",
        is_percent=False, is_currency=False, currency=None,
        context_phrase="1 chargers",
        char_start=0, char_end=1, display_decimals=0,
    )
    source = SourceData.from_dataframe(pd.DataFrame({
        "Entity": ["Place"],
        "Count": [1.4],
    }))
    [result] = match_records([rec], source)
    assert result.status == "unmatched"


def test_scaled_record_tolerance_unchanged():
    # Records with scale (K/M/B/T) keep 5% relative tolerance, not the
    # precision-aware path. "1.4 billion" still matches CSV 1.43e9.
    rec = NumberRecord(
        raw="1.4 billion", value=1_400_000_000.0, scale="B", kind="value",
        is_percent=False, is_currency=False, currency=None,
        context_phrase="India 1.4 billion in 2023",
        char_start=0, char_end=11, display_decimals=1,
    )
    source = SourceData.from_dataframe(pd.DataFrame({
        "Entity": ["India"],
        "Population": [1_438_069_597],
    }))
    [result] = match_records([rec], source)
    assert result.status == "confirmed"


def test_raw_decimal_match_large_value_still_uses_relative():
    # When value is large enough that 0.5% relative window > half-last-decimal,
    # the max() picks the relative one — unchanged behavior. "82.1" with 1 decimal:
    # rel window = 0.41, abs window = 0.05. CSV 82.4 is 0.37% off, within
    # relative window → match.
    rec = NumberRecord(
        raw="82.1", value=82.1, scale=None, kind="value",
        is_percent=False, is_currency=False, currency=None,
        context_phrase="life expectancy 82.1",
        char_start=0, char_end=4, display_decimals=1,
    )
    source = SourceData.from_dataframe(pd.DataFrame({
        "Entity": ["X"],
        "Life expectancy": [82.4],
    }))
    [result] = match_records([rec], source)
    # 0.37% off, within 0.5% relative (which is 0.41 absolute on a base of 82).
    assert result.status == "confirmed"
