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


def _tolerance_for(record: NumberRecord, override: Optional[float]) -> float:
    """
    Pick a tolerance for a given record.

    Civic dashboards display values rounded to 1 to 2 significant figures when
    a scale suffix is present ("90k" stands in for $92,862, ~3% off). Raw
    numbers without a scale suffix are usually exact ("82.0" life expectancy).

    Raw decimal-display values carry an implicit precision floor: the chart
    label "0.79" represents a value that's been rounded to 2 decimal places,
    so the underlying CSV can drift up to half-the-last-displayed-digit
    (±0.005 here) before the labels disagree. For small magnitudes (sub-1.0)
    this implicit window is wider than the 0.5% relative default. Use the
    more lenient of the two so chart-rounded labels verify against precise
    source values without admitting unrelated cells.

    Adaptive default reflects this; explicit `override` bypasses entirely.
    """
    if override is not None:
        return override
    if record.scale is not None:
        return 0.05   # 5% for K/M/B/T-suffixed display values
    if record.display_decimals > 0 and record.value != 0:
        # Half-last-displayed-digit absolute window, expressed as relative.
        # max() with the 0.5% baseline keeps existing behavior for larger
        # magnitudes where the relative window is already wider.
        rel_window = 0.005 * abs(record.value)
        abs_window = 0.5 * (10 ** -record.display_decimals)
        return max(rel_window, abs_window) / abs(record.value)
    return 0.005      # 0.5% for raw integer values


def match_records(
    records: list[NumberRecord],
    source: SourceData,
    tolerance: Optional[float] = None,
) -> list[MatchResult]:
    """
    For every value-kind record, return a MatchResult against the source index.

    Year, code, and axis records are filtered out before matching since they
    are not data values to verify.

    tolerance: if None (default), uses scale-aware adaptive tolerance (5% for
    scaled records, 0.5% for raw numbers). Pass an explicit float to apply a
    single tolerance to all records.
    """
    # Description-wide token pool: union every record's context_phrase tokens
    # so an entity mentioned once at the start of a description still anchors
    # numbers near the end. Per-record local windows are too narrow for typical
    # single-chart ARIA prose where all numbers refer to the same chart context.
    description_tokens = set()
    for r in records:
        description_tokens.update(t for t in _tokenize(r.context_phrase) if len(t) >= 4)

    results: list[MatchResult] = []

    for record in records:
        if record.kind != "value":
            continue

        t = _tolerance_for(record, tolerance)
        candidates = source.find_by_value(record.value, t)

        if not candidates:
            results.append(MatchResult(
                record=record,
                status="unmatched",
                cell=None,
                candidates=[],
                reason=None,
            ))
            continue

        cell, reason = _disambiguate(candidates, record, description_tokens)
        if cell is None:
            # Distinguish "candidates exist but context says no" from "multiple
            # candidates we cannot pick between": the matcher returns ambiguous
            # only when there are at least two candidates. A single-candidate
            # mismatch is reported as unmatched with the reason explaining the
            # context-disagreement, since the cell is numerically present but
            # semantically unrelated to the prose.
            status: Status = "ambiguous" if len(candidates) > 1 else "unmatched"
            results.append(MatchResult(
                record=record,
                status=status,
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
    description_tokens: set[str],
) -> tuple[Optional[SourceCell], Optional[str]]:
    """
    Pick the single best cell from a list of numerically-matching candidates.

    Returns (cell, None) when a unique winner is found.
    Returns (None, reason) when context cannot disambiguate.

    Single-candidate matches are NOT auto-confirmed: if the prose carries any
    meaningful context tokens and none of them appear in the candidate row,
    the numeric coincidence is treated as a context-mismatch (likely the model
    fabricated a value that happens to coincide with another row's data).

    description_tokens is the description-wide token pool computed by
    match_records; used as the context against which candidates are scored.
    """
    context_tokens = description_tokens

    # Score every candidate by token overlap with its row_context. We include
    # both the row's cell values AND the column headers, since the prose may
    # use column names ("sales", "arrivals") as semantic anchors even when no
    # entity from the row appears in the description.
    scored: list[tuple[int, SourceCell]] = []
    for cell in candidates:
        cell_tokens: set[str] = set()
        for k, v in cell.row_context.items():
            cell_tokens.update(_tokenize(k))
            cell_tokens.update(_tokenize(v))
        overlap = len(context_tokens & cell_tokens)
        scored.append((overlap, cell))

    scored.sort(key=lambda pair: -pair[0])

    # Single candidate: confirm only if context agrees, OR if the prose has no
    # meaningful context to check. "No context to check" is the legitimate case
    # of e.g. axis-removed inputs where there is nothing semantic around the value.
    if len(candidates) == 1:
        if not context_tokens:
            return candidates[0], None
        if scored[0][0] > 0:
            return candidates[0], None
        return None, (
            "A numeric match exists in the source data but its row does not "
            "contain any of the entities mentioned in the description; the "
            "value may be a fabrication coinciding with an unrelated row"
        )

    # Multiple candidates: need context to pick.
    if not context_tokens:
        return None, "Multiple matches and insufficient context to disambiguate"

    if scored[0][0] == 0:
        return None, "Multiple matches found; no context overlap with any candidate"

    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None, (
            f"Multiple matches found with equal context overlap "
            f"({scored[0][0]} tokens each); cannot disambiguate"
        )

    return scored[0][1], None
