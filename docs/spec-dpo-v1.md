# exp4c-dpo: DPO v1 training spec

**Status:** Ready for execution after SFT retrain (`spec-sft-retrain.md`) completes successfully. Vision DPO end-to-end working as of Apr 27 after upstream fixes landed in Unsloth issue #5196.

**Goal:** Train DPO v1 on top of the choropleth-augmented SFT checkpoint (`exp4c-sft`) using preference pairs targeting documented failure modes from the held-out audit. Score post-DPO outputs against the held-out audit. Ship v1 with DPO if calendar permits and gates pass.

**Base SFT checkpoint:** `exp4c-sft` (NOT exp4b). DPO trains on the latest SFT, not the original.

**Time budget:** ~3-4 hours total (training + scoring + integration). DOES NOT include preference pair construction time — see below.

---

## Why DPO is independent of SFT retrain outcome

The SFT retrain addresses chart-type recognition (a perception-class problem). DPO addresses output behavior style preferences (hedging, fabrication, positional binding, marker compliance — preference-class problems).

These are orthogonal:

**Retrain CAN fix:** choropleth-as-gradient projection, possibly other chart-type confusion failures.

**Retrain CANNOT fix:**
- `confident_invention` of axis metadata, tick steps, counts (3/5 of held-outs)
- `false_selection` (browser-share)
- `fabricated_tooltip` with externally-sourced facts (income-vs-life-exp Ireland $105k from world knowledge)
- `positional_binding error` on stacked bars (rural-vs-urban headline failure)
- `hedge_injection` ("approximately X" when X is visible)
- `marker_stripping` and `wrong_slot` openings

**DPO targets the second list, not the first.** The two trainings address different failure modes. Running DPO is not contingent on which failures the SFT retrain addresses or doesn't.

The real gate for DPO v1 in the May 18 submission is **calendar**, not failure-mode survival. The DPO-class failures will always survive the SFT retrain because they're outside its scope.

---

## Pre-flight checks

Before running DPO training, verify:

