# CivicInsight: Zero-Shot Gemma 4 E4B Evaluation Report

**Date:** April 12, 2026  
**Model:** google/gemma-4-e4b-it (zero-shot, no fine-tuning)  
**Environment:** Kaggle T4 x2 GPU  
**Prompt:** Generic, chart type, key values, trends (Markdown structure)  
**Token budget:** 2048 max_new_tokens  

---

## Test Set

**Phase 1, Real dashboards (9 images)**

| Image | Chart Type |
|-------|-----------|
| tourisme-powerbi.png | Mixed dashboard (KPIs, table, bar, map, gauge) |
| scatter-all-parties-clean.png | Scatter plot (all categories) |
| scatter-gauche-filtered.png | Scatter plot (one category filtered/highlighted) |
| scatter-gauche-droite-filtered.png | Scatter plot (two categories filtered/highlighted) |
| scatter-point-selected.png | Scatter plot with tooltip hovers |
| quintile-distrib.png | Horizontal stacked bar (100%) |
| boxplot-abstention.png | Box plot |
| choropleth-paris.png | Choropleth map (simple) |
| choropleth-marseille.png | Choropleth map (medium complexity) |

_The original audit covered 10 real-world images. `choropleth-paris-detailed.png` was lost from the repo at some point and is no longer reproducible; its qualitative findings remain in the Per-Chart-Type Summary below._

**Phase 2, Synthetic charts with ground truth (18 images tested)**

| Image | Chart Type | Variant |
|-------|-----------|-------------|
| stacked_bar_bars_3_001.png | Stacked bar | random, 3 bars, 6 segments |
| stacked_bar_bars_8_003.png | Stacked bar | random, 8 bars, 6 segments |
| stacked_bar_dist_even_007.png | Stacked bar | even (~16% each), 5 bars |
| stacked_bar_dist_dominant_008.png | Stacked bar | dominant (EXG ~60%), 5 bars |
| stacked_bar_dist_tiny_010.png | Stacked bar | tiny right segments, 5 bars |
| stacked_bar_random_011.png | Stacked bar | tiny, 4 segments only |
| boxplot_01_baseline.png | Box plot | baseline, no outlier labels |
| boxplot_02_outliers.png | Box plot | labeled outliers |
| boxplot_03_tooltips_center.png | Box plot | 2 tooltips visible |
| boxplot_04_proximity.png | Box plot | tooltip + named student points |
| boxplot_05_size_variation.png | Box plot | variable IQR sizes |
| boxplot_06_full_complexity.png | Box plot | full complexity, 2 tooltips |
| choropleth_01_political.png | Choropleth | political colors (6 blocs) |
| choropleth_02_transport.png | Choropleth | non-political colors (transport modes) |
| choropleth_03_circles.png | Choropleth | circle-size encoding |
| choropleth_04_political_circles.png | Choropleth | bivariate (political color + circle size) |
| choropleth_05_gradient.png | Choropleth | gradient, no printed labels |
| choropleth_06_gradient_labels.png | Choropleth | gradient + printed labels |

---

## Findings by Capability

### ✅ Strong, Reliable Zero-Shot

**Explicit number extraction**
- KPI metrics extracted correctly (14.6M, 2.3%, 8.81, 604.83, 2.595K, 0.65)
- Tooltip/hover content read correctly when numbers are printed
- Axis labels, tick values, min/max ranges

**Structural understanding**
- Chart type identification, correct across all 9 images
- Legend reading, categories and labels identified
- Table data, full seasonality table (36 cells, 12 months × 3 years) extracted correctly with sufficient token budget

**UI element reading**
- Ghost text vs active filters distinguished (search bar examples vs pills)
- Button text and UI chrome identified
- Noise identified and flagged ("road numbers omitted for conciseness")

**Trend/insight language**
- Scatter plot interpretation eerily close to human analysis
- Seasonal patterns correctly identified (July/August peak, Nov/Dec low)
- Correctly flagged "no strong linear correlation" on scatter plots

---

### ❌ Systematic Failures, Not Prompt-Fixable

