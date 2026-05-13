"""
Tests for app.core.extract.

Each test asserts behavior the matcher (app.grounding.match) actually depends on.
No coverage filler.
"""

import pytest

from app.core.extract import extract


def test_simple_integer_extraction():
    # The matcher needs canonical numeric values for CSV lookup.
    recs = extract("Sales were 14600000 units.", locale="en")
    [r] = [r for r in recs if r.kind == "value"]
    assert r.value == 14_600_000.0


def test_english_scale_with_decimal():
    # Scale and decimal must combine: 14.6M means fourteen million six hundred thousand.
    # Matcher displays via `scale`, compares numerically via `value`.
    recs = extract("Sales were 14.6M units.", locale="en")
    [r] = [r for r in recs if r.kind == "value"]
    assert r.raw == "14.6M"
    assert r.value == 14_600_000.0
    assert r.scale == "M"


def test_french_scale_with_decimal():
    # Comma-decimal is the dominant French civic format. Same canonical value.
    recs = extract("Les ventes etaient de 14,6M unites.", locale="fr")
    [r] = [r for r in recs if r.kind == "value"]
    assert r.raw == "14,6M"
    assert r.value == 14_600_000.0
    assert r.scale == "M"


def test_french_thousands_with_space():
    # "105 000" appears in held-out outputs (rural-vs-urban etc).
    # Currency detected from following word.
    recs = extract("Le prix etait 105 000 euros.", locale="fr")
    [r] = [r for r in recs if r.kind == "value"]
    assert r.value == 105_000.0
    assert r.is_currency
    assert r.currency == "EUR"


def test_english_thousands_with_comma():
    # English locale: "105,000" is one hundred five thousand, not 105.0.
    recs = extract("The price was 105,000 dollars.", locale="en")
    [r] = [r for r in recs if r.kind == "value"]
    assert r.value == 105_000.0
    assert r.currency == "USD"


def test_locale_changes_meaning_of_single_comma():
    # Same input, different locales, different canonical value.
    fr = extract("105,000", locale="fr")
    en = extract("105,000", locale="en")
    assert fr[0].value == 105.0
    assert en[0].value == 105_000.0


def test_currency_symbol_prefix_dollar():
    recs = extract("Revenue was $40K.", locale="en")
    [r] = [r for r in recs if r.kind == "value"]
    assert r.currency == "USD"
    assert r.scale == "K"
    assert r.value == 40_000.0


def test_currency_symbol_prefix_euro():
    recs = extract("Le revenu etait €40K.", locale="fr")
    [r] = [r for r in recs if r.kind == "value"]
    assert r.currency == "EUR"
    assert r.value == 40_000.0


def test_currency_symbol_following_number():
    # "40 000 €" is the French postfix-symbol form. Common in civic data.
    recs = extract("Le revenu etait 40 000 €.", locale="fr")
    [r] = [r for r in recs if r.kind == "value"]
    assert r.value == 40_000.0
    assert r.currency == "EUR"


def test_percent_french():
    # 2,3% canonicalizes to 0.023 (proportion, not display value).
    recs = extract("Une augmentation de 2,3%.", locale="fr")
    [r] = [r for r in recs if r.is_percent]
    assert r.value == pytest.approx(0.023)
    assert r.kind == "value"


def test_percent_english():
    recs = extract("An increase of 2.3%.", locale="en")
    [r] = [r for r in recs if r.is_percent]
    assert r.value == pytest.approx(0.023)


def test_year_classified_as_year():
    # Matcher must skip years. Classifier identifies bare 4-digit year-range integers.
    recs = extract("In 2024, things happened.", locale="en")
    [r] = recs
    assert r.kind == "year"
    assert r.value == 2024.0


def test_year_range_yields_two_year_records():
    # "from 2009 to 2023" appears in held-outs. Both endpoints classified as year.
    recs = extract("From 2009 to 2023, growth was steady.", locale="en")
    years = [r for r in recs if r.kind == "year"]
    assert {y.value for y in years} == {2009.0, 2023.0}


def test_insee_code_classified_as_code_with_cue():
    # 5-digit number with INSEE cue word in context: classify as code (not value).
    recs = extract("INSEE 75056 (Paris).", locale="fr")
    [r] = recs
    assert r.kind == "code"


def test_five_digit_without_insee_cue_stays_value():
    # A bare 5-digit integer without an INSEE/postal cue is still a value.
    # Avoids false positives in narrative prose like "75056 visitors attended".
    recs = extract("75056 visitors attended.", locale="en")
    [r] = recs
    assert r.kind == "value"
    assert r.value == 75_056.0


def test_eur_per_square_meter_format():
    # Real format from held-out boxplot output: "2643 EUR/m2"
    recs = extract("Median price was 2643 EUR/m2.", locale="en")
    [r] = [r for r in recs if r.kind == "value"]
    assert r.value == 2643.0
    assert r.currency == "EUR"


def test_context_phrase_captures_neighbors():
    # The matcher uses context_phrase to disambiguate when N>1 CSV cells match numerically.
    recs = extract("Auvergne tourist arrivals were 14.6M visitors in 2023.", locale="en")
    rec = next(r for r in recs if r.scale == "M")
    assert "Auvergne" in rec.context_phrase
    assert "tourist" in rec.context_phrase
    assert "visitors" in rec.context_phrase


