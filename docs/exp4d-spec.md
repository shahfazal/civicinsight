# exp4d (DPO v2): post-v1 backlog, ranked against Kaggle deliverables

**Status:** Draft. Written while exp4c v1 (DPO) trains.

**This spec is conditional.** v2 happens only if v1's post-DPO scorecard shows residual gaps that move the submission's evaluation score AND there's runway to ship it before May 15. Read decision gate before committing work.

---

## Why this spec exists at the right priority

The competition reference allocates time roughly 55% / 20% / 5% / 10% / 10% across dataset+training, video, demo, writeup, submission buffer. v1 DPO is the tail end of the 55% bucket. If v1 produces a working adapter, **v2 DPO is not the next thing to build**, the video, the Gradio demo, and the Grounder are.

Evaluation is 40 Impact + 30 Storytelling + 30 Technical = 70% video-driven, 30% verification of the tech. v2 DPO improves the 30% bucket marginally. The video improves the 70% bucket directly.

So this spec exists to:
1. Capture the v1 audit findings as a queryable backlog while they're fresh
2. Provide an explicit decision gate for when v2 is worth running
3. Pre-design v2 so that IF runway exists after video + demo + writeup are done, v2 can ship quickly

It does NOT exist as the next thing to build after v1 trains.

---

## Decision gate: when to run v2

**Only run v2 if ALL of these are true:**

1. v1 post-DPO scorecard shows specific failure modes from the audit are NOT fixed
2. Video script is drafted (Beat 1, 2, 3 from the agentic spec)
3. Gradio demo is functional on HF Spaces with image-only path AND CSV-grounded path
4. Writeup outline is complete (six sections from the agentic spec)
5. Calendar shows ≥4 days before May 15 personal deadline

**If any of these is false, v2 does not happen.** The gain from v2 DPO is incremental scorecard delta on edge cases. The loss from skipping video polish or shipping a broken demo is the entire submission.

**If v2 happens, scope is ruthlessly limited.** One tier, not six. The tier that matters most for the video demo's "wow" moment.

---

## v1 audit summary (5 held-outs, pre-DPO)

| Image | Headline failure |
|---|---|
| `baseline-1.png` (choropleth) | Hallucinated commune name (Plœrières, Ajaccio); invented step size ("steps of 1000"); contradicted own legend description in adjacent sentences; invented "centered on" claim |
| `browser-share-other-filtered.png` (line, "Other" selected) | Subtitle range substituted for x-axis tick range; invented categorical state (Safari "light blue" while others "faded") |
| `browser-share.png` (line, none selected) | False selection claim ("Chrome is selected" when nothing is) |
| `income-vs-life-exp.png` (scatter, labels only) | Claimed "untitled" when title is bold and prominent; invented step size ("steps of 25k" instead of 50k); fabricated entire tooltip with externally-sourced GDP value (~$105k for Ireland) when no tooltip exists in image; tooltip-consistency contradiction within output |
| `rural-vs-urban.png` (stacked bar, headline target) | Positional binding error, model reads printed values left-to-right and binds them to legend labels left-to-right, fails when leftmost segment has no printed value because it's too small. Top 4 rows (China, USA, Australia, India) all show this. Also: color-segment mapping confusion. |

## v2 target failure modes (ordered by submission impact, NOT frequency)

The previous version of this spec ordered tiers by frequency across audits. That was wrong framing. The right ordering is **how much each failure mode threatens the video demo and the Digital Equity track narrative.**

### Tier A: fabricated tooltip with externally-sourced facts

**Source:** `income-vs-life-exp.png` audit. Model invented a tooltip with $105k Ireland GDP value sourced from world knowledge, not the chart.

**Why this is Tier A despite being 1/5 frequency:**
- The Digital Equity submission is built on "blind users can verify civic data without sighted help." Fabricated tooltips with externally-correct values are catastrophic for that promise, a blind user has no way to detect the fabrication.
- This is the failure mode the Grounder (per agentic spec) is designed to catch at inference time. v2 DPO would be the upstream complement to the downstream Grounder defense.
- If the video's Beat 2 demonstrates the Grounder catching a fabrication and correcting it, v2 DPO reduces how often the Grounder needs to fire, making the submission look more polished, not just defensively correct.

**Proposed perturbations:**
- `fabricate_tooltip`, for "label only" golds, rejected version adds a fabricated tooltip with key-value pairs containing externally-correct values
- `fabricate_value`, for "no tooltip visible" golds, rejected version adds specific numeric values for unlabeled points

**Note:** Synthetic perturbation may be too easy here. The model has to suppress a strong pre-training prior (it knows real GDP values). May need 5-10 hand-written pairs from actual exp4c-v1 fabrications. Budget: 5 hours of careful labor.

