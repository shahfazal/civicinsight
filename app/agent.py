"""
Routing orchestrator. Single entry point that branches between the image-only
and image+CSV paths, calling the model and the grounding pipeline in the
right order.

Routing decisions:
  1. Run inference on the image.
  2. Run structural validator on the prose.
     - If marker is missing: short-circuit to structural-issue, do not ground.
  3. If no CSV provided: image-only path, return formatted output as
     "unverified" with no per-value details.
  4. If CSV provided: extract numbers, build source index, match each value
     record, format with verification details and confidence.

Public API:
  - run(image_bytes, csv_path=None, csv_bytes=None, locale="en", tolerance=0.005, infer_fn=None)
"""

from pathlib import Path
from typing import Callable, Optional, Union

from app.core.extract import extract
from app.core.format import FormattedOutput, format_output
from app.core.validator import validate
from app.grounding.match import match_records
from app.grounding.source import CSVLoadError, SourceData


def run(
    image_bytes: bytes,
    csv_path: Optional[Union[str, Path]] = None,
    csv_bytes: Optional[bytes] = None,
    locale: str = "en",
    tolerance: Optional[float] = None,
    infer_fn: Optional[Callable[[bytes], str]] = None,
) -> FormattedOutput:
    """
    Run the full pipeline on an image (and optional CSV).

    Pass CSV content via exactly one of:
      - csv_bytes: raw CSV bytes (preferred for web uploads, avoids temp-file
        lifecycle issues during long-running inferences)
      - csv_path: filesystem path to a CSV file (used by tests and scripts)

    tolerance: if None (default), uses scale-aware adaptive tolerance from
    match.py (5% for K/M/B/T-suffixed values, 0.5% for raw numbers). Pass an
    explicit float to apply a single tolerance to all records.

    infer_fn: optional override for the inference call. Defaults to the
    Modal-deployed InferenceServer via app.io.inference.infer. Tests inject
    a stub that returns canned prose.
    """
    if csv_bytes is not None and csv_path is not None:
        raise ValueError("Pass exactly one of csv_bytes or csv_path, not both.")

    if infer_fn is None:
        # Lazy import: avoids bringing modal into the import path for callers
        # that pass their own infer_fn.
        from app.io.inference import infer as default_infer
        infer_fn = default_infer

    description = infer_fn(image_bytes)
    validation = validate(description)

    # Structural failure short-circuits grounding. Never call the matcher on
    # output we cannot anchor to a CivicInsight model response.
    if not validation.has_marker:
        return format_output(description, validation, match_results=None)

    # Image-only path: no CSV, no per-value verification possible.
    if csv_path is None and csv_bytes is None:
        return format_output(description, validation, match_results=None)

    # Image+CSV path: extract, build source index, match, format.
    records = extract(description, locale=locale)

    try:
        if csv_bytes is not None:
            source = SourceData.from_csv_bytes(csv_bytes, locale=locale)
        else:
            source = SourceData.from_csv(csv_path, locale=locale)
    except CSVLoadError as csv_err:
        # CSV failed to parse. Fall back to the image-only output and surface
        # the parse error in structural_issues so the user sees a meaningful
        # message instead of a Python traceback. The model description still
        # renders; only the per-value verification is skipped.
        result = format_output(description, validation, match_results=None)
        result.structural_issues = list(result.structural_issues) + [
            f"Source CSV could not be loaded: {csv_err}"
        ]
        return result

    matches = match_records(records, source, tolerance=tolerance)

    return format_output(description, validation, match_results=matches)
