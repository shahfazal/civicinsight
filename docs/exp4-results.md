# Exp 4 Results — Apr 20 late session

**Config:** r=16, α=32, 5 epochs, LR 2e-4, batch 1×grad_accum 4, max_seq_length=2048, vision layers frozen, dataset.marked.json (50 examples, all unicode round-trip verified in 06).

**Training:** Loss 14.03 (step 1) → 0.28 (step 65). Min 0.18 at step 63. Classic memorization convergence. Adapter saturated; rank was binding constraint.

## What imprinted ✓

- **Style:** No more Googly prose. Output is flat, structured, tooltip-like. Clear diff vs baseline gen ("This is a box plot comparing... **1. Extrême gauche:** The distribution is relatively narrow...").
- **Slot pattern (partial):** Model emits `[chart type] titled "..."` consistently. Absorbed chart-type naming, titled-vs-untitled concept (weakly), axis-listing convention.
- **Cross-lingual transfer:** Bretagne (French image) got French aria_label in native idiom ("Carte choroplèthe..."). Template concept generalized across languages — **unexpected win**.
- **Banned adjectives:** Clean on training image (box plot). Confirms training-data edit pass worked at least for in-distribution chart types.

## What FAILED ❌

### 1. Marker missing on all 5 held-outs + training image

- Output starts with `aria-label:` (echoing user prompt) instead of `[civicinsight-v1]`
- **Root cause:** 8-token marker competing against 3-token prompt echo. Prompt echo wins every time.
- **Fix for Exp 5:** Register `[civicinsight-v1]` as special token via `tokenizer.add_tokens([...], special_tokens=True)` + `model.resize_token_embeddings(len(tokenizer))`. Becomes 1 token, vocab grows 262144→262145, wins prompt-echo competition.

### 2. Slot opener drift: "A" instead of "This"

- All 5 held-outs say `A line chart titled` / `A scatter plot titled` etc. Training says `This`.
- Systemic. Possibly entangled with marker failure — if model can't commit `[civicinsight-v1]` + `This`, it skips both.
- Fixing marker likely fixes this.

### 3. Banned adjectives regression on OOD (browser full line chart)

- "around X%" × 5, "generally trends upward/downward" × 6
- Model learned "no hedging" for box plots (in-distribution) but **didn't generalize as a rule**
- Training data edit pass may need a broader sweep, OR this is just frozen-vision confidence leaking out

### 4. Vision encoder limits (can't fix without unfreezing)

