# CivicInsight pre-DPO held-out audit

**Date:** April 26, 2026
**Model:** exp4b SFT checkpoint (5/5/5 scorecard), prior to DPO v1
**Inference:** greedy decoding (`do_sample=False`), byte-stable across kernel restarts
**Held-outs:** 5 images in `/mnt/civicinsight/test/`

This audit captures the failure modes present in the SFT model before DPO. Each image is reviewed line-by-line against what's actually visible. Findings feed into the v2 DPO backlog (`exp4d-spec.md`) and the scorecard tightening pass.

The 5 images cover four chart types: choropleth map, line chart (two filter states), scatter plot, stacked bar chart.

---

## Image 1: `baseline-1.png` — French commune real estate prices (choropleth)

**Generation time:** 133-181s

**Model output:**
> [civicinsight-v1] This choropleth map shows real estate prices per square metre in French communes. The color scale ranges from 0 - 1076 (light pink) to 2989 - 6571 (dark red), with steps of 1 000. The map is centered on Plœrières, which is currently selected with a tooltip showing a price of 2643 EUR/m2. The legend on the right shows the color scale: dark blue (top) is 0 - 1 076, light blue is 1 076 - 1 394, green is 1 394 - 1 568, yellow is 1 568 - 1 730, pink is 1 730 - 1 944, light red is 1 944 - 2 187, pink-red is 2 187 - 2 560, red is 2 560 - 2 989, and dark red (bottom) is 2 989 - 6 571. The map also shows commune names: Ajaccio, Plouguer, Rostrenen, Ste-Anne-du-Faou, Gourin, Cléguérec, Pontivy, Loudéac, Saint-Méen-le-Grand, Mauron, Scorien, Le Faouët, Quimperlé, Hennebont, Lorient, Auray, Vannes, Saint-Gildas-de-Rheux, Quiberon, Herbignac, Plœrmel, Guer, and Bruz.

### Errors found

1. **Hallucinated commune name in tooltip.** Tooltip header reads "Ploeren" (a real commune west of Vannes). Model output: "Plœrières" — confident misread auto-corrected toward a more typo-plausible French name. Worse than confabulation: confidently misreading text that's directly visible in the tooltip.

2. **"Steps of 1 000" — wrong.** The legend bins are: 0-1076, 1076-1394, 1394-1568, 1568-1730, 1730-1944, 1944-2187, 2187-2560, 2560-2989, 2989-6571. Step sizes range 200-400 with a final huge bucket. Model listed every bin correctly inline, then summarized them as "steps of 1 000" — internally contradictory with what it just said.

3. **"0 - 1076 (light pink) to 2989 - 6571 (dark red)" — wrong color.** 0-1076 is dark blue per the legend (which the model correctly identifies in the very next paragraph). Self-contradiction in adjacent sentences.

4. **"Centered on Plœrières" — fabricated framing.** No centering exists in the image. There's a tooltipped commune (Ploeren), the visual center is roughly Vannes. "Centered on" is the wrong frame entirely.

5. **Commune name list partially fabricated.** Real names visible in the image: Plouguer, Rostrenen, Gourin, Cléguérec, Pontivy, Loudéac, Saint-Méen-le-Grand, Mauron, Le Faouët, Quimperlé, Hennebont, Lorient, Auray, Vannes, Quiberon, Herbignac, Plœrmel, Guer, Bruz. Hallucinated names not in image: Ajaccio (Corsican city, not Brittany), "Ste-Anne-du-Faou" (real name is Châteauneuf-du-Faou), "Saint-Gildas-de-Rheux" (real name is Saint-Gildas-de-Rhuys), "Scorien" (not a real place). Worse than zero list: partially-correct list looks authoritative.

### Failure modes identified
- `confident_invention` (steps of 1000)
- `color_self_contradiction` (light pink vs dark blue for 0-1076)
- `hallucinated_entity` (Ajaccio, Plœrières, Ste-Anne-du-Faou, etc.)
- `fabricated_framing` (centered on X)