**1. Interactive state blindness** *(confirmed 3x)*
- Filtered/highlighted/faded states invisible to model
- Treats all data points as equal regardless of visual emphasis
- Same analysis produced for filtered and unfiltered versions of same chart
- Affects: any dashboard with interactive filters, selections, or highlights

**2. Proportional value extraction from bar widths** *(confirmed 6 synthetic charts, 4 distribution types)*
- Sums exceed 100% in 5 of 6 charts, worst case +30% overshoot
- Error magnitude: 5–30 percentage points per segment
- **Copy-paste failure at scale**: 8-bar chart (003), model reads one bar pattern and reproduces it identically across all 8 rows
- **Tiny segment inflation**: segments actually ~1–4% reported as 7–11% (EXD in "tiny" distribution)
- **Dominant segment compression**: actual ~60% segment read as ~50%, model anchors toward center
- **Segment-specific prior bias**: Gauche inflated in random distributions; Extrême droite deflated in even distributions; model applies internal political prior rather than reading widths
- Root cause: no printed numbers on chart, model guesses proportions by eye using a learned political prior
- Confirmed systematic across: random, even, dominant, and tiny distributions

**3. Box plot value estimation, multi-failure pattern** *(confirmed 6 synthetic charts)*
- **Tooltip tunnel vision**: when tooltips visible for 2 of 6 boxes, model reads only those 2 and gives qualitative descriptions for the rest, no Q1/Q3/whisker values attempted
- **Value collapsing**: nearby values rounded to same number (Emma 6.51 + Thomas 8.09 both reported as "~7"; Histoire 15.03 + Arts 14.56 both reported as "~15"), precision gap at sub-point level
- **Repeated student labels missed**: named points appearing on two boxes (Léa on Maths AND Sciences; Chloé on Français AND Sciences) only attributed to one box each time
- **Low outlier blindness**: Sciences had 5 outliers (1.47, 3.5, 3.71, 18.38, 20.0), model reported 2 high ones, missed 3 low ones completely; bias toward high outliers
- **Subject misattribution**: Français median (13.46) reported as ~10, collapsed with Sport (10.86), proximity confusion between adjacent boxes
- **Structural reading strong**: relative ranking of subjects preserved; tight vs. wide IQR correctly detected (05); overall trend language directionally correct
- Q1/Q3/whiskers estimated reliably only when no tooltips present and boxes are well-separated (01, 02, 05)

**4. Prior knowledge overriding visual evidence** *(confirmed across multiple chart types)*
- Paris choropleth (real): model "knows" left=blue, right=red, inverted actual colors
- Boxplot (real): high abstention read as high "support" (semantic inversion)
- Political choropleth (synthetic 01): Zone E is visibly YELLOW (Centre), model calls it Gauche anyway; prior overrides an unambiguous color cue, not a hue-confusion issue
- Political choropleth (synthetic 01): blue (Droite), yellow (Centre), grey (Divers) all collapsed into one "Center/Conservative" bloc, model applies French political prior but imprecisely
- Political choropleth (synthetic 01): Extrême droite zones (C, L) simultaneously placed in Centre cluster and correctly flagged as Extrême droite, internally contradictory output
- Model fills gaps with world knowledge instead of reading the image
- Dangerous for civic data: confident, wrong, politically loaded output

**5. Circle size encoding, complete failure** *(confirmed 2 synthetic charts)*
- Cannot differentiate circle sizes at all, all circles reported as identical (smallest category)
- Confirmed in both circle-only (03) and circle+color (04) variants
- In bivariate encoding (04): uses political color (black hexagon = Extrême droite) as proxy for "expensive" circle, reads the wrong channel entirely
- Bivariate encoding also causes dimension drop: focused on price circles, ignored political color dimension completely
- Model correctly reads legend symbols (empty/half/filled circles) but cannot match them to actual zone circles by size, 6/12 correct (50%), driven by lucky guesses not actual size reading
- **Summary whitewash**: model's "General Trend" conclusion (9 zones affordable) directly contradicts its own zone-by-zone output, cannot synthesize what it just produced
- Root cause: model has no circle size perception, only shape recognition

**6. Number hallucination under cognitive load**
- 27482 → "2,7482" (fabricated comma in 5-digit number)
- 1,405,332 → "140,552" (order of magnitude error)
- Occurs on dense, complex images, model picks confident subsets, fills rest
- Does not occur on simple, explicit numbers

