"""
Tests for app.agent.

The agent is exercised end-to-end with a stubbed infer_fn so tests do not
hit Modal. Real Modal invocation is verified by running the demo against a
real upload.
"""

import pandas as pd

from app.agent import run
from app.core.validator import MARKER


_GOOD_DESCRIPTION = (
    f"{MARKER} This line chart shows tourist arrivals in Auvergne. "
    "Total arrivals reached 14.6M visitors in 2023, up from 12.0M in 2020."
)


def _stub_infer(_image_bytes):
    """Returns the same canned prose regardless of input."""
    return _GOOD_DESCRIPTION


def test_image_only_path_returns_unverified(tmp_path):
    out = run(image_bytes=b"fake-image-data", csv_path=None, infer_fn=_stub_infer)
    assert out.data_status == "unverified"
    assert out.confidence is None
    assert out.aria_label.startswith("This line chart")


def test_image_plus_csv_path_with_full_match_returns_verified(tmp_path):
    csv = tmp_path / "tourism.csv"
    csv.write_text("region,arrivals\nAuvergne,14600000\nAuvergne,12000000\n")
    out = run(image_bytes=b"fake", csv_path=csv, infer_fn=_stub_infer)
    assert out.data_status == "verified"
    assert out.confidence == 1.0


def test_image_plus_csv_path_with_partial_match_returns_partial(tmp_path):
    # Only one of the two values appears in the CSV.
    csv = tmp_path / "tourism.csv"
    csv.write_text("region,arrivals\nAuvergne,14600000\n")
    out = run(image_bytes=b"fake", csv_path=csv, infer_fn=_stub_infer)
    assert out.data_status == "partial"
    assert out.confidence == 0.5


def test_missing_marker_short_circuits_grounding(tmp_path):
    # If the model output lacks the marker, the agent must NOT call extract or
    # match. The structural-issue path returns immediately. We assert this by
    # providing a CSV that would otherwise produce a verified outcome and
    # checking the agent did not "verify" anything.
    def stub_no_marker(_image_bytes):
        return "Some unrelated text that is not a CivicInsight response."

    csv = tmp_path / "tourism.csv"
    csv.write_text("region,arrivals\nAuvergne,14600000\n")
    out = run(image_bytes=b"fake", csv_path=csv, infer_fn=stub_no_marker)
    assert out.data_status == "structural-issue"
    assert out.confidence == 0.0
    assert out.verification_details == []


def test_infer_fn_receives_the_image_bytes():
    # Confirms the agent passes the image bytes through to infer untouched.
    captured = {}

    def capturing_stub(image_bytes):
        captured["bytes"] = image_bytes
        return _GOOD_DESCRIPTION

    run(image_bytes=b"specific-bytes", csv_path=None, infer_fn=capturing_stub)
    assert captured["bytes"] == b"specific-bytes"


def test_tolerance_override_propagates_to_matcher(tmp_path):
    # The agent passes tolerance through to match_records. With strict 0.0
    # tolerance, a 0.13%-off CSV value must NOT match.
    csv = tmp_path / "tourism.csv"
    csv.write_text("region,arrivals\nAuvergne,14580231\nAuvergne,12000000\n")
    out = run(image_bytes=b"fake", csv_path=csv, tolerance=0.0, infer_fn=_stub_infer)
    # 14.6M does not exact-match 14_580_231; only 12.0M matches 12_000_000.
    assert out.confidence == 0.5
