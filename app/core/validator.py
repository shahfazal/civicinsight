"""
Structural validator for raw model output.

Reports facts about a generated description without making policy decisions:
  - is the [civicinsight-v1] marker present? (gates downstream parsing)
  - how many numeric tokens are present?
  - is a chart type word present? (proxy for "this looks like a chart description")
  - is the prose long enough to be usable?

The agent uses these facts to decide whether to proceed, route to a fallback,
or surface a structural issue to the user. The validator itself does not
return a confidence score; downstream signals (matcher results) carry the
real verification confidence.

Public API:
  - ValidationResult (dataclass)
  - validate(description, min_word_count=20) -> ValidationResult
"""

import re
from dataclasses import dataclass


MARKER = "[civicinsight-v1]"

# Chart type words the SFT model is trained to emit. If any of these appears
# in the prose, the output looks like a chart description.
_CHART_TYPE_WORDS = (
    "bar", "line", "scatter", "pie", "gauge", "map", "table",
    "choropleth", "hexagonal", "hexmap", "heatmap", "box", "stacked",
    "area", "panel", "small multiples",
)

# Cheap numeric token detector. Matches anything resembling a number; it does
# not have to be locale-aware here, since this is a presence check, not parsing.
_NUMERIC_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass
class ValidationResult:
    has_marker: bool
    number_count: int
    has_chart_type: bool
    word_count: int
    issues: list[str]   # human-readable issue strings, empty when prose is sound


def validate(description: str, min_word_count: int = 20) -> ValidationResult:
    """
    Inspect a raw model description and return structural facts plus a list
    of human-readable issues for any axis that looks off.
    """
    has_marker = MARKER in description
    # The marker contains the digit 1 ("[civicinsight-v1]"); strip it before
    # counting numeric tokens so the marker itself does not register as a number.
    description_minus_marker = description.replace(MARKER, "", 1)
    number_count = len(_NUMERIC_PATTERN.findall(description_minus_marker))
    word_count = len(description.split())

    lower = description.lower()
    has_chart_type = any(word in lower for word in _CHART_TYPE_WORDS)

    issues: list[str] = []
    if not has_marker:
        issues.append(f"missing required marker {MARKER}")
    if number_count == 0:
        issues.append("no numeric values present")
    if not has_chart_type:
        issues.append("no chart type word present")
    if word_count < min_word_count:
        issues.append(f"description too short ({word_count} words, expected at least {min_word_count})")

    return ValidationResult(
        has_marker=has_marker,
        number_count=number_count,
        has_chart_type=has_chart_type,
        word_count=word_count,
        issues=issues,
    )
