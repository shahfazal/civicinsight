"""
Tests for app.core.validator.

Each test asserts a fact the agent (app.agent) actually depends on to decide
whether to proceed with grounding or surface a structural issue.
"""

from app.core.validator import MARKER, validate


_GOOD = (
    f"{MARKER} This line chart titled The Rise of Google Chrome shows web "
    "browser market share from 2009 to 2023. The Y-axis shows market share "
    "from 0 to 60% in steps of 10. The series Other is selected with a "
    "tooltip showing 9% in October 2020."
)


def test_well_formed_output_has_no_issues():
    # The Exp 4b held-out output passes all structural checks.
    result = validate(_GOOD)
    assert result.has_marker
    assert result.number_count > 0
    assert result.has_chart_type
    assert result.word_count >= 20
    assert result.issues == []


def test_missing_marker_is_flagged():
    # Marker absence is the most important signal: the agent must NOT proceed
    # with grounding on prose the SFT model did not anchor.
    output = _GOOD.replace(MARKER + " ", "", 1)
    result = validate(output)
    assert not result.has_marker
    assert any("marker" in issue for issue in result.issues)


def test_no_numbers_is_flagged():
    # An ARIA description without numbers is functionally useless for
    # accessibility (matches the AltText.ai failure mode we are explicitly fixing).
    output = f"{MARKER} This bar chart shows tourism arrivals across regions of France."
    result = validate(output)
    assert result.number_count == 0
    assert any("numeric" in issue for issue in result.issues)


def test_missing_chart_type_is_flagged():
    # No chart-type word -> probably not a chart description (could be a photo, doc, etc).
    output = f"{MARKER} This image contains the value 14.6M and the figure 2.3 percent."
    result = validate(output)
    assert not result.has_chart_type
    assert any("chart type" in issue for issue in result.issues)


def test_short_output_is_flagged():
    # Suspiciously short output indicates the model bailed or refused.
    output = f"{MARKER} A bar chart."
    result = validate(output, min_word_count=20)
    assert result.word_count < 20
    assert any("too short" in issue for issue in result.issues)


def test_min_word_count_is_configurable():
    # Caller (agent) may relax this for charts known to be label-only.
    output = f"{MARKER} A bar chart with 14M total."
    result = validate(output, min_word_count=5)
    assert not any("too short" in issue for issue in result.issues)


def test_number_count_uses_locale_agnostic_detection():
    # Validator does presence-counting only, not parsing. Both decimal styles count.
    output = f"{MARKER} This bar chart shows 14.6 and 14,6 and 105 000."
    result = validate(output)
    # "14.6" -> 1, "14,6" -> 1, "105" -> 1, "000" -> 1. Cheap counter, that's fine.
    assert result.number_count >= 3


def test_empty_input_collects_all_issues():
    # Defensive: empty string should report each axis as failing, no exceptions.
    result = validate("")
    assert not result.has_marker
    assert result.number_count == 0
    assert not result.has_chart_type
    assert result.word_count == 0
    # Every axis flagged.
    assert len(result.issues) == 4
