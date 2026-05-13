"""
Number extraction from prose.

Takes model-generated prose like:
  "[civicinsight-v1] This box plot shows median price 2643 EUR/m2..."
and returns a list of NumberRecord values that downstream components
(matcher, validator, formatter) operate on.

Public API:
  - NumberRecord (dataclass)
  - extract(text, locale="en") -> list[NumberRecord]

Locale ("en" or "fr") only matters for tokens with one separator and three
trailing digits, where the separator could be either thousands or decimal:
  - "1,234"  ->  1234   (en, comma is thousands)   |   1.234   (fr, comma is decimal)
  - "1.234"  ->  1.234  (en, period is decimal)    |   1234    (fr, period is rare thousands)
  - "1 234"  ->  1234 in either locale (space is unambiguous thousands)
  - "14,6"   ->  14.6 in either locale (single comma, non-3 trailing -> decimal)

In practice, French civic dashboards use space-thousands and comma-decimal,
so the ambiguous cases above rarely appear in fr-locale text.
"""

import re
from dataclasses import dataclass
from typing import Literal, Optional


Kind = Literal["value", "year", "code", "axis"]


@dataclass
class NumberRecord:
    raw: str                 # exactly as it appeared in the source prose
    value: float             # canonical numeric value (after scale and percent applied)
    scale: Optional[str]     # one of "K", "M", "B", "T", or None
    kind: Kind               # "value" (real data), "year", "code" (INSEE/postal), or "axis"
    is_percent: bool
    is_currency: bool
    currency: Optional[str]  # ISO code: "EUR", "USD", "GBP", "JPY", or None
    context_phrase: str      # window of surrounding text (for downstream disambiguation)
    char_start: int          # offset of the matched token in the original prose
    char_end: int


_CURRENCY_BY_SYMBOL = {
    "€": "EUR",   # euro
    "$": "USD",
    "£": "GBP",   # pound
    "¥": "JPY",   # yen
}

# Currency words/codes that may follow a number. Order matters: longer
# patterns first so "EUR/m2" wins over plain "EUR".
_CURRENCY_FOLLOWING = re.compile(
    r"\s*(EUR/m²|EUR/m2|US-Dollars?|EUR|USD|GBP|JPY|euros?|dollars?|pounds?)\b",
    re.IGNORECASE,
)

_SCALE_TO_MULT = {
    "K": 1_000,
    "M": 1_000_000,
    "B": 1_000_000_000,
    "T": 1_000_000_000_000,
}

# Word-form scale tokens that models often emit instead of the K/M/B/T letter
# suffix (e.g. "1.4 billion" rather than "1.4B"). Maps each word to the
# canonical letter so the rest of the pipeline (NumberRecord.scale field,
# _SCALE_TO_MULT lookup, classifier) stays unchanged. Covers English plus the
# two French quantifier nouns that disagree with English ("milliard" = billion,
# "mille" = thousand). Plurals handled in the regex.
_SCALE_WORD_TO_LETTER = {
    "thousand": "K",
    "million": "M",
    "billion": "B",
    "trillion": "T",
    "mille": "K",
    "milliard": "B",
}

# Number token. Captured groups:
#   prefix  - optional currency symbol immediately before the digits
#   digits  - digit string, may contain space/comma/period as separators
#   scale   - K/M/B/T letter OR word form (billion/million/thousand/trillion/milliard/mille)
#   percent - optional % suffix
# Word-form alternatives precede the letter class so the regex engine prefers
# the long match over consuming just the leading letter. The negative-letter
# lookahead rejects bare `B` in "billion" but accepts "billion" / "billions"
# (the char after those tokens is a non-letter). Plurals handled per-word.
# We match permissively here; _normalize_digits applies locale rules.
_NUMBER_RE = re.compile(
    r"(?P<prefix>[€$£¥])?\s?"
    r"(?P<digits>\d+(?:[  .,]\d+)*)"
    r"\s?(?:(?P<scale>billions?|millions?|thousands?|trillions?|milliards?|milles?|[KMBT])(?![A-Za-z]))?"
    r"(?P<percent>%)?",
    re.IGNORECASE,
)

# Cue words appearing before a number that mark it as an INSEE/postal/department code.
_INSEE_CUE = re.compile(
    r"\b(insee|code postal|d[eé]partement)\b",
    re.IGNORECASE,
)

# Cue phrases nearby a number that mark it as chart-axis metadata (axis tick,
# range endpoint, step size). These should not be matched against CSV cells
# since they describe the visualization's scale, not actual data values.
_AXIS_CUE = re.compile(
    r"(x[- ]?axis|y[- ]?axis|in steps of|step of|\branges?\b|axis labeled|"
    r"shows values|values from|\bticks?\b|labeled '|labeled \")",
    re.IGNORECASE,
)


def _normalize_digits(digits: str, locale: str) -> Optional[float]:
    """
    Convert a digit token to a plain float.

    locale ("fr" or "en") disambiguates tokens that have a single separator.
    Examples (fr): "14,6" -> 14.6, "105 000" -> 105000, "1 234,56" -> 1234.56
    Examples (en): "14.6" -> 14.6, "105,000" -> 105000, "1,234.56" -> 1234.56
    """
    s = digits.replace(" ", "").replace(" ", "")  # strip thousands spaces

    has_comma = "," in s
    has_period = "." in s

    if has_comma and has_period:
        # Mixed separators: the rightmost one is the decimal mark.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
        return float(s)

    if has_comma:
        return _resolve_single_separator(s, ",", locale)

    if has_period:
        return _resolve_single_separator(s, ".", locale)

    return float(s)


