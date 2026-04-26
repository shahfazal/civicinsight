# Exp 4b Results — Apr 23

**Variable under test:** vision layer unfreeze (the one architectural change Exp 5 V2 couldn't run on Kaggle T4 due to OOM).

**Config:** identical to Exp 4 — r=16, α=32, 5 epochs, LR 2e-4, batch 1×grad_accum 4, max_seq_length=2048, 4-bit, same `dataset.marked.json` (50 examples). **Changed:** `finetune_vision_layers=True`, `target_modules="all-linear"`.

**Hardware:** Modal A100 80GB (commercial pivot from Kaggle T4). Unsloth 2026.4.7, Transformers 5.6.1.

## Training

- 65 steps, 435s, ~$0.30 of A100 compute
- Loss curve: 3.32 (step 1) → 0.20 (step 42) over the run
- Absolute loss not comparable to Exp 4's `14.03 → 0.28` — different Unsloth/Transformers versions appear to mask loss differently (Exp 4's step-1 loss of 14 ≈ `ln(262144)`, suggesting the older run included tokens that shouldn't have been in the loss denominator). Trajectory is what matters; both descended cleanly.
- Trainable params: 34.9M language + 4.5M vision = **39.4M total (0.49%)**. Confirms vision LoRA attached — verified via per-submodule parameter breakdown.

## Scorecard delta vs Exp 4

| Metric | Exp 4 (frozen) | Exp 4b (unfrozen) |
|---|---|---|
| Marker `[civicinsight-v1]` | 0/5 | **5/5** ✅ |
| Opens with slot pattern | 0/5 | **5/5** ✅ |
| No banned adjectives | 4/5 | **5/5** ✅ |

Three separate failure classes from Apr 20 went from 0/5 or partial → 5/5 on the same held-out set, same 50 training examples. The only architectural change is vision layer unfreeze.

## What imprinted (beyond the scorecard)

- **Style:** no more `**bold**` headers, `## headings`, or bullet-point lists. Flat structured prose.
- **Cross-lingual transfer preserved:** French axis labels (`Prix médian au m²`) emitted correctly in French body.
- **Vision glyph fidelity ✓:** `€` reads correctly where Exp 4 read `C`. This is the single cleanest signal that vision unfreeze *actually trained* (bug #5039 zero-gradients hypothesis NOT biting us).
- **Chart-type classification ✓:** stacked bar correctly identified as "stacked bar chart" (Exp 4 called it "Bar chart").
- **Filter state ✓:** browser-share-other-filtered output captured "series 'Other' is selected with a tooltip showing 9% in October 2020" and identified other faded series by name. Exp 4 missed filter state entirely.
- **Scatter mode-collapse ✓:** no Samoa/Tonga cascade, no 15-country pretraining prior bleed. Listed real countries (Qatar, Ireland, Brunei, Spain, Maldives) with plausible coordinates.
- **No Chrome/IE swap, no Opera hallucination, Reykjavík diacritic preserved.**

## What's still broken (honest scorecard)

### Positional-schema filling — prediction falsified

The Apr 20 results doc predicted: *"Frozen vision can't detect absent segments, so 3 visible numbers always fill [slot1, slot2, slot3] regardless of which segments actually exist. **Unfreezing vision should fix.**"*

**It didn't.** The rural-vs-urban output still attributes values positionally by legend order:

> "China (Beijing) - 53%, USA (Washington, D.C.) - 80%, Australia (Canberra) - 88%..."

USA's 80 is on the "other urban" segment, not the "capital" segment. The model reads the numbers correctly but binds them to legend categories left-to-right instead of by the color-of-segment-the-number-sits-on.

**Reclassification:** This is not a vision-acquisition failure. It's a spatial-binding / preference failure. The vision tower *can* see the numbers; the reasoning chain "which color segment carries this number → which legend category has this color" requires an explicit preference signal. **DPO target.**

### Small-text OCR errors (vision-fidelity residual)

- `Plœrenq` for `Plœmeur`
- `Comomice-Mont-Blanc` for `Chamonix-Mont-Blanc`
- `Reven` for `Revin`
- `Abon` for `Abscon`
- `Sieur-Fourns-les-Plages` for `Six-Fours-les-Plages`

Model is *trying to read every label* (vs inventing them in Exp 4) — these are OCR edge cases on 1024×1024 renders. More diverse training data should improve this; architectural change has already given us what it can.

### Internal consistency drift

`income-vs-life-exp` output contains a contradiction within the same response:
- "A country tooltip is visible, showing Qatar at (78, 90k)..."
- "No country is selected, and no tooltip is visible."

Classic preference failure — two plausible-sounding statements with no internal coherence check. DPO territory.

### Geographic overreach

`baseline-1` (Bretagne choropleth) described as "arrondissements of France" instead of "communes of Brittany." Broader geographic prior wins over specific regional context. Fixable with either more Bretagne-specific training examples or DPO preference signal.

### Truncation on dense outputs

`rural-vs-urban` hit `max_new_tokens=600` mid-sentence. Easy config fix (bump to 800-1000) for dense stacked-bar charts.

## Held-out output detail

### baseline-1.png (Bretagne choropleth) — 19.3s
> [civicinsight-v1] This choropleth map shows real estate prices per square metre in arrondissements of France. The color scale ranges from 0 - 1076 euros per square metre (light pink) to 2989 - 6571 euros per square metre (dark red). The tooltip for the Plœrenq Arrondissement shows a price of 2643 EUR/m2, which is mapped in dark blue.

### browser-share-other-filtered.png — 23.1s
> [civicinsight-v1] This line chart titled 'The rise of Google Chrome' shows web browser market share from January 2009 to October 2023. The X-axis shows years from 2009 to 2023. The Y-axis shows market share from 0 to 60% in steps of 10. The series 'Other' is selected with a tooltip showing 9% in October 2020. The other series - Chrome, Safari, Edge, Firefox - are shown faded.

### browser-share.png — 17.7s
> [civicinsight-v1] This line chart titled 'The rise of Google Chrome' shows web browser market share from January 2009 to October 2023. The X-axis shows years from 2009 to 2023. The Y-axis shows 'market share' from 0 to 60, in steps of 10. The series 'Chrome' is selected.

### income-vs-life-exp.png — 33.7s
> [civicinsight-v1] This untitled scatter plot shows GDP per capita against life expectancy at birth for countries in 2021. The X-axis labeled 'Life expectancy at birth' has a range 50 to 85, in steps of 5. The Y-axis labeled 'GDP per capita' shows values from 0 to 100k, in steps of 25k. Individual countries are shown as dots. A country tooltip is visible, showing Qatar at (78, 90k) and Ireland at (83, 115k). Brunei is marked at (70, 55k), Spain at (80, 35k) and the Maldives at (80, 15k). No country is selected, and no tooltip is visible.

### rural-vs-urban.png — 115.6s (truncated at 600 tokens)
> [civicinsight-v1] This stacked bar chart titled 'Rural and urban population' shows the share of population living in the capital, in other urban areas, or in rural areas, broken down by country. [...] The 'in the capital' segment is printed in each bar: China (Beijing) - 53%, USA (Washington, D.C.) - 80%, Australia (Canberra) - 88% [...]

*(Full outputs in `/mnt/civicinsight/results/exp4b-results.json` on the Modal Volume, and in notebook [07-experiment-4b.ipynb](../notebooks/modal/07-experiment-4.ipynb) cell 14.)*

## Hardware / methodology lessons

- **Kaggle T4 was binding on vision unfreeze**, not the approach. Commercial pivot (A100 80GB via Modal) unblocked the result. Total compute cost for this run: ~$15 including debugging + training.
- **`target_modules="all-linear"` is the canonical Unsloth Gemma 4 vision-unfrozen config.** Explicit list of text-specific module names (`q_proj`, `k_proj`, etc.) doesn't extend to vision tower paths → vision LoRA never attaches. Spent ~$4 of A100 time discovering this via per-submodule param breakdown.
- **Modal's ephemeral container filesystem (`/root/` wipes on kernel shutdown)** cost us a round-trip: model + dataset had to be re-uploaded after overnight idle timeout. Volume mount (`/mnt/civicinsight/`) is the persistent path. Lesson: set up Volume *before* any data upload, not after first training works.

## Decisions locked for next phase

Per prof's Apr 22 prescription: **vision unfreeze ✓ → DPO → scale data to ≥200 examples.**

- **SFT base checkpoint secured** at `/mnt/civicinsight/checkpoints/exp4-visionunfrozen/checkpoint-65` — this becomes DPO's π_ref.
- **DPO preference pairs essentially free:** gold = `dataset.marked.json` aria_labels (already have 50). Rejected = Exp 4 (frozen) outputs with marker-missing / slot-drift / banned adjective failures (already captured in `docs/exp4-results.md` + `docs/exp4-reproducibility-0421.md`). No new data collection needed for first DPO pass.
- **Scale data path:** user committed to 50 → 200+. Independent workstream from A100 setup; can proceed in parallel.

## Relation to original Checkpoint 2 question

Checkpoint 2 (Apr 25) asked: *"Does fine-tuning actually work?"* Success criteria were: "model generates coherent aria-labels, overfitting behavior understood and documented, accuracy 60%+."

**Answer: yes, fine-tuning works** — with the correction that vision unfreeze is load-bearing. On 50 examples + vision-unfrozen SFT alone (no DPO, no data scale), three scorecard metrics hit 100% on held-out set. Specific vision failures from Exp 4 are substantially eliminated. Remaining imperfections are well-scoped, attributable, and map to next-phase interventions (DPO + data scale, both already prescribed).

The honest Checkpoint 2 framing: *"SFT with vision unfreeze produces coherent, marker-disciplined aria-labels with material vision-fidelity improvements on a 5-image held-out. Positional-schema-filling and internal-consistency drift remain as preference-layer problems, not style or imitation problems — exactly the shape DPO is designed for."*
