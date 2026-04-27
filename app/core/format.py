"""
Output assembly: take the model's prose, the structural validation result,
and the matcher's per-value outcomes, and produce the final structured object
that the Gradio UI renders.

Design choice: the model's description is passed through untouched (with the
internal marker stripped for cleaner screen-reader output). Verification
information is delivered as a separate structured annotation, NOT as in-place
edits to the prose. This keeps the description aurally clean and lets the UI
highlight verification status independently.

Public API:
  - FormattedOutput (dataclass)
  - format_output(description, validation, match_results=None) -> FormattedOutput
"""

from dataclasses import dataclass
from typing import Optional

from app.core.validator import MARKER, ValidationResult
from app.grounding.match import MatchResult


@dataclass
class FormattedOutput:
    aria_label: str                    # description with marker stripped, ready for ARIA
    data_status: str                   # "verified" | "partial" | "unverified" | "structural-issue"
    confidence: Optional[float]        # confirmed/total for image+CSV; None for image-only
    verification_summary: str          # one-line summary intended for screen readers
    verification_details: list[str]    # per-value lines, one per MatchResult
    structural_issues: list[str]       # validator-flagged issues (empty when prose is sound)


def format_output(
    description: str,
    validation: ValidationResult,
    match_results: Optional[list[MatchResult]] = None,
) -> FormattedOutput:
    """
    Assemble the final structured output.

    match_results is None for the image-only path (no CSV uploaded) and a list
    for the image+CSV path. The agent decides which to pass.
    """
    aria_label = description.replace(MARKER, "", 1).strip()

    # Structural failure short-circuits everything else: if the marker is
    # missing the model output cannot be trusted, regardless of CSV grounding.
    if not validation.has_marker:
        return FormattedOutput(
            aria_label=aria_label,
            data_status="structural-issue",
            confidence=0.0,
            verification_summary=(
                "This output does not appear to be a CivicInsight model response. "
                "It may be unrelated to a data visualization."
            ),
            verification_details=[],
            structural_issues=validation.issues,
        )

    # Image-only path: no source data, no numeric verification possible.
    if match_results is None:
        return FormattedOutput(
            aria_label=aria_label,
            data_status="unverified",
            confidence=None,
            verification_summary=(
                "No source data provided. Numeric values are extracted from the image "
                "and have not been verified against any external dataset."
            ),
            verification_details=[],
            structural_issues=validation.issues,
        )

    # Image+CSV path: bucket each match result and build a per-value detail line.
    confirmed = [r for r in match_results if r.status == "confirmed"]
    ambiguous = [r for r in match_results if r.status == "ambiguous"]
    unmatched = [r for r in match_results if r.status == "unmatched"]
    total = len(match_results)

    if total == 0:
        # No value-kind records to verify (only years/codes were present).
        return FormattedOutput(
            aria_label=aria_label,
            data_status="unverified",
            confidence=None,
            verification_summary=(
                "Source data was provided but the description contained no numeric "
                "values eligible for verification."
            ),
            verification_details=[],
            structural_issues=validation.issues,
        )

    confidence = len(confirmed) / total
    if confidence == 1.0:
        data_status = "verified"
    elif len(confirmed) > 0:
        data_status = "partial"
    else:
        data_status = "unverified"

    summary_parts = [f"{len(confirmed)} of {total} numeric values verified against source data."]
    if ambiguous:
        summary_parts.append(f"{len(ambiguous)} ambiguous (multiple matches).")
    if unmatched:
        summary_parts.append(f"{len(unmatched)} unverified (no matching source value).")
    verification_summary = " ".join(summary_parts)

    verification_details: list[str] = []
    for r in match_results:
        if r.status == "confirmed":
            verification_details.append(
                f"Verified: '{r.record.raw}' matches source "
                f"(column '{r.cell.column}', row {r.cell.row_index})."
            )
        elif r.status == "ambiguous":
            verification_details.append(
                f"Ambiguous: '{r.record.raw}' could match {len(r.candidates)} cells. "
                f"{r.reason}."
            )
        else:
            # Unmatched comes in two flavors: no candidates anywhere, or a
            # single candidate whose row context does not match the prose
            # (likely fabrication). Use the reason text when present so the
            # user sees the more specific signal.
            if r.reason:
                verification_details.append(
                    f"Unverified: '{r.record.raw}'. {r.reason}."
                )
            else:
                verification_details.append(
                    f"Unverified: '{r.record.raw}' has no matching value in source data."
                )

    return FormattedOutput(
        aria_label=aria_label,
        data_status=data_status,
        confidence=confidence,
        verification_summary=verification_summary,
        verification_details=verification_details,
        structural_issues=validation.issues,
    )