1. **Verified working stack is installed.** Test against `notebooks/modal/dpo-vision-repro.ipynb` — confirm synthetic test trains end-to-end. If synthetic works, real training will work.

   The verified working stack as of Apr 30 (after PR #5199 merged into mainline):
   ```
   unsloth: git+https://github.com/unslothai/unsloth.git@4f9c8321a2136e62fd86fe722a544afd534334a5
   trl: 0.24.0
   torch: 2.11.0+cu129 + matching torchvision (--index-url https://download.pytorch.org/whl/cu129)
   transformers: 5.5.0
   datasets: 4.3.0
   peft: 0.19.1
   unsloth-zoo: 2026.4.9
   bitsandbytes: 0.49.2
   Python 3.12, A100 80GB Modal
   ```

   This pin includes all three fixes from issue #5196: tokenization hang (a9729c8), data collator schema (6b11713), and vision keys handling (dc3e6a5 + post-merge `dpo_trainer_data_collator_vision_keys` patch).

   Earlier pin `git+https://github.com/datta0/unsloth@e96d05ba` orphaned after Datta0 force-pushed his branch during PR cleanup. That commit ID still resolves but is no longer reachable from any branch — install for stability is on official `unslothai/unsloth` mainline post-merge.

2. **exp4c-sft checkpoint exists** at `/mnt/civicinsight/checkpoints/exp4c-sft/checkpoint-N/` and is accessible.

3. **chpth-1 audit on exp4c-sft is complete.** This validates the SFT retrain succeeded before adding DPO on top.

4. **Modal Workspace Budget** confirmed at $100. DPO training adds ~$15 in GPU time.

5. **dataset.marked.json contains all 14 augmented images and their annotations** from the SFT retrain.

---

## Preference pair construction

**Time budget for pair construction:** ~5-7 hours. This is NOT included in the 3-4 hour training budget.

### Strategy: synthetic perturbations of gold annotations

Build pairs from the existing 50 SFT golds plus the 10 new ones (60 total potential pairs). For each gold, apply a perturbation function to produce a "rejected" version. Eight perturbation types in rotation:

1. **strip_marker** — removes the `[civicinsight-v1]` prefix
2. **wrong_slot** — replaces the chart-type opener with a wrong type ("This bar chart shows..." for a scatter)
3. **inject_hedge** — adds "approximately" or "roughly" before precise values
4. **break_consistency** — swaps a number or label mid-description
5. **positional_schema_swap** — for stacked bar / multi-segment charts, swaps positional bindings (this is the rural-vs-urban target perturbation)
6. **googly_wrap** — adds an unprofessional preamble or postamble
7. **force_clean_structure** — invents a clean schema that doesn't exist in the image. For images where N tooltips are visible but they don't cover all M categories from the legend, the rejected version reframes them as "one tooltip per category, all categories represented" — even when the actual data shows only a subset of categories. This targets the `structural_fabrication` failure mode surfaced on the Élections viz scatter Apr 27.
8. **proper_noun_prior_substitution** — replaces an obscure proper noun in the gold (e.g., "Sartène", "Revin", "Ploërmel") with a more famous regional alternative (e.g., "Ajaccio" for Sartène, "Charleville-Mézières" for Revin), keeping all surrounding numeric data accurate. Targets the `proper_noun_prior_substitution` failure mode verified Apr 27 — model substitutes obscure communes with famous ones from its pretraining prior.

Some perturbations are no-ops on certain golds (e.g., positional_schema_swap on a single-encoding line chart, force_clean_structure on charts where no tooltips are visible, proper_noun_prior_substitution on charts with no proper nouns). Filter `if rejected != gold` to drop these.

### Over-sampling on critical failure modes

The audit identifies specific high-priority failures. Over-sample perturbations targeting them:

- **positional_schema_swap on rural-vs-urban** (the headline DPO target)
- **fabricate_external_fact on income-vs-life-exp** (the Ireland $105k pattern — needs a perturbation that adds fake world-knowledge values)
- **inject_hedge on values that are clearly visible**
- **force_clean_structure on multi-tooltip images where blocs are unevenly represented** (the Élections viz scatter pattern — high accessibility risk)
- **proper_noun_prior_substitution on golds containing obscure French communes** (Sartène→Ajaccio pattern verified Apr 27 — high civic-data accessibility risk because famous-name substitutions read as plausible)

These should appear at higher frequency than the round-robin would produce.

### Expected pair count

With 60 source golds × 6 perturbations × filtering = ~50-55 valid preference pairs. Enough for one DPO run on the working stack.

### Schema

**Critical:** Prepend `tokenizer.image_token` to the prompt string. Without it, the prompt has no image-token placeholder, input_ids has 0 image-token slots, and the vision encoder produces N image features with nowhere to inject them. Symptom: `ValueError: Image features and image tokens do not match, tokens: 0, features: 512` when training starts.

This is a usage-side requirement, not an Unsloth bug. SFTTrainer auto-handles image token insertion via apply_chat_template; DPOTrainer with raw string prompts does not.

```python
# tokenizer is a Gemma4Processor; tokenizer.image_token resolves to "<|image|>"
PROMPT = f"{tokenizer.image_token}\nGenerate an aria-label for this data visualization image."

def make_pair(image, gold, rejected, prompt=PROMPT):
    return {
        "images": [image],   # flat list of PIL images, NOT chat-template wrapped
        "prompt": prompt,
        "chosen": gold,
        "rejected": rejected,
    }

# Wrap as Dataset before passing to DPOTrainer
from datasets import Dataset
pairs_ds = Dataset.from_list(pairs)
```

**Alternative:** construct prompts via apply_chat_template with `[{"type": "image"}, {"type": "text", "text": "..."}]` for proper conversation-style messages. More robust to chat template changes but slightly more verbose.

**Validation cell to run before training** (catches the issue before the 15-minute training run):

```python
sample = pairs_ds[0]
processed = tokenizer(
    text=sample['prompt'] + sample['chosen'],
    images=sample['images'],
    return_tensors="pt",
)
n_image_tokens = (processed['input_ids'] == tokenizer.image_token_id).sum().item()
assert n_image_tokens > 0, f"No image tokens in input_ids — prompt missing {tokenizer.image_token}"
print(f"OK: {n_image_tokens} image-token slots in input_ids, {processed['pixel_values'].shape[0]} pixel batches")
```

---

## Training configuration

```python
from trl import DPOConfig, DPOTrainer

dpo_config = DPOConfig(
    beta=0.1,                              # KL penalty strength, standard
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,         # effective batch of 4
    num_train_epochs=3,                    # DPO converges faster than SFT
    learning_rate=5e-6,                    # ~40x lower than SFT, standard for DPO
    output_dir="/mnt/civicinsight/checkpoints/exp4c-dpo",
    max_length=2048,
    max_prompt_length=1024,                # DPO-specific: max tokens for prompt portion
    remove_unused_columns=False,           # required for image+text format
    logging_steps=1,                       # log every step
    dataset_num_proc=2,                    # Modal os.cpu_count()=47 lies, ~2 cores
    save_strategy="epoch",                 # save once per epoch
)
```

LoRA config mirrors exp4c-sft.

---

## Trainer instantiation

```python
dpo_trainer = DPOTrainer(
    model=model,                        # exp4c-sft loaded with LoRA attached
    ref_model=None,                     # auto-creates frozen reference from current state
    processing_class=tokenizer,         # NOT tokenizer=tokenizer (newer TRL API)
    train_dataset=pairs_ds,
    args=dpo_config,
)
```

---

## Working DPO-from-SFT load pattern

```python
from unsloth import FastVisionModel
from peft import set_peft_model_state_dict
from safetensors.torch import load_file as safe_load

model, tokenizer = FastVisionModel.from_pretrained(
    "/mnt/civicinsight/model",
    load_in_4bit=True,
    use_gradient_checkpointing="unsloth",
)
model = FastVisionModel.get_peft_model(
    model, r=16, lora_alpha=32, lora_dropout=0, bias="none",
    finetune_vision_layers=True,
    finetune_language_layers=True,
    finetune_attention_modules=True,
    finetune_mlp_modules=True,
    target_modules="all-linear",
)
SFT_CHECKPOINT = "/mnt/civicinsight/checkpoints/exp4c-sft/checkpoint-N"
sft_state = safe_load(SFT_CHECKPOINT + "/adapter_model.safetensors")
load_result = set_peft_model_state_dict(model, sft_state)

assert not load_result.unexpected_keys, f"Unexpected keys: {load_result.unexpected_keys[:5]}"
model.print_trainable_parameters()
```

NOT `PeftModel.from_pretrained` — fails on `Gemma4ClippableLinear` with PEFT 0.19.1.

---

## Expected training behavior

Based on synthetic test:
- Training time: ~3-4 minutes per epoch on A100 80GB
- ~10-12 minutes total for 3 epochs
- Loss starts at ln(2) ≈ 0.693 (random baseline)

Real preference data should NOT overfit to 0.0005 like synthetic — that was an artifact of synthetic preferences being trivially distinguishable.

**Healthy real-data loss curve:**
- Starts ~0.69
- Drops to 0.3-0.5 range by end
- rewards/accuracies in 0.7-0.9 range
- rewards/margin clearly positive

**Warning signs:**
- Loss drops below 0.05 too quickly: perturbations too easy, model not learning generalizable preferences. Investigate perturbation diversity.
- Loss stays at 0.69 throughout: rejected pairs aren't producing distinguishable signal. Check that rejected != gold actually differs meaningfully.

---

## Validation gates

### Gate 1: Training completed cleanly

- All ~39 steps executed (3 epochs × 13 batches per epoch, depending on pair count)
- Loss decreased from baseline
- rewards/accuracies > 0.7 by final step
- rewards/margin clearly positive
- Final checkpoint saved at `/mnt/civicinsight/checkpoints/exp4c-dpo/checkpoint-N/`

If any fail, do not proceed to scoring. Investigate.

### Gate 2: Post-DPO held-out sweep

Run inference on the same 5 held-out images:
- baseline-1.png (choropleth — primarily exp4c-sft territory but baseline check)
- browser-share.png (line chart, no selection)
- browser-share-other-filtered.png (line chart, "Other" selected)
- income-vs-life-exp.png (scatter — Demo 2 critical, the fabricated_tooltip target)
- rural-vs-urban.png (stacked bar — positional_binding target, the headline DPO win)

Use `do_sample=False`, same prompt as pre-DPO. Save outputs to known path.

### Gate 3: DPO improvement scorecard

Compare pre-DPO (exp4c-sft) outputs against post-DPO (exp4c-dpo) outputs on each held-out:

**Targeted improvements (the DPO win conditions):**
- rural-vs-urban: positional binding errors reduced or eliminated
- income-vs-life-exp: Ireland $105k externally-sourced fabrication reduced
- browser-share-other-filtered: subtitle range substitution reduced
- general: hedge injection reduced, marker compliance maintained
- structural fabrication patterns reduced (test on Élections viz scatter — was forcing one-tooltip-per-bloc framing onto images with uneven bloc distribution)
- proper-noun-substitution reduced (test on Élections viz scatter — was substituting "Sartène" with "Ajaccio")

**Maintained capabilities (no-regression):**
- Marker presence: 5/5 still
- Slot opener consistency: still
- Output structural validity: still

**Acceptable: marginal improvement on 2-3 of the targeted failures**
**Unacceptable: regression on the maintained capabilities**

### Gate 4: chpth-1 maintained

DPO should NOT regress the choropleth-handling improvements from exp4c-sft. Run chpth-1 inference on exp4c-dpo, confirm output quality matches exp4c-sft (or improves marginally if DPO happened to also help there).

### Gate 5: ship vs revert decision

Ship v1 with exp4c-dpo if:
- Gates 1-4 pass
- Targeted improvements visible on rural-vs-urban OR income-vs-life-exp (at least one)
- No regression on maintained capabilities
- No regression on chpth-1

Revert to exp4c-sft if:
- DPO introduces new failure modes
- Targeted failures don't improve at all
- Output style drifted in ways that break the agentic shell's assumptions

If on the fence: try lowering `beta` (e.g., 0.05) for softer KL constraint, or reduce epochs to 2. Don't endlessly tune — DPO with one set of hyperparameters either helps or it doesn't.

---

## Integration tasks (if Gate 5 = ship)

1. **Update model on HF Hub** — push exp4c-dpo to `shahfazal/civicinsight-gemma4-e4b-it` with revision tag `v0.3-dpo`. Keep exp4c-sft accessible as previous revision.

2. **Update inference path in `app/io/inference.py`** — point at exp4c-dpo by default.

3. **Update Kaggle submission notebook** — re-run Demo 2 (income-vs-life-exp) and Demo on rural-vs-urban with DPO model, capture new outputs, update narrative numbers in markdown cells.

4. **Update writeup** — section 4 (Results) gets a real before/after table comparing exp4c-sft vs exp4c-dpo on targeted failures. Section 3 (Architecture) framing changes from "fine-tuning + agentic verification" to "fine-tuning + preference training + agentic verification."

5. **Run benchmark study against exp4c-dpo**, not exp4b or exp4c-sft. Update `bench/scores.csv` accordingly.

6. **Note in writeup limitations:** trained on official Unsloth mainline post-merge of PR #5199, with all three vision DPO bug fixes applied. Pin: `unslothai/unsloth.git@4f9c8321a2136e62fd86fe722a544afd534334a5`. Inference uses the same stack. Adapter weights are version-independent.

---

## Anti-patterns — do NOT repeat

1. No `Gemma4ClippableLinear` patch (the dev.to one). Unsloth handles via target-modules regex.
2. No `UNSLOTH_COMPILE_DISABLE=1`. Was workaround for symptom of (1).
3. No `model.load_adapter()` for DPO. Loads with `inference_mode=True`, freezes LoRA, silently no-ops DPO.
4. No version pins outside the verified working stack from `notebooks/modal/dpo-vision-repro.ipynb`.
5. No `trl 0.22.2` — bug 3 lives there. Use `trl 0.24.0`.
6. No raw-string prompts without image token. PROMPT must start with `tokenizer.image_token` (`<|image|>` for Gemma4) or training fails with `tokens: 0, features: 512` at first step.
7. No commit-pinned installs from contributor forks for long-lived references. Branch tips can force-push; orphaned commits eventually GC'd. Pin to merge commits on official repo (`unslothai/unsloth.git@<merge-hash>`) for stability.

---

## Calendar gate (binary)

DPO v1 ships in May 18 submission ONLY IF:

- exp4c-sft is locked in by [TBD date — work backwards from May 13 HF flip]
- Preference pair construction can fit in 5-7 hours of focused work
- DPO training + scorecard + integration fits in another 4-6 hours
- Other critical-path work (video, writeup, benchmark, a11y, demo polish) has not slipped

If any of these conditions fails: SHIP exp4c-sft + agentic shell. DPO becomes v2 with its own writeup post-submission.

The DPO recipe and the choropleth retrain together would be a strong v2 release on their own — "v2: post-training improvements after v1 submission" reads as deliberate engineering, not failure to ship.

**Don't take the DPO calendar gate emotionally.** The recipe works. The pipeline is verified. Whether it ships in v1 vs v2 depends on what fits cleanly in the calendar, not on what's technically feasible.

---

## Writeup framing (if shipped)

> "v1 ships with two stages of post-training: SFT for format and structure on 64 civic-data examples (50 original + 14 categorical/dual-encoded choropleths), followed by DPO with synthetic perturbations targeting six known failure modes from a documented held-out audit. The agentic verification layer catches numeric grounding errors that survive both stages by cross-referencing extracted values against optional source CSVs. The full pipeline addresses [X out of N] failure modes documented in the held-out audit. Remaining gaps are tracked in `docs/post-kaggle-backlog.md`."

That's a strong, honest, complete engineering arc.

---

## Files referenced

| Purpose | Path |
|---|---|
| SFT retrain spec (prerequisite) | `spec-sft-retrain.md` |
| Pre-DPO audit (failure modes) | `docs/civicinsight-pre-dpo-audit.md` |
| Working DPO stack reference | `notebooks/modal/dpo-vision-repro.ipynb` |
| Public bug report | https://github.com/unslothai/unsloth/issues/5196 |
| Upstream PR (merged Apr 28) | https://github.com/unslothai/unsloth/pull/5199 |
| Source data (existing dataset) | `dataset.marked.json` |
| Held-out images | `examples/standardized/baseline-1.png` etc., plus `chpth-1.png` |