### Tier B: positional binding on stacked bars (rural-vs-urban)

**Source:** `rural-vs-urban.png` audit. Model maps printed numbers to legend labels left-to-right, fails on rows where leftmost segment is too small to print a value (China, USA, Australia, India).

**Why Tier B:**
- This IS what v1's `positional_schema_swap` was over-sampled to fix. The post-v1 scorecard tells us if v1 worked.
- If v1 fixed it: v2 doesn't need this perturbation at all.
- If v1 didn't fix it: this is the headline failure mode for civic data accessibility (every civic dashboard has stacked bars), so v2 must include a more targeted perturbation.

**Refined perturbation if needed:**
- `omit_unlabeled_segment`, more targeted than generic `positional_schema_swap`. Take a gold with N segments where segment 1 is unlabeled (small share, no printed value) and segments 2..N are labeled. Rejected version drops the unlabeled segment from the description and shifts segment 2's value into the segment-1 slot in the legend mapping.

### Tier C: confident invention of axis/structure metadata

**Source:** 3/5 held-outs (`baseline-1`, `income-vs-life-exp`, `rural-vs-urban`). Model invents axis structure facts ("steps of N", "equal width", "centered on X") that contradict its own transcribed values.

**Why Tier C (high frequency, lower priority than A/B):**
- Detectable by Validator structure check at inference time (per agentic spec). A confident invention that contradicts transcribed values fails the validator, gets flagged as low confidence, user sees the warning.
- This is exactly the case the agentic layer was designed for. The spec frames the Validator as catching these even if the model produces them.
- v2 DPO would reduce the rate, but the Validator already provides a defense. Lower priority than Tier A (where Validator alone can't catch externally-sourced facts).

**Proposed perturbations (only if A and B are addressed):**
- `invent_step_size`, replace correct numeric step description with a "round" wrong one
- `invent_centering`, add a fabricated "centered on X" claim that wasn't in the gold
- `invent_axis_equality`, add fabricated "equal width" claims when the gold doesn't have them

### Tiers D+ (deferred to post-Kaggle)

The remaining failure modes, subtitle/axis substitution, false selection, color contradiction, are real but lower priority for the submission window:

- Subtitle/axis substitution: 1/5 frequency, single image
- False selection: 1/5 frequency, edge case (none-selected charts are uncommon in civic data)
- Color contradiction: detectable mechanically by the scorecard; doesn't need DPO

These go into `docs/post-kaggle-backlog.md`, not v2.

---

## Tightened scorecard for honest v1 evaluation

This is the **one thing** that should happen tomorrow regardless of v2 fate, because the existing scorecard has blind spots that will make the v1 post-DPO numbers look better than they are. Wrong numbers in the writeup damage the submission more than missing perturbations damage v2.

### Existing scorecard regex misses

The current consistency check:
```python
CONSISTENCY_CONTRADICTIONS = [
    (r"tooltip\s+is\s+visible", r"no\s+tooltip\s+is\s+visible"),
]
```
This regex did not catch the `income-vs-life-exp` failure ("with the tooltip" + "no tooltips visible"). Tighten to:
```python
CONSISTENCY_CONTRADICTIONS = [
    (r"with the tooltip", r"no tooltips? visible"),
    (r"tooltips? (?:is|are)?\s*visible", r"no tooltips? (?:is|are)?\s*visible"),
]
```

### Add: confident-invention detector

Catches Tier C failures mechanically:
```python
INVENTED_STEP_PATTERNS = [
    r"steps of 1[ ,]000",      # round-thousand step claim
    r"in steps of \d+0+",      # any "steps of round number"
    r"equal width",            # fabricated axis equality
    r"centered on \w+",        # fabricated centering
]
```
Flag if any pattern matches. Manual review needed to confirm vs. legitimate use, but cheap to add.

### Add: color-segment mapping checker

Catches `rural-vs-urban` color contradiction:
```python
def detect_color_contradiction(output):
    pairs = extract_color_element_pairs(output)
    elements_with_multiple_colors = [
        e for e, colors in group_by_element(pairs).items()
        if len(set(colors)) > 1
    ]
    return elements_with_multiple_colors
```

### Add: per-image metadata file

Required for Tier 2/3/4 detection. Without per-image truth, the scorecard can't know "the image has no tooltip" so can't flag fabrication. Draft format:

```json
{
  "rural-vs-urban.png": {
    "title": "Rural and urban population",
    "selection_state": "none_selected",
    "tooltip_visible": false,
    "expected_positional_traps": [
      {"label": "China", "wrong_capital_value": "53"},
      {"label": "USA", "wrong_capital_value": "80"},
      {"label": "Australia", "wrong_capital_value": "88"},
      {"label": "India", "wrong_capital_value": "30"}
    ]
  },
  "income-vs-life-exp.png": {
    "title": "Income vs life expectancy",
    "tooltip_visible": false,
    "labeled_dots": ["Qatar", "Ireland", "Brunei", "Spain", "Maldives"],
    "y_axis_steps": "50k"
  }
}
```

~30 min to write metadata for 5 held-outs. Pays for itself the first time the scorecard runs.

**Total scorecard tightening effort: ~1 day. This happens before any v2 work.**

---

## v2 implementation order (only if decision gate passes)

If v2 happens, ruthlessly scoped:

1. **Re-score v1 post-DPO with tightened scorecard** (~30 min). Identifies which tiers v1 actually fixed.
2. **Pick ONE tier to address in v2** based on submission impact (default: Tier A, fabricated tooltip).
3. **Build perturbation library for that tier only** (~half day).
4. **Optional: 5-10 hand-written hard negative pairs** if Tier A and the synthetic perturbation looks too easy (~5 hours).
5. **Train v2 DPO** (~3 hours on Modal).
6. **Score v2 vs v1** with same scorecard. Document delta.
7. **Decide: ship v2 or v1?** Based on which produces better demo output on the 5 held-outs.

Total v2 effort: ~2 days minimum, ~3 days if hand-writing hard negatives. **No v2 happens with less than 4 days of runway before May 15.**

---

## What v2 doesn't change (anti-patterns from )

Same constraints as v1. Don't relitigate these:
- No `Gemma4ClippableLinear` patch (Unsloth handles it)
- No `UNSLOTH_COMPILE_DISABLE` (not needed)
- No `model.load_adapter()` for DPO (use the `get_peft_model` + `set_peft_model_state_dict` pattern from exp4c)
- No `transformers`/`unsloth` version pins outside what `requirements-exp4c-WORKING.txt` resolved to

---

## Relationship to agentic spec

This v2 spec is upstream of the Validator + Grounder layer. They solve overlapping problems with different mechanisms:

| Failure mode | DPO v2 fix | Validator catch | Grounder catch |
|---|---|---|---|
| Fabricated tooltip (Tier A) | Reduces rate | No (looks structurally valid) | Yes if CSV provided |
| Positional binding (Tier B) | Reduces rate | No (numbers are present) | Partial (CSV verifies values, not bindings) |
| Confident invention (Tier C) | Reduces rate | Partial (some patterns regex-detectable) | Yes if CSV provided |

**Defense in depth.** v2 DPO + Validator + Grounder all reduce rate of bad output reaching the user. The Grounder is the strongest single defense IF the user provides CSV. v2 DPO is the only defense for the image-only path.

**This matters for the writeup section 3 (Agentic Retrieval, 300 words).** The story is "we improved the model AND added a verification layer for when the user has source data." Two-layer defense is more credible than either alone, and explicitly maps to the hackathon's "post-training, domain adaptation, AND agentic retrieval" framing.

---

## Open questions

- Does v1's `positional_schema_swap` fix `rural-vs-urban`? (answer comes from v1 scorecard)
- If v1 fixes nothing on Tier A (fabricated tooltip), is the Grounder alone sufficient defense for the submission? (probably yes; Grounder is the demo's "wow" moment regardless)
- Should the post-v1 scorecard also score the **agentic layer's behavior**, e.g., did the Validator correctly flag low-confidence cases? Yes, but separate metric, separate scorecard sheet.

---

## Notes for the writeup (drag forward into Section 3)

When writing the 1,500-word writeup, Section 3 (Agentic Retrieval, 300 words) should reference v1 vs v2 honestly:

- If v1 ships: "Fine-tuning closed X failure modes. The agentic layer adds verification for the remaining cases."
- If v2 ships: "Two rounds of post-training closed X failure modes; the agentic layer adds verification for the remaining cases."

Either is true. v2 only matters for the writeup if the scorecard delta is large enough to be worth a sentence. If v2 produces a 5% improvement, don't mention it, say "fine-tuning" without versioning.

---

## What I'd actually do tonight while v1 trains

Drop the v2 spec into the backlog. Don't think about it again until v1 finishes. Use the training time for:

1. Drafting the video script (Beat 1, 2, 3 from agentic spec)
2. Setting up the HuggingFace Space for the Gradio demo
3. Sketching the Validator's `check()` function from the agentic spec, this is the easy half of the agentic layer and unblocks Beat 2 of the video

If v1 finishes during your sleep cycle, the post-DPO scorecard tells you what to do tomorrow. Either way, the next 24-48 hours are video + demo + writeup work, not v2 DPO.
