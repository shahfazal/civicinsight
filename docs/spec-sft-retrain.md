# exp4c-sft: SFT retraining with expanded choropleth coverage

**Status:** Spec. Not yet executed.

**Context:** Pre-submission held-out test on the Paris arrondissements choropleth (`choropleth-paris.png`) revealed the model fabricates an entire price-encoding system that doesn't exist on the map. Root cause: training set imbalance — 4 choropleth examples total, with the price-gradient pattern dominant. The model compressed "choropleth" to "price color scale" and projects that schema onto categorical maps.

**Goal:** Retrain SFT with expanded categorical choropleth examples to teach the model to distinguish gradient vs categorical encoding. Maintain the existing 5/5/5 scorecard on the held-out 5 images.

**Scope constraint:** This is NOT a redesign. Same SFTTrainer code path that exp4 and exp4b used successfully. SFT works on this stack — only DPO has the upstream bug. Adding training examples and re-running SFT is a known-working operation.

---

## What this fixes

| Failure mode | Held-out image affected | Root cause |
|---|---|---|
| Fabricated color encoding system | choropleth-paris (post-hoc test, not in original 5) | 3-of-4 training choropleths were price-gradient, pattern dominates |
| Forced "selected vs faded" two-state on multi-state map | choropleth-paris | Same root cause; model defaults to two-tier visual grammar |

What this does NOT fix (deferred to v2 post-DPO):
- Subtitle/axis range substitution (browser-share-other-filtered)
- False selection (browser-share)
- Fabricated tooltip with externally-sourced facts (income-vs-life-exp)
- Positional binding errors on stacked bars (rural-vs-urban)
- Generic confident invention of axis metadata across chart types

These are addressed by DPO v2 once upstream library bugs resolve. SFT alone won't fix them.

---

## Training data plan

### Add to dataset.marked.json: 5-7 new categorical choropleth examples

Source material is fully available — Faz has the gold elections data and price data from the Élections Municipales 2026 project (`github.com/shahfazal/elections-municipales-2026`).

### Variation matrix (target 5 examples covering 5 patterns)

| # | Geographic scope | Categories | Encoding | Tooltip state | Notes |
|---|---|---|---|---|---|
| 1 | Paris arrondissements | 3 (Gauche/Centre/Droite) | Bloc winner color only | One arrondissement selected | Mirror Paris held-out test case |
| 2 | Lyon arrondissements | 3 (Gauche/Centre/Droite) | Bloc winner color | None selected | All-shown state for Lyon |
| 3 | Region (Île-de-France or other) | 4 (extreme-left/Gauche/Centre/Droite) | Bloc winner color + density via opacity | Mixed | Dual-encoding teaches model that two encodings can coexist |
| 4 | Departments (départements view) | 3-5 categories | Bloc winner color | One department selected | Different geographic scale than commune-level |
| 5 | Commune cluster (e.g., greater Marseille) | 3 (Gauche/Centre/Droite) | Bloc winner | None selected | Smaller geographic scope, dense urban map |

**Variation principle:** 5 examples covering 5 different patterns beats 10 near-identical maps. The goal is generalization, not pattern reinforcement.

### Do NOT remove existing price-gradient choropleths from training

Keeping the 3 price-gradient examples preserves the model's ability to handle gradient choropleths. Adding 5 categorical examples on top teaches it to distinguish.

If gradient examples are removed, the model trades one capability for another rather than gaining a new one. Net training set goes from 4 choropleths to 8-9 (4 existing + 5 new).

### Image generation pipeline

For each new example:
1. Use the elections data already in `elections-municipales-2026` repo
2. Generate the choropleth via the same Datawrapper-style pipeline used for the existing site visualization
3. Capture screenshot at 1024x1024 (matching the standardization used for existing training images)
4. Save to `examples/raw/` with naming `choropleth_political_{region}.png`
5. Run the standardization script to produce `examples/standardized/choropleth_political_{region}.png`

### Annotation guidelines

Apply the locked rule sheet from the original SFT dataset:
- Use the `[civicinsight-v1]` marker
- Open with the chart type slot ("This choropleth map shows...")
- Describe categorical encoding explicitly: "The arrondissements are colored by winning political bloc: pink for Gauche, yellow for Centre, blue for Droite"
- For selected state: name the selected element and the tooltip values verbatim from the image
- For non-selected state: describe distribution of categories without naming individual elements unless they have labels
- Avoid the "lighter pink" / two-state language that misled the model on the Paris test
- Avoid claims about price encoding when the chart only shows category encoding
- Approximately 100-150 words per annotation, matching existing dataset style