def test_char_offsets_point_at_raw_substring():
    # The formatter uses char_start/char_end to highlight the matched span.
    # Asserting the slice equals raw protects against off-by-one in the regex post-processing.
    text = "The figure 14.6M dominated the chart."
    [r] = [x for x in extract(text, locale="en") if x.scale == "M"]
    assert text[r.char_start:r.char_end] == r.raw
    assert r.raw == "14.6M"


def test_multiple_numbers_in_one_sentence():
    # Sanity: many numbers in one sentence all extracted, each with correct kind/value.
    text = "Sales rose from 14.6M to 18.2M, a 24% jump."
    recs = extract(text, locale="en")
    values_with_scale = sorted(r.value for r in recs if r.scale == "M")
    assert values_with_scale == [14_600_000.0, 18_200_000.0]
    pct = next(r for r in recs if r.is_percent)
    assert pct.value == pytest.approx(0.24)


def test_empty_text_yields_no_records():
    # Boundary: empty string and whitespace produce no records (no exceptions either).
    assert extract("", locale="fr") == []
    assert extract("No numbers here at all.", locale="fr") == []


def test_axis_cue_classifies_number_as_axis():
    # Numbers following axis cues like "X-axis range 50 to 85" are tick labels,
    # not data values. The matcher relies on this kind to skip them.
    text = "The X-axis labeled 'Year' shows values from 0 to 100 in steps of 25."
    recs = extract(text, locale="en")
    # All numeric records here should be axis-kind.
    kinds = {r.kind for r in recs}
    assert kinds == {"axis"}
    assert all(r.kind == "axis" for r in recs)


def test_axis_cue_does_not_leak_into_subsequent_data_values():
    # The axis classifier looks BACK 30 chars; an axis description earlier in
    # the prose must not contaminate a data value mentioned afterwards.
    text = (
        "The Y-axis shows values from 0 to 100k. "
        "Subsequently, Auvergne tourist arrivals reached 14.6M visitors."
    )
    recs = extract(text, locale="en")
    # The 14.6M is a data value, not axis metadata.
    value = next(r for r in recs if r.scale == "M")
    assert value.kind == "value"


def test_steps_of_phrase_marks_step_value_as_axis():
    # "in steps of 5" - the 5 is the axis step, not a data value.
    text = "The X-axis ranges from 50 to 85, in steps of 5."
    recs = extract(text, locale="en")
    # Find the "5" record (the step). It should be axis-classified.
    five = next(r for r in recs if r.raw == "5")
    assert five.kind == "axis"


# --- Word-form scale tokens (billion / million / thousand / trillion + FR) ---

def test_english_word_form_billion():
    # The OWID-population regression: "1.4 billion" must canonicalise to 1.4e9
    # so the matcher can compare against raw CSV integers like 1438069597.
    text = "The series 'India' is selected with a tooltip showing 1.4 billion in 2023."
    recs = extract(text, locale="en")
    r = next(x for x in recs if x.scale == "B")
    assert r.value == 1_400_000_000.0
    assert r.kind == "value"


def test_english_word_form_million():
    text = "Auvergne tourist arrivals reached 14.6 million visitors."
    recs = extract(text, locale="en")
    r = next(x for x in recs if x.scale == "M")
    assert r.value == 14_600_000.0


def test_english_word_form_thousand():
    text = "The dashboard tracks 105 thousand daily users."
    recs = extract(text, locale="en")
    r = next(x for x in recs if x.scale == "K")
    assert r.value == 105_000.0


def test_english_word_form_trillion():
    text = "Total GDP exceeded 25 trillion dollars."
    recs = extract(text, locale="en")
    r = next(x for x in recs if x.scale == "T")
    assert r.value == 25_000_000_000_000.0


def test_english_plural_word_form():
    # "2 billions" - regex must consume the 's' so raw_end is correct and
    # the canonical value still applies the B scale.
    text = "Two regions exceed 2 billions inhabitants combined."
    recs = extract(text, locale="en")
    r = next(x for x in recs if x.scale == "B")
    assert r.value == 2_000_000_000.0


def test_french_word_form_milliard():
    # FR: "milliard" = English billion (10^9), not million.
    text = "La population mondiale atteint 8 milliards en 2023."
    recs = extract(text, locale="fr")
    r = next(x for x in recs if x.scale == "B")
    assert r.value == 8_000_000_000.0


def test_french_word_form_mille():
    # FR: "mille" = thousand. Distinct from comma/space-separated thousands.
    text = "La commune compte 5 mille habitants."
    recs = extract(text, locale="fr")
    r = next(x for x in recs if x.scale == "K")
    assert r.value == 5_000.0


def test_french_word_form_million_same_as_english():
    # FR "million" = EN "million" (same word, same multiplier). Verifies the
    # word-to-letter table doesn't accidentally divert it elsewhere.
    text = "La région totalise 14,6 millions de visiteurs."
    recs = extract(text, locale="fr")
    r = next(x for x in recs if x.scale == "M")
    assert r.value == 14_600_000.0


def test_word_form_does_not_eat_bare_capital_letter():
    # Regression guard: the alternation must not let "B" inside "By" match
    # as the billion-scale word. The negative lookahead protected this in the
    # letter-only regex; the extended regex must too.
    text = "By 2023, the total reached 1.4 billion."
    recs = extract(text, locale="en")
    # Only one scaled record (the 1.4 billion). The "2023" is a year, not a scale.
    scaled = [r for r in recs if r.scale is not None]
    assert len(scaled) == 1
    assert scaled[0].scale == "B"
    assert scaled[0].value == 1_400_000_000.0
