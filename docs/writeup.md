# CivicInsight: ARIA-ready descriptions for civic data visualizations

## Why this matters

CivicInsight is an attempt to make ARIA-ready descriptions for data visualizations both generatable and trustworthy. A fine-tuned Gemma 4 E4B model paired with a deterministic verification layer, it extracts actual values, trends, and structural relationships from chart screenshots, running locally on commodity GPU, MIT-licensed, with no API spend and no third-party calls. Numbers from the model are treated as claims to be checked, not tokens to be trusted. Specialization plus verification produces output users can both understand and trust.

Civic data is meant to inform public decision-making. Election results, hospital wait times, air quality, school performance, transit reliability: governments publish this data, often as interactive visualizations on official portals. For screen reader users, these charts with multi-encoded visuals, tooltips, and selection states can surface as "image" or "chart" with no underlying values. Major BI platforms (Power BI, Tableau) and viz services (Datawrapper) bake accessibility into their tooling, but pricing and editorial workflows put them out of reach for many civic publishers. The default is a static chart image, embedded in a blog post, press release, or research report, with no underlying data structure attached. Even my own [elections visualization](https://shahfazal.com/elections-municipales-2026/), which ships 70 ARIA attributes and three custom keyboard handlers, leaves chart content opaque to screen readers: the gap between accessible UI chrome and accessible chart data is the hard one.

Generic alt-text tools (AltText.ai, Writer.com) produce sparse, inconsistent outputs. Frontier-model APIs (Claude, GPT4) work well on raw vision but require ongoing spend and route data to third parties, a conflict with data residency requirements.

## What the base model gets right, and what it doesn't

Before fine-tuning, I ran a zero-shot audit of Gemma 4 E4B on 27 civic data visualizations: 9 real-world charts and 18 synthetic, covering choropleth maps, line charts with multiple filter states, scatter plots, and stacked bars. Verbatim outputs are committed to [`notebooks/kaggle/01-zero-shot-evaluation.ipynb`](https://github.com/shahfazal/civicinsight/blob/main/notebooks/kaggle/01-zero-shot-evaluation.ipynb). Five held-out images anchor the qualitative analysis in sections 3 and 5.

The base model handles **text printed on the chart** with full precision across all 27 images. Titles, axis labels, legend entries, source attributions, and units extracted correctly.

The base model fails systematically on **visually encoded values**. Nine distinct failure modes emerged from the audit, including proportional bar misreading, interactive state blindness, and prior knowledge overriding visual evidence. Errors on proportional bars ranged from 5 to 30 percentage points. The failure mode is consistent: the model produces a plausible-sounding number that wasn't in the chart, with no signal to the reader that the value was inferred rather than read.

One representative case from the held-out set: a stacked bar of rural-vs-urban population. China's row shows 53% and 46%, which the legend binds to **other urban areas** and **rural areas** (capital share is too small to print). The model output reads "53% capital, 46% other urban, 0% rural", binding each visible number one category to the left and confidently asserting a zero where the actual rural share is 46%.

This pattern is not Gemma-specific. Frontier vision models exhibit the same failure mode at lower error rates: numbers get fabricated when they need to be measured. Any architecture for civic data viz accessibility has to address fabrication structurally, not by hoping a larger model is enough.

## Architecture: specialization plus verification

CivicInsight is a two-layer system. A fine-tuned Gemma 4 E4B generates the description; a deterministic verifier grounds the numeric claims against source data when available. Each layer addresses one of the failure modes from the audit. Fine-tuning shapes the description style, format, and selection-awareness that section 2's failure analysis showed the base model lacks. Verification addresses the fabrication problem directly, by treating numbers as claims to be checked rather than tokens to be trusted.

The verifier has two stages. First, a structural validator runs on every output. It checks for a `[civicinsight-v1]` marker, at least one numeric token, a chart-type word, and minimum length. Outputs missing the marker short-circuit to `structural-issue` and skip grounding entirely.

Second, a numeric cross-check runs when the user supplies a source CSV. A regex-based extractor pulls numeric tokens from the description and classifies each one: value, year, postal/INSEE code, or axis tick. Years, codes, and axis numbers are filtered out. The remaining `value` records are matched against a CSV index with adaptive tolerance: 5% for K/M/B/T-scaled values, 0.5% for raw numbers. When multiple CSV rows could match a value, the matcher disambiguates by overlap between the description's surrounding context tokens and the candidate row's headers. A numeric coincidence with an unrelated row is flagged as likely fabrication, not confirmed.

The output reports one of four states. **Verified**: every eligible value matched. **Partial**: some matched, some didn't. **Unverified**: no CSV provided, no eligible values, or none matched. **Structural-issue**: the output failed validation.

The video shows the partial case on a Global CO2 emissions chart (Our World In Data). Of 4 eligible numeric claims, 1 matched the CSV: the tooltip value of 8336 megatonnes for Coal in 1986. The y-axis bounds (0, 14000) and the series count (3) had no source match and were flagged unverified. Final state: partial, 25% confidence, with per-value detail surfaced to the user. Specialization produces a description; verification tells the user which parts of it are grounded and which to trust at their own risk.

## Training methodology and the Unsloth contribution arc

CivicInsight is a fine-tune of Gemma 4 E4B (4-bit quantized, vision-unfrozen LoRA r=16) on 61 hand-curated civic data viz examples. Small by intent: the goal was format and style transfer, not knowledge transfer. The base model already has the vision capability to read these charts (section 2 confirmed text extraction is reliable); what it lacked was the structural discipline to produce ARIA-ready descriptions, identify selection states, and stay grounded to the image.

Vision DPO on Gemma 4 was the planned next step. DPO infrastructure took longer than the fine-tuning. Three blockers surfaced on `trl 0.22.2` + `unsloth 2026.4.8`: a tokenization hang in `dataset.map`, a data collator schema mismatch, and a vision tower AttributeError. I filed [unslothai/unsloth#5196](https://github.com/unslothai/unsloth/issues/5196) with reproductions and four documented workaround attempts. The fix landed in [PR #5199](https://github.com/unslothai/unsloth/pull/5199), merged into main on April 29, 2026.

I verified end-to-end on commit `4f9c832` with the full pinned stack: synthetic DPO converged cleanly on the infrastructure-validation toy pairs, loss 0.6931 to 0.0005 (full table in [`notebooks/modal/dpo-vision-repro.ipynb`](https://github.com/shahfazal/civicinsight/blob/main/notebooks/modal/dpo-vision-repro.ipynb)), rewards/accuracies 0 to 1.0. The infrastructure was solid.

Whether to actually use DPO for CivicInsight v1 was a separate question, and the answer was no. Synthetic preference pairs were gameable: the model learned to prefer responses that _looked_ more confident over ones that _were_ more accurate. The deterministic verification layer addressed the same residual failure modes (fabrication, ungrounded confidence) more reliably and without the synthetic-pair gaming surface.

## Results and limitations

Across the five held-out images, the fine-tuned model produces ARIA-ready descriptions in the intended structure: chart title, axis ranges, selected series, tooltip values, and the `[civicinsight-v1]` marker for the verifier. On the Corsica EV-charger choropleth and the browser-share line chart, the model correctly identifies which commune or browser is selected and reads the tooltip value (Corté with 9 chargers; the "Other" series at 9% in August 2020). On the CO2 emissions chart with source CSV, the verifier surfaces 1 of 4 numeric claims as matched and the rest as unverified, and the user gets per-value detail rather than a global trust signal.

The post-SFT held-out audit ([`docs/civicinsight-pre-dpo-audit.md`](https://github.com/shahfazal/civicinsight/blob/main/docs/civicinsight-pre-dpo-audit.md)) also surfaces what the system does not catch. On the income-vs-life-expectancy scatter, the model fabricated a plausible label ("Ireland, GDP $105,000, life expectancy 81") with no tooltip in the image to anchor the claim. On a Corsican commune scatter, all numerics were extracted correctly, but the small commune Sartène was substituted with Ajaccio (population ~70,000 versus ~3,000). The verifier's scope is numeric values; place-name substitution and chart-type identification are not cross-checked.

The base model's vision capability is preserved. On an out of distribution, non-chart image (a cheetah portrait), the model produces a structured description without hallucinating chart elements.

Other limitations: DPO was not used in v1; multi-page dashboards are unsupported; the dataset and prompt are English only.

## Reproducibility and license

Code is MIT-licensed at [github.com/shahfazal/civicinsight](https://github.com/shahfazal/civicinsight). The fine-tuned model is at [huggingface.co/shahfazal/civicinsight-gemma4-e4b-it](https://huggingface.co/shahfazal/civicinsight-gemma4-e4b-it), Apache 2.0 (Gemma) plus the LoRA adapter under MIT. The live demo runs on Modal at [shahfazal--civicinsight-web-fastapi-app.modal.run](https://shahfazal--civicinsight-web-fastapi-app.modal.run), public.

The system runs locally on commodity GPU, on Modal, or through HuggingFace inference. Specialization plus verification, MIT-licensed, no third-party calls.
