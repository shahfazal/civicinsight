# Demo examples spec

Working catalog of test cases verified against the live `feat/modal-hf-logistics`
+ `fix/csv-modal-fixes` branches as of May 2, 2026. Each case shows a different
property of the system: clean output, model failure caught by grounding,
pipeline conservatism on correct outputs, robustness to non-viz inputs.

Use this during video recording and live demos to know what to expect, what
talking point each case supports, and what to watch out for (cold-start
timing, screen reader test, etc.).

---

## Order of demonstration (recommended)

1. **Case A, Sillon Lorrain choropleth, image only** (baseline: model works)
2. **Case B, Corsica EV chargers + CSV** (model right, pipeline conservative, honest)
3. **Case C, rural-vs-urban + CSV** (model wrong, pipeline catches it, value of verification)
4. **Case D, income-vs-life-exp + CSV** (worst documented failure mode, pipeline still catches it)
5. **Case E (optional), steering wheel image** (robustness: not-a-viz handled gracefully)

Rationale: A → B builds confidence the system works on simple cases. C → D
introduces the verification story increasingly dramatically. E is a closer that
shows the system has limits and is honest about them.

For a 3-minute video, A + C + D + E is probably enough. B is for the longer
writeup or live walkthrough.

---

## Case A, Sillon Lorrain choropleth (image only)

**Inputs:**
- Image: any electoral choropleth (e.g., baseline-1 or yvelines from the held-outs)
- CSV: none

**Expected ARIA output:**

> [civicinsight-v1] This choropleth map titled 'Sillon Lorrain' shows communes
> colored by the winning political bloc. The legend on the bottom right shows:
> Bloc vainqueur - Dark Red square for Extrême gauche, Pink square for Gauche,
> Yellow square for Centre, Gray square for Divers, Blue square for Droite and
> Black square for Extrême droite. 12 communes are shown colored: Gauche
> (Pink) - 2, Centre (Yellow) - 3, Divers (Gray) - 3 and Droite (Blue) - 4.

**Expected status / confidence:**
- Data Status: `unverified`
- Confidence: `Not applicable (no source data provided)`
- Verification Summary: standard "no source data" message
- Per-value Verification: `No per-value details.`
- Structural Issues: `None`

**What this demonstrates:**
- Model produces a coherent, structured ARIA description with marker prefix,
  slot opener, field-by-field description
- Without CSV, the system honestly reports "unverified" rather than guessing
- Output is screen-reader-ready: prose only, no bullet symbols, conversational tone

**Recording tip:** First request after a quiet period is a cold start (~60-90s
on the inference container). Either warm the container before recording or
edit out the wait.

---

## Case B, Corsica EV chargers (image + CSV)

**Inputs:**
- Image: `examples/standardized/corse-ev-deuteranopia.png` (or whichever Corsica
  EV image is available, check examples/ for current name)
- CSV: `examples/raw/corse-ev-charging-ground-truth.csv`

**Expected ARIA output (mostly correct):**

> [civicinsight-v1] This choropleth map titled 'Données Chargeurs Électrique'
> shows the distribution of electric vehicle chargers across communes in
> Corsica, France. The color scale ranges from 0 (light green/teal) to 47
> (dark blue), indicating the number of chargers per commune. Ajaccio is
> marked in dark blue at the top of the 0-47 scale. Bastia is also shown in
> dark blue, near the top of the scale. Corte is currently selected with a
> tooltip showing 9 chargers. ...

**Expected status / confidence:**
- Data Status: `unverified`
- Confidence: `0%`
- Verification Summary: `0 of 5 numeric values verified against source data.
  2 ambiguous (multiple matches). 3 unverified (no matching source value).`
- Per-value Verification:
  - `Unverified: '47'. A numeric match exists ... but its row does not contain
    any of the entities mentioned ...`
  - `Ambiguous: '0' could match 13 cells. ... no context overlap with any
    candidate.`
  - `Unverified: '9'. ... value may be a fabrication coinciding with an
    unrelated row.`

