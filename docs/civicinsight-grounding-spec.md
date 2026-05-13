# CivicInsight: Grounding Architecture

This spec describes the deterministic grounding layer that pairs with the fine-tuned Gemma 4 E4B model in CivicInsight. The model produces an ARIA description from a chart image; this layer cross-references the description's numeric claims against an optional source CSV, flagging unverified or fabricated values before the output reaches the user. The design uses a single inference pass plus deterministic post-processing rather than self-healing retry loops, so a blind user does not wait minutes on round-trips.

---

## Architecture overview

```
User Input                          Output
-----------                         ------
[Dashboard Screenshot] (required)   [ARIA Description]
[Source CSV]           (optional)   [Verification Report]
                                    [Confidence Indicators]

                 +-------------------+
                 |      ROUTER       |
                 | (selects pipeline)|
                 +--------+----------+
                          |
              +-----------+-----------+
              |                       |
     [Image Only Path]      [Image + CSV Path]
              |                       |
              v                       v
     +--------+--------+    +--------+--------+
     |  1. EXTRACT     |    |  1. EXTRACT     |
     |  Fine-tuned E4B |    |  Fine-tuned E4B |
     |  Single pass    |    |  Single pass    |
     +--------+--------+    +--------+--------+
              |                      |
              v                      v
     +--------+--------+    +--------+--------+
     |  2. VALIDATE    |    |  2. VALIDATE    |
     |  Structure check|    |  Structure check|
     |  (rule-based)   |    |  (rule-based)   |
     +--------+--------+    +--------+--------+
              |                      |
              v                      v
     +--------+--------+    +--------+--------+
     |  3. FORMAT      |    |  3. GROUND      |
     |  ARIA output +  |    |  Cross-ref CSV  |
     |  unverified flag|    |  Flag values    |
     +-----------------+    +--------+--------+
                                     |
                                     v
                            +--------+--------+
                            |  4. FORMAT      |
                            |  ARIA output +  |
                            |  verification   |
                            +-----------------+
```

The router does not invoke an LLM. It is a Python conditional that checks for CSV presence and selects which downstream pipeline runs. The downstream pipelines are themselves rule-based: regex extraction, schema validation, and deterministic CSV cross-reference. No tool-using agent loop, no model-in-the-loop planning.

---

## Stages

**1. EXTRACT.** The fine-tuned Gemma 4 E4B model is called once with the dashboard screenshot and the prompt `"Generate an aria-label for this data visualization image."` The output is a single ARIA description string that should begin with the `[civicinsight-v1]` marker as its first token.

**2. VALIDATE.** A rule-based structural validator runs on every output. It checks for the marker, at least one numeric token, a chart-type word, and minimum length. Outputs missing the marker short-circuit to `structural-issue` and skip grounding entirely; the model's output is preserved verbatim for the user but flagged as unverified.

**3a. FORMAT (image-only path).** If no CSV is supplied, the formatter assembles the ARIA description with `data_status="unverified"` and returns. The user gets the model's description with an explicit signal that nothing has been cross-checked.

**3b. GROUND (image + CSV path).** When a CSV is supplied, a regex-based extractor pulls numeric tokens from the description and classifies each one as value, year, postal/INSEE code, or axis tick. Years, codes, and axis numbers are filtered out. Remaining `value` records are matched against a CSV index with adaptive tolerance: 5% for K/M/B/T-scaled values (to absorb display rounding), 0.5% for raw numbers. When multiple CSV rows could match a value, the matcher disambiguates by context-token overlap with row headers. A numeric coincidence with an unrelated row is flagged as likely fabrication, not confirmed.

**4. FORMAT (image + CSV path).** The formatter assembles the ARIA description plus a per-value verification annotation. `data_status` resolves to one of:

- `verified`: every eligible value matched.
- `partial`: some matched, some didn't.
- `unverified`: no CSV provided, no eligible values, or none matched.
- `structural-issue`: the output failed validation.

---

## Where the code lives

| Stage | Module |
|---|---|
| Router | [`app/agent.py`](../app/agent.py) (`run()` function) |
| 1. EXTRACT | [`app/io/inference.py`](../app/io/inference.py) (Modal-deployed Gemma 4 E4B) |
| 2. VALIDATE | [`app/core/validator.py`](../app/core/validator.py) |
| 3a. FORMAT (image only) | [`app/core/format.py`](../app/core/format.py) |
| 3b. GROUND | [`app/grounding/source.py`](../app/grounding/source.py) (CSV ingestion) + [`app/grounding/match.py`](../app/grounding/match.py) (value cross-reference) |
| Numeric extraction | [`app/core/extract.py`](../app/core/extract.py) |
| 4. FORMAT (image + CSV) | [`app/core/format.py`](../app/core/format.py) |
| Web demo | [`app/io/web.py`](../app/io/web.py) + [`app/io/demo.py`](../app/io/demo.py) |

Tests for each module live in [`tests/`](../tests/) and exercise the router end-to-end with a stubbed inference function so they do not require GPU or Modal access.