### Quality control before training

Before kicking off training, verify on a small set:

- Re-read each new annotation against its image — does it say only what's visually present?
- Cross-check against the existing rule sheet — do the new annotations follow the same conventions as the original 50?
- Run a manual diff: pick 3 existing choropleth annotations and 3 new ones, confirm they're stylistically consistent

---

## Training run

### Configuration (mirror exp4b exactly)

```python
# Same hyperparameters as exp4b that produced 5/5/5
SFTConfig(
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    num_train_epochs=3,
    learning_rate=2e-4,
    output_dir="/mnt/civicinsight/checkpoints/exp4c-sft",
    max_length=2048,
    remove_unused_columns=False,
    logging_steps=1,
)

# LoRA config also mirrors exp4b
get_peft_model(
    model,
    r=16, lora_alpha=32, lora_dropout=0, bias="none",
    finetune_vision_layers=True,
    finetune_language_layers=True,
    finetune_attention_modules=True,
    finetune_mlp_modules=True,
    target_modules="all-linear",
)
```

### Estimated time

- Image generation + standardization: 1 hour
- Annotation: 2-2.5 hours (~25 min per high-quality annotation × 5)
- Dataset.marked.json update + sanity QC: 30 min
- Training on Modal A100: ~3 hours
- Total: **~6.5-7 hours**

### Output checkpoint name

`exp4c-sft` — distinguishes from exp4b (existing locked checkpoint) and exp4c-dpo (the DPO branch that hit the upstream bug). New SFT, not DPO.

---

## Validation gates

### Gate 1: 5/5/5 scorecard maintained on original held-outs

Run the existing scorecard against the new model on the 5 original held-out images. Required: still 5/5/5.

If the new model regresses on any of the original 5, **do not ship it**. Decision tree:
- 5/5/5: ship the new model
- 4/5 on one image: investigate the regression. If it's a marker/format issue, fixable. If it's a quality regression on a chart type that was previously good, revert to exp4b.
- 3/5 or worse: revert to exp4b unconditionally.

### Gate 2: choropleth-paris improvement

The post-hoc Paris choropleth test that exposed the issue. Required: visible improvement, no regression to a different failure mode.

Specifically:
- Does the model still claim a "price color scale" that doesn't exist? Should be reduced or eliminated.
- Does the model correctly identify the categorical encoding (Gauche/Centre/Droite)? Should be present.
- Does the tooltip extraction match what's visible (8813 €/m², 36.4%, 1523)? Should match.

### Gate 3: held-out audit on the new training images

Reserve 1 of the 5-7 new examples as held-out — don't train on it, only generate the gold annotation for scoring purposes. Run the model on it post-training. This validates that the model learned the new pattern rather than just memorizing.

---

## Roll-out plan

If both gates pass:
1. Update `notebooks/modal/07-experiment-4.ipynb` (or branch off as `notebooks/modal/07b-experiment-4c-sft.ipynb`)
2. Push new model to HuggingFace Hub at the same model repo with a new revision/branch
3. Update `app/io/inference.py` to point at the new checkpoint
4. Re-run held-out sweep, save new outputs
5. Update Kaggle submission notebook's demo cells with new outputs
6. Update writeup limitations section: choropleth handling now improved; remaining failure modes documented

If gates fail:
1. Keep exp4b as canonical
2. Document the experiment in `docs/exp4c-sft-attempt.md` for future reference
3. Add the Paris choropleth failure to the writeup's limitations section as a known issue
4. Move on to other priorities

---

## Decision: do this or skip?

Skip if:
- Less than 6.5 hours of focused time available before May 13 (HF public flip)
- Original 5/5/5 scorecard on held-outs is more important than choropleth coverage
- Other work (benchmark, video, demo polish) is at risk of slipping

Do this if:
- 6.5-7 hours of focused time available in one or two sittings
- The Paris choropleth output is below acceptable quality bar AND a choropleth is needed in the demo or video
- Calendar shows clear runway through May 13

The exhaustion check from previous session applies: if running this means working past sustainable hours or sacrificing other deliverables, skip it. exp4b ships with documented limitations.

---

## Open question for Faz

**Is choropleth handling actually needed for the demo and video?** If the demo uses bar charts, scatter plots, or line charts as primary examples, the Paris choropleth weakness is purely a writeup-limitations issue and doesn't justify retraining. Worth answering before committing the time.