**Ground truth from CSV:**
- Ajaccio = 47 (model correct)
- Corte = 9 (model correct, including tooltip)
- Bastia = 38 (second highest, "near top of scale")

**What this demonstrates:**
- Model output is **substantively correct** on a CivicInsight-domain image
- Pipeline reports `unverified` / 0% because the matcher's context-window
  heuristic can't programmatically confirm the entity-to-value mappings
  (entity labels and numbers are separated across sentence boundaries)
- This is the system's **conservative bias**: prefer false negatives over
  false positives. An accessibility user gets "I can't verify" rather than
  "verified but actually wrong"

**Talking point:**
> "Even when the model is correct, the verification layer doesn't claim
> certainty without evidence. For accessibility tooling, an honest 'I can't
> verify' is safer than a confident-but-wrong claim. The user knows to check
> the source data."

**Recording tip:** This is the case that makes the system look "too pessimistic"
at a glance. Frame it carefully, emphasize the design choice, not the
limitation.

---

## Case C, rural-vs-urban stacked bar (image + CSV)

**Inputs:**
- Image: `examples/standardized/rural-vs-urban.png`
- CSV: `examples/raw/dw-population-ground-truth.csv`

**Expected ARIA output (model has documented positional binding error):**

> [civicinsight-v1] This stacked bar chart titled 'Rural and urban population'
> shows the share of the population living in three areas: the capital, in
> other urban areas, and in rural areas, for 24 countries. ... The US bar is
> currently selected and is highlighted in dark blue. The three segments of
> the US bar show: capital - 80%, other urban areas - 0%, and rural areas - 19%.
> ...

**Expected status / confidence:**
- Data Status: `partial`
- Confidence: `~17%`
- Verification Summary: `1 of 6 numeric values verified against source data.
  5 unverified (no matching source value).`
- Per-value Verification: most values flagged unmatched; possibly one
  coincidental "Verified" match on a count-shaped number ('23')

**Ground truth from CSV:**
- USA: capital=1.54%, other urban=79.9%, rural=18.6%
- Model: claimed capital=80%, other=0%, rural=19% → **labels reversed**
- 80% is actually the "other urban" segment value, not capital
- Image actually has 18 countries, not 24 as model claimed

**What this demonstrates:**
- Documented exp4c-sft failure mode: positional binding error on stacked bars
- This was a **DPO target** in the v1 plan (deferred to v2)
- Pipeline correctly flags 5 of 6 numeric values as unverified
- 17% confidence appropriately signals "do not trust this output without
  source verification"

**Talking point:**
> "The model confidently produced 80% / 0% / 19%, labels swapped. Without
> the CSV, a screen-reader user would have no way to know this is wrong.
> With the CSV, the pipeline flags it. 17% confidence is the system telling
> the user: don't trust these specific numbers."

**Heads up:** the '23' false-positive verified match is documented in the
model card as a known limitation, coincidental matches with overlapping
context. If a viewer asks "why is one number verified?", that's the answer.

---

## Case D, income vs life expectancy scatter (image + CSV)

**Inputs:**
- Image: `examples/standardized/income-vs-life-exp.png`
- CSV: `examples/raw/dw-life-expectancy.csv`

**Expected ARIA output (worst documented failure mode):**

> [civicinsight-v1] This untitled scatter plot shows GDP per capita against
> life expectancy, with the 'Country' point tooltip visible. The X-axis
> shows 'GDP per capita' from 50 000 to 100 000 in steps of 5 000. The Y-axis
> shows 'Life expectancy at birth' from 0 to 100 in steps of 25. The country
> Qatar is selected, showing a tooltip with: 'Qatar', 'GDP per capita' at
> 75 000, and 'Life expectancy at birth' at 78 years. ...

**Expected status / confidence:**
- Data Status: `partial`
- Confidence: `~14%`
- Verification Summary: `1 of 7 numeric values verified ... 1 ambiguous ...
  5 unverified ...`

