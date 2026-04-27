"""
Tests for app.io.inference.

Only the pure-local logic is unit tested. The Modal-side @app.cls path requires
a deployed function to exercise; that is integration testing, not unit, and
is verified by running the demo against a real upload.
"""

from app.io.inference import strip_chat_wrapping


def test_strip_chat_wrapping_removes_user_prompt_prefix():
    # Mirrors what tokenizer.decode produces with skip_special_tokens=True
    # after the model emits its turn. Format documented in notebook 07.
    decoded = (
        "user\n"
        "Generate an aria-label for this data visualization image.\n"
        "model\n"
        "[civicinsight-v1] This line chart shows arrivals."
    )
    assert strip_chat_wrapping(decoded) == "[civicinsight-v1] This line chart shows arrivals."


def test_strip_chat_wrapping_preserves_marker_and_prose():
    # The caller expects the marker untouched; validator and formatter rely on it.
    decoded = "model\n[civicinsight-v1] Test description."
    out = strip_chat_wrapping(decoded)
    assert out.startswith("[civicinsight-v1]")


def test_strip_chat_wrapping_with_no_delimiter_returns_input_trimmed():
    # Defensive: if the chat template ever changes, return the input unchanged
    # rather than mangling it. Validator will catch the missing marker.
    decoded = "  Some unexpected output without the marker  "
    assert strip_chat_wrapping(decoded) == "Some unexpected output without the marker"