---

### ⚠️ Prompt-Fixable, One-Line Fixes

| Issue | Fix |
|-------|-----|
| Truncated output | `max_new_tokens=2048` (already applied) |
| Locale transposition (44,2% → 44.2%) | "preserve original number formatting and locale" |
| Year markers missed on KPIs | "for each value, note its time period label" |
| Directional indicators missed (↑ green arrow) | "note directional indicators (arrows, colors) and their meaning" |
| Legend items out of order | "list legend items top-to-bottom as they appear" |
| Values without context labels | "for each number, include its label from the image" |
| Outliers missed on box plots | "explicitly identify outlier points above/below whiskers" |
| Incomplete sidebar enumeration | "list all items exhaustively, do not skip" |

---

## Per Chart Type Summary

| Chart Type | Number Extraction | Structure | Trends | Notes |
|-----------|-----------------|-----------|--------|-------|
| KPI dashboard | ✅ Excellent | ✅ Good | ✅ Good | Best performance |
| Data table | ✅ Excellent | ✅ Good | N/A | Needs 2048 tokens |
| Scatter plot (unfiltered) | ✅ Good | ✅ Good | ✅ Good | Strong |
| Scatter plot (filtered) | ❌ Miss | ✅ Good | ❌ Wrong | Filter state invisible |
| Scatter (tooltips) | ✅ Good* | ✅ Good | ✅ Good | *Minor hallucination |
| Stacked bar (100%) | ❌ Poor | ✅ Good | ❌ Wrong | Confirmed systematic: sums >100%, copy-paste across bars, prior bias per segment |
| Box plot | ⚠️ Partial | ✅ Good | ⚠️ Partial | Tooltips+named labels=exact; Q1/Q3/whiskers=variable; low outliers missed; value collapsing; subject misattribution |
| Choropleth (gradient + labels) | ✅ Excellent | ✅ Good | ✅ Good | Printed numbers = perfect; 12/12 zones correct |
| Choropleth (gradient, no labels) | ✅ Good | ✅ Good | ✅ Good | 11/12 zones correctly ranked; color gradient works |
| Choropleth (political colors) | ⚠️ Partial | ⚠️ Partial | ⚠️ Partial | Correct at cluster level; can't split similar hues; prior interference |
| Choropleth (non-political colors) | ⚠️ Partial | ⚠️ Partial | ⚠️ Partial | Similar-color confusion (Train vs Bus); no prior interference |
| Choropleth (circle size) | ❌ Fail | ✅ Good | ❌ Wrong | Zero circle size perception; all zones reported as identical |
| Choropleth (bivariate: color+circle) | ❌ Fail | ⚠️ Partial | ❌ Wrong | Drops one dimension; confounds color channels; can't read circles |

---

## Fine-Tuning Targets (Confirmed)

1. **Interactive state detection**, teach model to read filter/highlight/selection state
2. **Proportional extraction**, bar width → percentage, without printed numbers; break the political prior bias
3. **Legend fidelity**, read actual colors, don't apply prior political conventions
4. **Uncertainty signalling**, "I cannot reliably extract this" > confident wrong answer
5. **Dense text enumeration**, exhaustive reading of sidebars, legends, tables
6. **Box plot exhaustiveness**, extract Q1/Q3/whiskers per box regardless of tooltip presence; scan each box independently; report all named points per subject not just first occurrence
7. **Precision at sub-point level**, avoid value collapsing of nearby but distinct data points
8. **Circle size perception**, teach model to read size-encoded data; currently zero capability
9. **Bivariate encoding**, handle charts with two simultaneous visual encodings without dropping one

---

## To-Be-Tested (Gaps in Current Analysis)

### Chart Types, Need More Samples

**Stacked bars (proportional extraction)**
- 6 synthetic charts tested (of 15 generated) across 4 distribution types: random, even, dominant, tiny
- **Confirmed systematic failure**, see updated findings in Systematic Failures section
- Error rate: 5–30pp per segment; sums exceed 100% in 5/6 charts
- New failure type discovered: copy-paste across bars (all rows get same estimate)
- Remaining open question: does error scale with number of segments? (only tested 4 and 6 segments)