---

## Image 2: `browser-share-other-filtered.png` — Browser market share, "Other" selected

**Generation time:** 33.5-36.5s

**Model output:**
> [civicinsight-v1] This line chart titled 'The rise of Google Chrome' shows web browser market share from January 2009 to October 2023. The X-axis shows years from 2009 to 2023. The Y-axis shows market share from 0 to 60% in steps of 10. The series 'Other' is selected with a tooltip showing 9% in 1 août 2020. The Safari line is shown in light blue and the other lines - Chrome, Edge, Firefox - are faded.

### Errors found

1. **Subtitle range substituted for x-axis tick range.** Subtitle reads "Web browser market share, January 2009 to October 2023." Visible x-axis ticks: 2010, 2012, 2014, 2016, 2018, 2020, 2022. Model conflated the two — claimed the x-axis "shows years from 2009 to 2023." The training data design explicitly avoids this (rules sheet: "ignore subtitle scope") but the model violated the rule. Suggests pre-training prior leakage rather than poisoned signal.

2. **Invented categorical state — Safari called "light blue" while others called "faded."** Looking at the image: Safari is the darker blue line that flatlines around 18% from 2017 onward. The model split the four non-selected series into two tiers (Safari + the others) that don't exist as a distinction in the image. All four non-selected series are equally faded.

### What worked
- Correctly identified "Other" as the selected series
- Correctly noted the tooltip and its value (9% on 1 août 2020)
- Correctly used "faded" language for non-selected series

### Failure modes identified
- `subtitle_axis_substitution`
- `invented_categorical_state`

---

## Image 3: `browser-share.png` — Browser market share, none selected

**Generation time:** 23.3-24.1s

**Model output:**
> [civicinsight-v1] This line chart titled 'The rise of Google Chrome' shows web browser market share from January 2009 to October 2023. The X-axis shows years from 2009 to 2023. The Y-axis shows market share from 0 to 60% in steps of 10. The series 'Chrome' is selected.

### Errors found

1. **False selection — "Chrome is selected" when nothing is.** Looking at the image: all six lines (Chrome, Safari, Other, Edge, Firefox, IE) are equally rendered with no fade and no tooltip. The training data design has exactly two valid states: one-selected-rest-faded OR none-selected-all-shown. The model produced a third state that doesn't exist in training: "one selected, rest equally rendered (no fade)."

2. **Same subtitle/axis substitution as Image 2.** Carry-over of the same failure mode.