**Ground truth from CSV (Qatar row):**
- GDP per capita: **92,862** (model said 75,000, wrong)
- Life expectancy: **79.3** (model said 78, close, might match within tolerance)
- Image actually titled "Income vs life expectancy" (model said "untitled")
- X-axis is Life expectancy (50–85), Y-axis is GDP per capita (0–100k)
 , **model swapped them**

**What this demonstrates:**
- Two compounding failure modes: title fabrication (model says "untitled")
  and axis swap
- Tooltip values fabricated (Qatar's real values are very different)
- Pipeline catches all numeric fabrications
- 14% confidence appropriately low

**Talking point:**
> "The model invented the title, swapped the axes, and made up Qatar's
> tooltip values. Without verification, this output reads as confident and
> precise, exactly the kind of accessibility failure that's invisible to
> sighted developers because the prose feels professional. The verification
> layer's confidence score makes the unreliability measurable."

**Notable:** this is the strongest case for the verification-layer-as-safety-net
narrative. If you only have time for one image+CSV demo, use this one.

---

## Case E (optional), Steering wheel image (not a viz)

**Inputs:**
- Image: any non-data-visualization image (we used a "Nobody Tests The
  Steering Wheel" meme, anything that's not a chart works)
- CSV: any CSV (or none, both behave reasonably)

**Expected ARIA output:**

> [civicinsight-v1] This circular diagram titled 'Steering Wheel' shows a
> wireframe of a steering wheel. The rim of the wheel is shown in light blue,
> and the inner hub is marked with a dark blue circle. ...

**Expected status / confidence:**
- Data Status: `unverified`
- Confidence: `Not applicable (no source data provided)` or `0%` if CSV provided
- Structural Issues: `no numeric values present` (caught by validator)

**What this demonstrates:**
- Model recognizes the image is not a typical chart and uses novel
  descriptors ("circular diagram") rather than force-fitting a chart type
- Model doesn't fabricate numeric data even though the prompt is "describe
  this data visualization"
- Structural validator correctly flags the absence of numeric content

**Talking point:**
> "Even when given an image that isn't a data visualization at all, the
> model produces an honest visual description without inventing values.
> The structural validator confirms the absence of data, and the system
> correctly reports there's nothing to verify."

**Use this case if:** you want to address the inevitable judge question
"what happens when the input isn't actually civic data?" Otherwise skip
for time.

---

## Setup checklist before recording

1. **Warm the inference container.** Submit one request 5 min before recording
   so the container is hot. Without this, your first demo case eats a 60-90s
   cold start.

2. **Verify Modal app state:**
   - DEMO_PUBLIC=1 if recording without auth challenge (or stay auth-gated and
     edit the password prompt out)
   - DEMO_HOT=1 in deploy env if expecting concurrent demos

3. **Have screenshots ready** for each case in case the live demo fails. Tab
   through them as fallback.

4. **Test each case end-to-end the day before** to catch deploy regressions.

5. **Browser:** Chrome/Firefox in incognito mode. Standard zoom (no zoom-in
   for "presentation mode", Gradio's layout breaks at high zoom).

6. **Recording resolution:** 1920×1080 minimum. Show full Gradio output panel
   so per-value verification is readable.

---

## What to NOT show in a 3-min video

- Modal logs (interesting to engineers, dead-air to general audience)
- HuggingFace Hub model card (link to it; don't read it on camera)
- The agentic shell's Python source (too much detail, kaggle notebook
  walks through it)
- Cold-start timing (warm everything first)
- The 72-missing-keys warning (architectural quirk, not user-facing)

---

## Failure modes to prepare for during live demo

| Symptom | Likely cause | Recovery |
|---|---|---|
| 60-120s blank wait | Cold start | "First request loads model from disk; ~30-90s. Subsequent are fast." |
| 500 / Connection error | Container crash | Hard refresh, retry. If persistent, fall back to recorded screenshots. |
| File upload doesn't appear in form | Browser cache or upload progress 404 | Hard refresh, re-upload. |
| Submit hangs >2 min | Inference timeout fired | Don't retry on camera; fall back to screenshot. Investigate after. |
| Output completely incoherent | Model is loading wrong adapter | Check Modal logs, redeploy `app/io/inference.py`. |
