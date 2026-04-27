"""
Numeric matcher: take NumberRecords from extract and a SourceData index, and
report for each value record whether it was confirmed, ambiguous, or unmatched.

Match algorithm:
  1. Skip records whose kind is not "value" (year/code records are not data
     values to verify).
  2. Find SourceCells whose canonical value matches within relative tolerance.
  3. If a single cell matches: confirmed.
  4. If multiple cells match: disambiguate via token overlap between the
     record's context_phrase and each cell's row_context. Pick the unique
     highest-overlap candidate. Tie or zero overlap -> ambiguous.
  5. If no cells match within tolerance: unmatched.

Tolerance: 0.5% relative is the default. This catches display rounding
(model says 14.6M, CSV holds 14,580,231) without admitting unrelated values
(14.6M vs 14.5M is 0.685% off and stays distinct).

There is no "corrected" status in v1. Proposing a correction requires either
a second model pass (L3) or fuzzy column-name matching that risks confidently
mislabeling unrelated cells. Honest "unmatched" is the v1 contract.

Public API:
  - MatchResult (dataclass)
  - match_records(records, source, tolerance=0.005) -> list[MatchResult]
"""

import re
from dataclasses import dataclass
from typing import Literal, Optional

from app.core.extract import NumberRecord
from app.grounding.source import SourceCell, SourceData


Status = Literal["confirmed", "ambiguous", "unmatched"]


@dataclass
class MatchResult:
    record: NumberRecord
    status: Status
    cell: Optional[SourceCell]      # the matched cell, when status is confirmed
    candidates: list[SourceCell]    # all numeric matches before disambiguation
    reason: Optional[str]           # human-readable explanation for non-confirmed outcomes


def match_records(
    records: list[NumberRecord],
    source: SourceData,
    tolerance: float = 0.005,
) -> list[MatchResult]:
    """
    For every value-kind record, return a MatchResult against the source index.

    Year and code records are filtered out before matching since they are not
    data values to verify.
    """
    results: list[MatchResult] = []

    for record in records:
        if record.kind != "value":
            continue

        candidates = source.find_by_value(record.value, tolerance)

        if not candidates:
            results.append(MatchResult(
                record=record,
                status="unmatched",
                cell=None,
                candidates=[],
                reason=None,
            ))
            continue

        cell, reason = _disambiguate(candidates, record)
        if cell is None:
            results.append(MatchResult(
                record=record,
                status="ambiguous",
                cell=None,
                candidates=candidates,
                reason=reason,
            ))
        else:
            results.append(MatchResult(
                record=record,
                status="confirmed",
                cell=cell,
                candidates=candidates,
                reason=None,
            ))

    return results


def _tokenize(text: str) -> set[str]:
    """Return a set of lowercase alphanumeric word tokens."""
    return set(re.findall(r"\w+", text.lower()))


def _disambiguate(
    candidates: list[SourceCell],
    record: NumberRecord,
) -> tuple[Optional[SourceCell], Optional[str]]:
    """
    Pick the single best cell from a list of numerically-matching candidates.

    Returns (cell, None) when a unique winner is found.
    Returns (None, reason) when context cannot disambiguate.
    """
    if len(candidates) == 1:
        return candidates[0], None

    # Tokens shorter than 4 chars are noise ("the", "of", "is").
    context_tokens = {t for t in _tokenize(record.context_phrase) if len(t) >= 4}
    if not context_tokens:
        return None, "Insufficient context to disambiguate among multiple matches"

    scored: list[tuple[int, SourceCell]] = []
    for cell in candidates:
        cell_tokens: set[str] = set()
        for v in cell.row_context.values():
            cell_tokens.update(_tokenize(v))
        overlap = len(context_tokens & cell_tokens)
        scored.append((overlap, cell))

    scored.sort(key=lambda pair: -pair[0])

    if scored[0][0] == 0:
        return None, "Multiple matches found; no context overlap with any candidate"

    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None, (
            f"Multiple matches found with equal context overlap "
            f"({scored[0][0]} tokens each); cannot disambiguate"
        )

    return scored[0][1], None
