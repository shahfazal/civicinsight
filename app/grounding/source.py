"""
CSV ingestion: turn a tabular file into a searchable index of numeric cells
with row context preserved.

Each numeric cell becomes a SourceCell carrying:
  - the canonical numeric value (parsed via app.core.extract for unit/scale handling)
  - the original raw string from the cell
  - the column header
  - the 0-based row index
  - a dict of every cell in the same row, keyed by column header

The row_context dict is the disambiguation hook for the matcher: when several
cells match a number numerically, the matcher uses row_context to find the one
whose siblings overlap with the model's surrounding prose.

Public API:
  - SourceCell (dataclass)
  - SourceData (with .from_csv, .from_dataframe, .find_by_value)
"""

import csv
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Union

import pandas as pd

from app.core.extract import extract


class CSVLoadError(Exception):
    """Raised when a CSV file cannot be loaded into a SourceData index.

    The agent catches this and surfaces the message in the verification report
    as a structural issue rather than letting the traceback escape to the UI.
    """


# Hardening limits. Tunable; current values protect against:
#   - 50 MB ceiling: avoids Modal container OOM
#   - 500k row hard reject: same; matching N records against 500k cells is also slow
#   - 50k row warn threshold (informational only, not enforced here)
_MAX_BYTES = 50 * 1024 * 1024
_MAX_ROWS = 500_000

# Encoding fallback chain. Ordered most-likely to least-likely for civic CSVs:
#   utf-8 (default), utf-8-sig (Excel BOM), utf-16 (BOM-detected),
#   latin-1 (legacy Western European), cp1252 (Windows-1252).
#
# Note: utf-16-le and utf-16-be are deliberately omitted. They always "succeed"
# on any byte stream (interpreting bytes pairwise as endian codepoints) and
# would mask the latin-1/cp1252 fallbacks for non-utf-16 inputs. Plain utf-16
# requires a BOM and raises cleanly when one is absent.
_ENCODING_CHAIN = ["utf-8", "utf-8-sig", "utf-16", "latin-1", "cp1252"]


def _sniff_delimiter(sample: str) -> str:
    """Detect CSV delimiter from a sample. Falls back to comma on ambiguity."""
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return ","


def _read_text_with_fallback(path: Path) -> tuple[str, str]:
    """
    Decode a file as text, trying encodings in the fallback chain.
    Returns (text, encoding_used). Raises CSVLoadError if no encoding works.
    """
    last_err: Exception = UnicodeDecodeError("none", b"", 0, 0, "no encodings tried")
    for enc in _ENCODING_CHAIN:
        try:
            return path.read_text(encoding=enc), enc
        except (UnicodeDecodeError, UnicodeError) as e:
            last_err = e
    raise CSVLoadError(
        f"Could not decode the file with any of: {', '.join(_ENCODING_CHAIN)}. "
        f"Last error: {last_err}"
    )


@dataclass
class SourceCell:
    value: float                    # canonical numeric value after parsing
    raw: str                        # original cell text as it appeared
    column: str                     # column header
    row_index: int                  # 0-based position in the source frame
    row_context: dict[str, str]     # every cell in this row, keyed by column header


class SourceData:
    """A cell-level numeric index built from a CSV or DataFrame."""

    def __init__(self, cells: list[SourceCell]):
        self.cells = cells

    @classmethod
    def from_csv(cls, path: Union[str, Path], locale: str = "en") -> "SourceData":
        """
        Read a CSV file into a SourceData index, with hardening:

          - rejects empty files and files larger than 50 MB
          - decodes via an encoding fallback chain (utf-8, utf-8-sig, utf-16,
            latin-1, cp1252) so Excel-on-Windows exports load without ceremony
          - sniffs the delimiter (comma, tab, semicolon, pipe) so non-comma
            CSVs do not silently load as one giant single-column DataFrame
          - rejects DataFrames with more rows than the matcher can usefully
            handle (default cap: 500 000 rows)

        Any failure raises CSVLoadError. The agent catches CSVLoadError and
        surfaces the message in the verification report's structural_issues
        list rather than letting a traceback escape to the UI.
        """
        p = Path(path)
        if not p.exists():
            raise CSVLoadError(f"File not found: {path}")

        size = p.stat().st_size
        if size == 0:
            raise CSVLoadError("File is empty.")
        if size > _MAX_BYTES:
            raise CSVLoadError(
                f"File is {size / 1024 / 1024:.1f} MB; max accepted is "
                f"{_MAX_BYTES / 1024 / 1024:.0f} MB. Trim or summarize the data first."
            )

        text, encoding = _read_text_with_fallback(p)

        # Use a sample of the head for delimiter sniffing; whole-file would be
        # wasteful and the delimiter is consistent throughout a real CSV.
        sample = text[:8192]
        delimiter = _sniff_delimiter(sample)

        try:
            df = pd.read_csv(StringIO(text), sep=delimiter, on_bad_lines="warn")
        except pd.errors.EmptyDataError:
            raise CSVLoadError("File contains no parseable CSV content.")
        except pd.errors.ParserError as e:
            raise CSVLoadError(f"Could not parse CSV: {e}")
        except Exception as e:
            raise CSVLoadError(f"Unexpected error reading CSV: {e}")

        if len(df) > _MAX_ROWS:
            raise CSVLoadError(
                f"File has {len(df):,} rows; max accepted is {_MAX_ROWS:,}. "
                f"Trim to a representative subset for verification."
            )

        return cls.from_dataframe(df, locale=locale)

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame, locale: str = "en") -> "SourceData":
        """Build a SourceData index from an existing DataFrame."""
        cells: list[SourceCell] = []
        columns = list(df.columns)

        for row_index in range(len(df)):
            row = df.iloc[row_index]
            row_context = {col: str(row[col]) for col in columns}

            for col in columns:
                raw = row_context[col]
                records = extract(raw, locale=locale)
                if not records:
                    continue
                # A cell with multiple numbers (rare, e.g., "between 10 and 20")
                # contributes only its first recognized value. The full raw
                # string is preserved on the SourceCell so callers can inspect.
                rec = records[0]
                cells.append(SourceCell(
                    value=rec.value,
                    raw=raw,
                    column=col,
                    row_index=row_index,
                    row_context=row_context,
                ))

        return cls(cells)

    def find_by_value(self, value: float, tolerance: float) -> list[SourceCell]:
        """
        Return cells whose value matches `value` within relative tolerance.

        Tolerance is relative (0.005 = 0.5%). For value=0, only exact matches
        are returned, since relative tolerance is undefined at zero.
        """
        matches: list[SourceCell] = []
        for cell in self.cells:
            if cell.value == value:
                matches.append(cell)
                continue
            if value == 0:
                continue
            if abs(cell.value - value) / abs(value) <= tolerance:
                matches.append(cell)
        return matches
