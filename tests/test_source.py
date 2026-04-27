"""
Tests for app.grounding.source.

Each test asserts behavior the matcher (app.grounding.match) actually depends on.
No coverage filler.
"""

import pandas as pd
import pytest

from app.grounding.source import SourceCell, SourceData


def test_dataframe_indexes_only_numeric_cells():
    # Text columns (e.g. region names) must be skipped; numeric columns indexed.
    df = pd.DataFrame({
        "region": ["Auvergne", "Brittany"],
        "arrivals": [14_600_000, 8_500_000],
    })
    source = SourceData.from_dataframe(df)
    columns_present = {c.column for c in source.cells}
    assert "region" not in columns_present
    assert "arrivals" in columns_present


def test_cell_carries_column_row_index_and_context():
    # The matcher uses column + row_index to identify the cell in verification
    # reports, and row_context to disambiguate when multiple cells match.
    df = pd.DataFrame({
        "region": ["Auvergne", "Brittany"],
        "arrivals": [14_600_000, 8_500_000],
    })
    source = SourceData.from_dataframe(df)
    auvergne = next(c for c in source.cells if c.value == 14_600_000.0)
    assert auvergne.column == "arrivals"
    assert auvergne.row_index == 0
    assert auvergne.row_context["region"] == "Auvergne"
    assert auvergne.row_context["arrivals"] == "14600000"


def test_find_by_value_exact_with_zero_tolerance():
    df = pd.DataFrame({"col": [100, 200, 300]})
    source = SourceData.from_dataframe(df)
    [match] = source.find_by_value(200.0, tolerance=0.0)
    assert match.value == 200.0


def test_find_by_value_within_tolerance_catches_display_rounding():
    # The model emits "14.6M" -> 14_600_000. CSV may have the exact source
    # value 14_580_231 (0.13% off). Both should match at 0.5% tolerance.
    df = pd.DataFrame({"col": [14_580_231, 14_600_000]})
    source = SourceData.from_dataframe(df)
    matches = source.find_by_value(14_600_000.0, tolerance=0.005)
    assert {m.value for m in matches} == {14_580_231.0, 14_600_000.0}


def test_find_by_value_excludes_distant_values():
    # 14M vs 14.6M is ~4% off; must not match at 0.5% tolerance.
    df = pd.DataFrame({"col": [14_000_000, 14_600_000]})
    source = SourceData.from_dataframe(df)
    [match] = source.find_by_value(14_600_000.0, tolerance=0.005)
    assert match.value == 14_600_000.0


def test_find_by_value_returns_empty_when_nothing_matches():
    df = pd.DataFrame({"col": [100, 200]})
    source = SourceData.from_dataframe(df)
    assert source.find_by_value(999.0, tolerance=0.005) == []


def test_find_by_value_zero_requires_exact_match():
    # Relative tolerance is undefined at zero; only exact matches qualify.
    df = pd.DataFrame({"col": [0, 0.001, 1.0]})
    source = SourceData.from_dataframe(df)
    [match] = source.find_by_value(0.0, tolerance=0.5)
    assert match.value == 0.0


def test_cell_with_scale_canonicalizes_via_extract():
    # CSVs sometimes carry display-formatted strings ("14.6M visitors").
    # The cell value must be the canonical 14_600_000, matching what the
    # extractor produces from prose, so prose vs CSV are comparable.
    df = pd.DataFrame({"label": ["14.6M visitors"]})
    source = SourceData.from_dataframe(df)
    [cell] = source.cells
    assert cell.value == 14_600_000.0


def test_percent_cell_canonicalizes_to_proportion():
    # "2.3%" must become 0.023 to match what extract() produces from prose.
    df = pd.DataFrame({"share": ["2.3%"]})
    source = SourceData.from_dataframe(df)
    [cell] = source.cells
    assert cell.value == pytest.approx(0.023)


def test_from_csv_reads_a_real_file(tmp_path):
    # Gradio passes uploaded files as paths; this is the production entry point.
    csv = tmp_path / "tourism.csv"
    csv.write_text("region,arrivals\nAuvergne,14600000\nBrittany,8500000\n")
    source = SourceData.from_csv(csv)
    arrivals = sorted(c.value for c in source.cells if c.column == "arrivals")
    assert arrivals == [8_500_000.0, 14_600_000.0]


def test_row_context_lets_matcher_disambiguate_repeated_values():
    # Civic dashboards repeat values across rows. row_context is what lets
    # the matcher pick the right cell when prose says "Auvergne 14.6M":
    # both cells match numerically; only one has "Auvergne" in row_context.
    df = pd.DataFrame({
        "region": ["Auvergne", "Brittany"],
        "arrivals": [14_600_000, 14_600_000],
    })
    source = SourceData.from_dataframe(df)
    matches = source.find_by_value(14_600_000.0, tolerance=0.0)
    assert len(matches) == 2
    regions_in_context = {m.row_context["region"] for m in matches}
    assert regions_in_context == {"Auvergne", "Brittany"}