def _resolve_single_separator(s: str, sep: str, locale: str) -> float:
    """
    Disambiguate a digit string that contains exactly one kind of separator.

    Rules:
      - Multiple instances must be thousands (no one writes 1.234.567 as a decimal).
      - Single instance with exactly 3 trailing digits: thousands by default,
        unless the separator is the locale's decimal char (then decimal).
      - Single instance with non-3 trailing digits: must be decimal.
    """
    if s.count(sep) > 1:
        return float(s.replace(sep, ""))

    after = s.split(sep)[1]
    if len(after) == 3:
        if locale == "fr" and sep == ",":
            return float(s.replace(",", "."))
        if locale == "en" and sep == ".":
            return float(s)
        return float(s.replace(sep, ""))

    if sep == ",":
        return float(s.replace(",", "."))
    return float(s)


def _detect_currency(prefix: Optional[str], following_text: str) -> Optional[str]:
    """
    Determine the currency for a matched number, if any.

    Checks (in order):
      1. The prefix character captured before the digits.
      2. A currency symbol immediately after the digits.
      3. A currency word/code regex match after the digits.
    """
    if prefix and prefix in _CURRENCY_BY_SYMBOL:
        return _CURRENCY_BY_SYMBOL[prefix]

    stripped = following_text.lstrip()
    if stripped and stripped[0] in _CURRENCY_BY_SYMBOL:
        return _CURRENCY_BY_SYMBOL[stripped[0]]

    m = _CURRENCY_FOLLOWING.match(following_text)
    if m:
        word = m.group(1).lower()
        if word.startswith("eur"):
            return "EUR"
        if word.startswith("us-dollar") or word.startswith("dollar") or word == "usd":
            return "USD"
        if word.startswith("pound") or word == "gbp":
            return "GBP"
        if word == "jpy" or word == "yen":
            return "JPY"
    return None


def _classify_kind(digits: str, scale: Optional[str], is_percent: bool,
                   is_currency: bool, context_left: str) -> Kind:
    """
    Decide whether the number is a real data value, a year, an INSEE code,
    or chart-axis metadata.

    Axis classification fires when the surrounding prose contains chart-scale
    cues like "X-axis", "in steps of", "range", or "values from". Axis numbers
    are not data values to verify (they describe the chart's coordinate scale).
    """
    # Axis cues take precedence: a 100k that follows "Y-axis shows values from
    # 0 to 100k" is the chart's max tick, not a data point.
    if _AXIS_CUE.search(context_left):
        return "axis"

    if scale is not None or is_percent or is_currency:
        return "value"

    # Bare integer: no decimal/thousand separators present
    if digits.isdigit():
        n = int(digits)
        if len(digits) == 4 and 1900 <= n <= 2100:
            return "year"
        if len(digits) == 5 and _INSEE_CUE.search(context_left):
            return "code"

    return "value"


def _context_phrase(text: str, start: int, end: int, window: int = 40) -> str:
    """
    Capture a window of characters around the matched number, excluding the
    number itself. Whitespace is collapsed to single spaces.
    """
    left = text[max(0, start - window):start]
    right = text[end:end + window]
    phrase = (left + " " + right).strip()
    return re.sub(r"\s+", " ", phrase)


def extract(text: str, locale: str = "en") -> list[NumberRecord]:
    """
    Find every number-like token in `text` and return a list of NumberRecords.

    locale ("en" or "fr") disambiguates single-separator tokens with three
    trailing digits. See module docstring for the full rule table.
    """
    records: list[NumberRecord] = []

    for m in _NUMBER_RE.finditer(text):
        digits = m.group("digits")
        if not digits or not any(c.isdigit() for c in digits):
            continue

        # Reject digits glued to a preceding letter (e.g. "2" inside "m2",
        # "v2" in version strings). Currency-prefixed numbers ($40K) are
        # unaffected because the digit is preceded by the symbol, not a letter.
        digit_start = m.start("digits")
        if digit_start > 0 and text[digit_start - 1].isalpha():
            continue

        try:
            normalized = _normalize_digits(digits, locale)
        except ValueError:
            continue
        if normalized is None:
            continue

        prefix = m.group("prefix")
        scale_token = m.group("scale")
        if scale_token is None:
            scale = None
        else:
            # Letter form ("M") canonicalises to upper-case. Word form ("million",
            # "milliards") looks up the canonical letter, plurals stripped.
            normalized_token = scale_token.lower().rstrip("s")
            scale = _SCALE_WORD_TO_LETTER.get(normalized_token, scale_token.upper())
        is_percent = m.group("percent") == "%"

        # Compute raw bounds: include prefix and scale/percent suffix when present.
        raw_start = m.start("prefix") if prefix else m.start("digits")
        if is_percent:
            raw_end = m.end("percent")
        elif scale:
            raw_end = m.end("scale")
        else:
            raw_end = m.end("digits")
        raw = text[raw_start:raw_end]

        # Apply scale and percent to the canonical value.
        value = normalized
        if scale:
            value = value * _SCALE_TO_MULT[scale]
        if is_percent:
            value = value / 100.0

        currency = _detect_currency(prefix, text[raw_end:raw_end + 20])
        is_currency = currency is not None

        context_left = text[max(0, raw_start - 30):raw_start]
        kind = _classify_kind(digits, scale, is_percent, is_currency, context_left)

        records.append(NumberRecord(
            raw=raw,
            value=value,
            scale=scale,
            kind=kind,
            is_percent=is_percent,
            is_currency=is_currency,
            currency=currency,
            context_phrase=_context_phrase(text, raw_start, raw_end),
            char_start=raw_start,
            char_end=raw_end,
        ))

    return records