- `€` → `C` on boxplot
- Colors hallucinated on Bretagne choropleth (dark yellow vs actual maroon)
- Outlier city labels skipped on boxplot
- Filter state missed completely on browser-share-other-filtered
- Cross-line confusion on browser-share (IE's 2009 high attributed to Chrome)
- **Fix for Exp 5:** `finetune_vision_layers=True`. Accept slower training + catastrophic-forgetting risk.

### 5. Text-prior-over-vision hallucinations

- Boxplot: invented q1/q3 values for boxes without tooltips
- Browser-share: inserted "Opera" which isn't on the chart
- **Scatter (income-vs-life-exp): CATASTROPHIC mode collapse** — model listed correct 5 labeled points (Qatar/Ireland/Spain/Maldives/Brunei) then hallucinated 15+ Pacific/Caribbean island nations from Gemma's pretraining prior (Dominica/Samoa/Tonga/Fiji/Seychelles/Barbados...), then entered degenerate loop: "Samoa near 10k... Tonga near 10k... Samoa near 10k..." until max_new_tokens hit.
- **Fixes for Exp 5:** (a) `repetition_penalty=1.2` or `no_repeat_ngram_size=4` at inference time; (b) unfrozen vision should reduce vacuum for text-head to fill.

## Held-out run summary (all 5 complete)

**Config:** r=16, α=32, 5 epochs, LR 2e-4, batch 1×ga4, max_seq=2048, vision frozen, 50 examples, loss 14.03 → 0.28 over 65 steps.

**Data hygiene:** training set audit confirms 50/50 records start `[civicinsight-v1] This` — signal is clean, drift is not hedging against label noise.

| Image                            | Marker | Slot                                 | Banned adj                              | Data fidelity                                                                                                                                                                                                     |
| -------------------------------- | ------ | ------------------------------------ | --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Box plot (training idx 5)        | ❌     | ⚠️ "Box plot titled"                 | ✓                                       | ❌ hallucinated tooltips, €→C                                                                                                                                                                                     |
| baseline-1 (Bretagne choropleth) | ❌     | ⚠️ "Carte choroplèthe" (French!)     | ✓                                       | ⚠️ colors wrong, bins mostly right                                                                                                                                                                                |
| browser-share-other-filtered     | ❌     | ⚠️ "A line chart titled"             | ✓                                       | ❌ Opera hallucinated, filter state missed                                                                                                                                                                        |
| browser-share (full)             | ❌     | ⚠️ "A line chart titled"             | ❌❌ "around" ×5, "generally trends" ×6 | ❌ Chrome/IE swapped, end values all "~5%"                                                                                                                                                                        |
| income-vs-life-exp (scatter)     | ❌     | ⚠️ "A scatter plot titled"           | ✓                                       | ❌❌ repetition loop + 15 hallucinated countries                                                                                                                                                                  |
| rural-vs-urban (stacked)         | ❌     | ⚠️ "Bar chart showing" (no article!) | ✓                                       | ❌ top-4 positional shift (missing dark segment → [cap,urb,rur] slides to [urb,rur,0]); USA "1" hallucinated (sum-to-100 text prior); Reykjavík diacritic dropped; misidentified as "Bar chart" not "stacked bar" |

**Automated scorecard — marker / slot-opener / banned-adjectives (cell 11):**

- marker appears: **0%** (0/5)
- opens with slot pattern: **0%** (0/5)
- no banned adjectives: **80%** (4/5 — browser-share full is the regressor)

**Three distinct slot-opener drift patterns across 5 held-outs:**

1. `A [type] titled` — 3 cases (browser×2, scatter) — English default prior
2. `[Type] titled` (no article) — 1 case (box plot, training image)
3. `Bar chart showing` (no article, different verb) — 1 case (rural-urban)
4. `Carte choroplèthe` — 1 case (Bretagne, French transfer)

Confirms model is improvising slot because it cannot commit the 8-token `[civicinsight-v1]` prefix. No hedging-for-inconsistency — dataset audit (Apr 20 S8) confirmed 50/50 records start `[civicinsight-v1] This` cleanly. Drift is pure "skip marker → fall back to pretraining prior" chain.

**Best output:** Bretagne (cross-lingual transfer, structure coherent, bins mostly correct)
**Worst output:** income-vs-life-exp (mode collapse + pretraining-bleed hallucination)

**New failure class (stacked bar specific):** positional-schema filling. Frozen vision can't detect absent segments, so 3 visible numbers always fill [slot1, slot2, slot3] regardless of which segments actually exist. Unfreezing vision should fix.

**Most viscerally diagnostic artifact (for show-and-tell):** scatter mode-collapse loop —

> "...Samoa near 10k per capita and 75 years life expectancy... Tonga near 10k per capita and 75 years life expectancy... Samoa near 10k per capita and 75 years life expectancy..." (until max_new_tokens)

Textbook degenerate decoding — model in a fixed-point attractor. Single clearest "one look and you see the failure" example in the run.

## Exp 5 design (as proposed Apr 20) — priority-ordered knobs

1. **Register `[civicinsight-v1]` as special token** — 1-token fix, high confidence it'll resolve marker + likely slot drift (`This`)
2. **Unfreeze vision layers** (`finetune_vision_layers=True`) — single biggest lever for data fidelity. Will slow training ~2-3x on T4.
3. **Inference-time:** `repetition_penalty=1.2`, `no_repeat_ngram_size=4` — break the scatter loop class of failure
4. **Keep r=16, same dataset** — rank isn't the problem; dataset is already edit-passed and clean
5. **Optional:** Broader banned-adjective sweep in edit pass if (1) + (2) don't clean them up

## What NOT to touch

- Dataset size (50 is fine — memorization working)
- LoRA rank (16 is adequate — loss hit 0.28, not rank-bound)
- Epochs (5 is correct — more won't help with frozen vision)
- Marker string itself (keep `[civicinsight-v1]`, just tokenize differently)

## Blog narrative material

- "Template imprinted, marker didn't" → easy-to-explain diagnostic
- Scatter mode collapse → textbook VLM failure in the wild
- Cross-lingual French generation → unexpected emergent behavior
- Exp 4 → Exp 5 progression = "what one frozen config couldn't do, you need architectural knobs for"

---

## Update — Apr 21: Exp 5 plumbing pivot

The Exp 5 design above was the plan going in. Reality: the special-token fix (#1 above) turned out to be a multi-commit rabbit hole in the Unsloth + Gemma4 + 4-bit multimodal stack.

**Attempts (4 Kaggle commits):**

- **5a v1:** crashed on `Gemma4Processor has no len()` — processor vs tokenizer distinction.
- **5a v2:** OOM on vision unfreeze (T4 16GB can't hold hundreds of millions of extra trainable params). Vision unfreeze banked.
- **5a v3 (frozen):** `resize_token_embeddings` hit `_init_added_embeddings_weights_with_mean` — fp32 materialization of full 262144×2560 embedding (2.5 GB alloc failed).
- **5a v4 (`mean_resizing=False`):** cell 5 clean (embed_tokens 262145 ✓, lm_head 262145 ✓). Training crashed step 1 with `vectorized_gather_kernel: index out of bounds`. Traceback lands in vision tower but that's a CUDA async artifact.
- **5b (dequantize-before-resize):** dequantize was a no-op (embedding was already fp16). Same training crash.
- **5c (`tie_weights()` + shape assert):** assert passed — both embed_tokens and lm_head were 262145 before AND after tie_weights. Hypothesis falsified. Training still OOB'd at step 1 with same vision-tower traceback.

**Diagnosis:** the stack has many places where vocab size is baked in (compiled kernel cache, 4-bit quantization metadata, image-token indexing, model/generation config fields, internal buffers). `resize_token_embeddings` reached embed_tokens + lm_head, not the rest. Identifying the exact OOB kernel would require `CUDA_LAUNCH_BLOCKING=1` + 2-4 hours of forensic work through Unsloth patches, on a 4-day deadline.

**Pivot officially reached (Apr 21):** vocab expansion is a dead end in this stack. Abandon the special-token plan. The marker is not the core challenge — it's the most visible of three entangled Exp 4 failures. Real problems to address next:

- **Vision collapse** — frozen vision reading charts poorly, poisoning the text layer.
- **Prior dominance over training signal** — 50 examples at r=16, 5 epochs, frozen vision = under-learning. Model learned style/format (flat prose, no Googly interpretation) but didn't absorb the marker/slot discipline strongly enough to resist prompt echo.
- **Banned-phrase leakage on OOD** — edit-pass taught the rule in-distribution only.

**Evidence still intact from Exp 4:** baseline (Googly prose with `**bold**` and `## headers`) vs post-train (flat structured sentences, no markdown furniture, cross-lingual French transfer) is a visible learning signal. Even with marker=0%, training moved the model.

**Next-experiment candidates (for prof discussion):**

- Scale the signal: more epochs, higher LoRA rank, partial vision unfreeze (last N layers only — avoid full-unfreeze T4 OOM).
- Marker as cosmetic post-hoc: inject via chat template at inference, stop fighting the model to emit it. Free up experiment budget for vision + leakage.
- Dataset scale: augment 50 → 250 if under-learning is the root cause (original plan had this as an overfitting-response; here the problem is inverse).
- Surrogate atomic marker: pre-existing single token in Gemma's vocab that doesn't collide with civic content — zero plumbing.
