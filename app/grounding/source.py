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

from dataclasses import dataclass
from pathlib import Path
from typing import Union

import pandas as pd

from app.core.extract import extract


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
        """Read a CSV file into a SourceData index."""
        df = pd.read_csv(path)
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
