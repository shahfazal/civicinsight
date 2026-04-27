# Exp 4 Reproducibility Run, Apr 21

Second run of `07-experiment-4.ipynb`, identical config to Apr 20. Purpose: confirm the Exp 4 scorecard is reproducible, not a flaky one-off. Canon findings live in [exp4-results.md](exp4-results.md), this note captures only the deltas.

**Notebook artifact:** `notebooks/kaggle/07-experiment-4-run-0421.ipynb` (with outputs preserved).

## Config

Identical to Apr 20: r=16, α=32, 5 epochs, LR 2e-4, batch 1×grad_accum 4, max_seq_length=2048, 4-bit, vision frozen, dataset.marked.json (50 examples).

## Training is deterministic ✓

Loss curve is **byte-identical** to the Apr 20 run:

- Step 1: 14.03
- Step 65: 0.28
- Min: 0.18 (step 63)

Same seed + same data + same config + same arithmetic → reproducible loss. Good reproducibility credibility. The `14 → 0.28` memorization signature holds.

## Inference is NOT deterministic

All three `model.generate()` calls in the notebook pass only `max_new_tokens`, no sampling params. Gemma's default `generation_config` has `do_sample=True`, so every run draws a different sample.

## Aggregate scorecard, robust

Pattern holds across both runs:

- **Marker appears: 0/5** (same as Apr 20)
- **Slot opener pattern: 0/5** (same as Apr 20)
- **Banned adjectives clean: ~3/5** (within noise of Apr 20's 4/5)

The headline findings are real, not a sampling artifact.

## Drift-mode delta, the interesting part

Individual failures are stochastic draws from a distribution of drifts. Different rolls surface different modes.

**New drift modes observed Apr 21 (absent Apr 20):**

- **"Helpful assistant wrapper"**, 3/5 outputs open with `An aria-label for this image is:` or `would be:`. The model describes *what it would emit* instead of emitting. Prompt-echo one level deeper.
- **HTML attribute syntax**, browser-share-other-filtered opens `aria-label="..."`. Echoed "aria-label" as if it were an HTML attribute.
- **Markdown formatting regression**, browser-share (full) wraps output in `**bold**`. Googly-prose artifact leaking back.

**Apr 20 drifts that did NOT recur Apr 21:**

- Scatter mode-collapse loop (Samoa/Tonga cascade), did not appear. Model listed 5 labeled points (Qatar, Ireland, Brunei, Maldives, Spain) and stopped cleanly.
- USA "1" sum-to-100 hallucination on rural-vs-urban, did not appear. Different positional-schema drift this run (Germany got 3 numbers instead of 2).

**Drifts that repeated both runs:**

- Bretagne generated in French (gold is English), cross-lingual drift robust.
- `around X%` banned adjective on browser-share (full).
- Reykjavík diacritic dropped.
- "Bar chart" misclassification instead of "stacked bar chart".
- Scatter axis labels swapped (X=life-exp, Y=GDP).

## Methodological implication

Any future config-comparison experiment must:

1. **`do_sample=False`** on all inference calls, otherwise run-to-run variance swamps config-to-config signal.
2. **Held-out set larger than 5**, 15-20 images minimum, stratified by chart type.
3. **Optional but useful:** multiple sampling seeds alongside the greedy reference, to estimate the drift-mode distribution per config.

## The single sentence for the prof

> "Loss curve reproduces exactly; aggregate scorecard reproduces within noise; individual drift modes are stochastic. The failures are a *distribution* the model samples from, not a fixed set. So config comparisons need greedy decoding and a larger held-out to see signal above that distribution."