### What worked
- Output appropriately terse (didn't over-describe)

### Failure modes identified
- `false_selection`
- `subtitle_axis_substitution` (carryover)

### Why this is interesting

The model is forcing two-state grammar onto an image that genuinely has one state (no selection). It picks Chrome as the "selected" series — likely because Chrome is in the chart title ("The rise of Google Chrome") or because Chrome is the topmost series at end of timeline. Plausible prior, wrong output.

---

## Image 4: `income-vs-life-exp.png` — GDP vs life expectancy scatter plot

**Generation time:** 36.0-36.8s

**Model output:**
> [civicinsight-v1] This untitled scatter plot shows 'Life expectancy at birth' on the X-axis and 'GDP per capita' in US-Dollars on the Y-axis. The X-axis shows values from 50 to 85, in steps of 5. The Y-axis shows values from 0 to 100k, in steps of 25k. A country is selected with the tooltip: Country - Ireland, GDP per capita - 105 000 US-Dollars, Life expectancy at birth - 81, years. The other countries are shown as dots with no tooltips visible.

### Errors found

1. **"Untitled" — wrong.** Title "Income vs life expectancy" is in bold at the top of the image, one of the most visually prominent elements. Confident invention in the absence direction (claiming absence of a feature that's clearly present).

2. **"Steps of 25k" — wrong.** Visible y-axis labels: 0, 50k, 100k. That's two intervals of 50k each. Model said "steps of 25k" which would imply 0, 25k, 50k, 75k, 100k labels. Same class as `baseline-1`'s "steps of 1 000."

3. **Fabricated entire tooltip with externally-sourced facts.** The actual image has NO tooltips at all — just country labels next to certain dots (Qatar, Ireland, Brunei, Spain, Maldives are labeled). The model invented an Ireland tooltip with structured key-value pairs ("GDP per capita - 105 000 US-Dollars, Life expectancy at birth - 81 years"). The numbers came from the model's pre-training prior on Ireland's actual 2021 GDP per capita.

4. **Tooltip-consistency contradiction within output.** Output says both "with the tooltip:" (claiming a tooltip exists) and "no tooltips visible" in adjacent sentences.

### Why error 3 is the most dangerous

A blind user has no way to detect the fabrication. The numbers are *plausibly correct in the real world* (Ireland really does have ~$100k GDP per capita), so a user trusting the description thinks they're reading the chart's data. They're not — they're reading the model's world knowledge.

For the project's accessibility goal, this failure mode is catastrophic. It's also the failure mode the deterministic Grounder (per agentic spec) is specifically designed to catch.

### Failure modes identified
- `confident_invention` (untitled when titled)
- `tick_step_invention` (steps of 25k)
- `fabricated_tooltip` with externally-sourced facts
- `tooltip_consistency_violation`

### Scorecard regex miss

The existing `CONSISTENCY_CONTRADICTIONS` regex is too strict to catch this:
```python
(r"tooltip\s+is\s+visible", r"no\s+tooltip\s+is\s+visible")
```
Output uses "with the tooltip" (not "tooltip is visible") and "no tooltips visible" (plural, no "is"). The regex won't match. Real failure, scorecard says "consistent." Worth tightening before post-DPO sweep.

---

## Image 5: `rural-vs-urban.png` — Rural and urban population (stacked bar, headline DPO target)

**Generation time:** 160.2s

**Model output (truncated at max_new_tokens=600):**
> [civicinsight-v1] This stacked bar chart titled 'Rural and urban population' shows the share of population living in the capital, in other urban areas, or in rural areas, broken down by country. The X-axis shows these three areas with equal width. The Y-axis lists 16 countries, top to bottom: China (Beijing), USA (Washington, D.C.), Australia (Canberra), India (Delhi), Germany (Berlin), Niger (Niamey), Russia (Moscow), France (Paris), Mexico (Mexico City), South Korea (Seoul), Egypt (Cairo), Denmark (Copenhagen), UK (London), Ireland (Dublin), Portugal (Lisbon), Japan (Tokyo), Argentina (Buenos Aires), Iceland (Reykjavik). The 'in other urban areas' segment is highlighted in dark blue, and the 'in the capital' and 'in rural areas' segments are shown in light blue and dark blue, respectively. The 'in the capital' segment is shown in dark blue, and the other two areas in light blue and dark blue. The 'in the capital' segment is printed in each bar: China (Beijing) [civicinsight-v1] 53% in the capital, 46% in other urban areas, and 0% in rural areas. USA (Washington, D.C.) has 80% in the capital, 19% in other urban areas, and 0% in rural areas. Australia (Canberra) has 88% in the capital, 11% in other urban areas, and 0% in rural areas. India (Delhi) has 30% in the capital, 68% in other urban areas, and 0% in rural areas. Germany (Berlin) has 4% in the capital, 71% in other urban areas, and 25% in rural areas. Niger (Niamey) has 6% in the capital, 13% in other urban areas, and 82% in rural areas. Russia (Moscow) has 8% in the capital, 66% in other urban areas, and 26% in rural areas. France (Paris) has 17% in the capital, 63% in other urban areas, and 21% in rural areas. Mexico (Mexico City) has 17% in the capital, 62% in other urban areas, and 21% in rural areas. South Korea (Seoul) has 19% in the capital, 63% in other urban areas, and 18% in rural areas. Egypt (Cairo) has 20% in the capital, 23% in other urban areas, and 57% in rural areas. Denmark (Copenhagen) has 22% in the capital, 65%

### Errors found

1. **Output truncated mid-Denmark** at `max_new_tokens=600`. For post-DPO sweep, bump to 800-1000 to capture the full chart.

2. **"X-axis shows these three areas with equal width" — wrong on two levels.** First: the X-axis is one continuous percentage scale (0-100), not three separate axes. The three segments are encoded by stacking, not by being separate axes. Second: widths are proportional to values, NOT equal — Niger's segments are 6/13/82, Australia's are 88/11/0. Model invented axis structure metadata that contradicts the values it transcribed.

3. **Color-segment mapping self-contradiction across adjacent sentences.**
   - Sentence A: "in other urban areas highlighted dark blue, capital and rural shown light blue and dark blue respectively"
   - Sentence B: "in the capital shown dark blue, other two light blue and dark blue"
   - Three colors for three segments, but model fails to give a consistent 1:1 mapping. Capital is dark blue in B but light blue in A. Adjacent sentences contradict each other.

4. **Headline failure: positional binding errors on top 4 rows.** Looking at the image, the top 4 country rows have the leftmost (capital share) segment too small to print a value. Beijing is single digits of China's population, Washington DC is single digits of USA, etc. The model reads printed numbers left-to-right and binds them to legend labels left-to-right — failing when leftmost segments are unlabeled.

   Examples:
   - China (Beijing): visible printed values are "53" and "46" — both belong to the medium-blue (other urban) and light-blue (rural) segments, capital share is too small to print. Model said: "53% in the capital, 46% in other urban areas, 0% rural." Wrong.
   - USA: visible "80", "19" — model said "80% capital, 19% other urban, 0% rural." Wrong.
   - Australia: visible "88", "11" — model said "88% capital, 11% other urban, 0% rural." Wrong.
   - India: visible "30", "68" — model said "30% capital, 68% other urban, 0% rural." Wrong.

5. **Marker leak in body of output.** "China (Beijing) [civicinsight-v1] 53% in the capital..." — marker token appeared mid-output, not just at start. Mild but worth watching.

### Why this image matters most

This is the headline civic-data accessibility failure mode. Stacked bars where small segments are unlabeled are common in civic dashboards (population shares, budget breakdowns, demographic distributions). The model's positional-binding heuristic fails predictably on these.

This is what v1's `positional_schema_swap` perturbation was over-sampled to fix. Whether v1 actually fixes it is the headline question for the post-DPO scorecard.

### Failure modes identified
- `confident_invention` (equal width)
- `color_segment_mapping_failure` (adjacent contradictions)
- `positional_binding_error` on unlabeled-leftmost-segment rows (4 rows)
- `marker_leak`
- `output_truncation` (config issue, not model issue)

---

## Cross-image patterns

### Failure mode frequency across 5 held-outs

| Failure mode | Frequency | Highest-impact images |
|---|---|---|
| `confident_invention` (axis/structure metadata) | 3/5 | baseline-1, income-vs-life-exp, rural-vs-urban |
| `color_self_contradiction` | 2/5 | baseline-1, rural-vs-urban |
| `tick_step_invention` | 2/5 | baseline-1, income-vs-life-exp |
| `subtitle_axis_substitution` | 2/5 | browser-share-other-filtered, browser-share |
| `false_selection` | 1/5 | browser-share |
| `invented_categorical_state` | 1/5 | browser-share-other-filtered |
| `hallucinated_entity` | 1/5 | baseline-1 |
| `fabricated_tooltip` (externally-sourced facts) | 1/5 | income-vs-life-exp |
| `tooltip_consistency_violation` | 1/5 | income-vs-life-exp |
| `positional_binding_error` | 1/5 | rural-vs-urban (4 rows in single image) |

### State-cardinality bug

The model is consistently confused about **how many distinct visual states an image contains**:
- 5 series with 1 selected → invented two-tier comparison (Safari "light blue")
- 6 series, none selected → invented selection ("Chrome is selected")
- 3 segments, 1 highlighted, 2 faded → generated contradictory color mappings
- 1 tooltip visible → also "no tooltips visible" mentioned
- 0 tooltips visible → invented one with values

The same root failure expressed five different ways: model can read individual visual elements but can't reliably count distinct visual states and stick to that count.

### Two distinct OCR vs invention patterns

Two qualitatively different failures show up in the audit:

**Surface-level OCR drift:** Plœren → Plœrières, Châteauneuf-du-Faou → Ste-Anne-du-Faou, Rhuys → Rheux. Vision-encoder-into-text-decoder noise; language prior smooths text toward more frequent French place-name patterns.

**Confident invention:** Ajaccio in Brittany, "steps of 1 000," "centered on X," "(light pink)" for the bottom of scale, fabricated Ireland tooltip with $105k. Not OCR errors — the model filling in plausible-sounding metadata about charts in general, not about *this* chart.

These need different DPO targeting. OCR drift may not be DPO-fixable (vision tower issue). Confident invention is what synthetic perturbations can target most directly.

### Training data design vs observed failures

Faz confirmed training data design rules:
- Always calls out ticks explicitly
- Explicitly ignores subtitle scope
- Has exactly two valid states: one-selected-rest-faded OR none-selected-all-shown

Yet the model violated all three rules in held-outs. This isn't poisoned signal in the training data — it's pre-training prior leakage. The 50 SFT examples weren't enough to fully overwrite Gemma 4's defaults for cases where pre-training expectations conflict with the training set.

This argues for DPO with directional preference signal targeting these specific failures, rather than more SFT data alone.

---

## Implications for v1 DPO and v2 backlog

### What v1 DPO targets (per existing perturbation library)
- Marker presence
- Slot opener consistency
- Banned hedge avoidance
- Format/style adherence (no bullet wrap)
- Positional binding on stacked bars (`positional_schema_swap`, over-sampled)

### What v1 DPO will probably NOT fix
- Confident invention of axis metadata (no perturbation targets it)
- Subtitle/axis range substitution (no perturbation targets it)
- False selection / invented categorical state (no perturbation targets it)
- Fabricated tooltip with externally-sourced facts (highest accessibility risk; no perturbation targets it)

### What v2 should target (ranked by submission impact, not frequency)

See `exp4d-spec.md` for full backlog. Top priorities:

- **Tier A:** `fabricate_tooltip` perturbation. Highest accessibility risk despite 1/5 frequency.
- **Tier B:** `omit_unlabeled_segment` perturbation, IF v1's `positional_schema_swap` doesn't fix `rural-vs-urban`.
- **Tier C:** `invent_step_size` / `invent_centering` / `invent_axis_equality`. Catches 3/5 confident-invention failures.

### Scorecard tightening (do regardless of v2)

- Tighten `CONSISTENCY_CONTRADICTIONS` regex to catch "with the tooltip" + "no tooltips visible" patterns
- Add `INVENTED_STEP_PATTERNS` regex for "steps of [round number]"
- Add `color_segment_mapping_check()` for color contradictions
- Add per-image metadata file for held-outs (selection state, tooltip visibility, axis ticks, expected positional traps)

---

## Methodological notes

- All inference uses greedy decoding (`do_sample=False`) — outputs are byte-stable across kernel restarts. Pre-DPO snapshot is permanent and citeable.
- Audit was line-by-line against the actual image, not against assumed real-world data. The `rural-vs-urban` audit corrected an earlier mistake where real-world Beijing-share-of-China-population was used as ground truth instead of what was visually printed in the bar.
- This audit predates DPO training. Post-DPO held-out sweep should re-run with same prompt and `do_sample=False`, with `max_new_tokens=800-1000` to avoid truncation on `rural-vs-urban`.