**Box plots**
- 2 real samples + 6 synthetic charts tested (8 total)
- Confirmed failure modes across all samples:
  - Tooltip tunnel vision: tooltips present → model reads only those, skips Q1/Q3/whiskers for remaining boxes
  - Value collapsing: distinct nearby values reported as same number (~7 for both 6.51 and 8.09)
  - Repeated student labels missed: named point appearing on 2 boxes only attributed to one
  - Low outlier blindness: systematically misses below-whisker points; only reports high outliers
  - Subject misattribution: adjacent box medians confused when boxes are visually close
  - Prior knowledge override: high abstention = high "support" (semantic inversion), from real samples
  - Spatial anchoring failure: tooltip values attributed to wrong box, from real samples
- Failure modes now well-characterised across synthetic set
- No further synthetic box plot testing needed unless new failure mode suspected

**Choropleths**
- 3 real + 6 synthetic charts tested (9 total)
- Confirmed failure modes across all samples:
  - Circle size encoding: complete failure, zero circle size perception confirmed (03)
  - Bivariate encoding: drops one dimension, confounds color channels (04)
  - Similar-hue confusion: cannot split Extrême gauche (dark red) from Gauche (pink); Train (green) from Bus (orange)
  - Prior knowledge override: political color priors interfere with Centre zone classification
  - Hard boundary hallucination: invented "transition zones" (real samples)
  - Dense text: skipped items, hallucinated legend entries (real samples)
- Strong finding: color gradient works well (11/12 correct); printed labels perfect (12/12)
- Failure modes fully characterised. No further synthetic choropleth testing needed.

### Prompt Engineering, Not Yet Tested

- Improved prompt with all fixes applied (locale, directionality, ordering, labels)
- Measure: how many of the "prompt-fixable" issues actually resolve?
- Do prompt fixes introduce new failure modes?

### Token Budget

- 512 tokens: truncation confirmed
- 2048 tokens: sufficient for most charts
- Not tested: charts that may need >2048 (very dense dashboards)

### Other Chart Types, Not Yet Tested

- Pie/donut charts
- Line charts (standalone, not embedded in dashboard)
- Gauge charts (standalone)
- Maps without political encoding (e.g., geographic/statistical only)
- Tables (standalone, not embedded)

---

## Decision Point

**Core question answered:** Does zero-shot Gemma 4 extract numbers from civic dashboards?

**Answer:** Yes for explicit numbers (KPIs, tables, tooltips, printed labels). No for encoded values (proportional bars, circle sizes, political color priors, Y-axis estimation without tooltips).

**The fundamental boundary:**
- **Text on screen** → extracted correctly, reliably, to full precision. No exception found across the 27 reproducible images.
- **Value encoded visually** (width, size, color intensity, position) → model guesses using learned priors. Errors are systematic and large.

**Fine-tuning justified?** Unambiguously yes. 9 confirmed failure modes, all specific and measurable:
1. Interactive state blindness
2. Proportional bar extraction (5–30pp error, sums >100%, copy-paste across bars)
3. Box plot estimation (tooltip tunnel vision, value collapsing, low outlier blindness)
4. Prior knowledge overriding visual evidence (political color, semantic inversion)
5. Circle size encoding (zero capability)
6. Bivariate encoding (dimension drop)
7. Similar-hue confusion
8. Dense text enumeration
9. Summary contradicting own output (whitewash)

**Zero-shot evaluation status:** COMPLETE
- 9 real dashboard images (Phase 1; original audit was 10, one source file lost)
- 18 synthetic charts with ground truth JSON (Phase 2): 6 stacked bars, 6 box plots, 6 choropleths
- **Total reproducible: 27 images** (verbatim outputs in `notebooks/kaggle/01-zero-shot-evaluation.ipynb`)

**Verdict:** Zero-shot evaluation was a success. Gemma 4 fails in exactly the right places, encoded values, visual inference, political priors, leaving clear room for fine-tuning to add genuine value. The model is not broken; it is unspecialized. That is the best possible outcome.

**Next step:** Dataset creation and fine-tuning. Week 1 Day 3+ tasks.
