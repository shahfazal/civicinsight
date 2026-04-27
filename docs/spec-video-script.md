# 3-minute video script for Kaggle Gemma 4 Good Hackathon submission

**Status:** Draft v1. Three-beat structure per user direction 2026-04-27.
Beat 2's three sub-demos require specific image selections (TBD; criteria
documented below) which become final after the SFT retrain on the expanded
choropleth dataset.

**Total runtime:** 3:00 hard cap (Kaggle requirement).

**Format columns below:** TIME / VISUAL / AUDIO.

---

## Beat 1: The Problem (0:00 - 0:45)

| Time | Visual | Audio |
|---|---|---|
| 0:00 - 0:08 | Hands typing into a code editor; on-screen text fragments: `aria-label="..."`, `aria-label="..."`, `aria-label="..."` rapidly piling up. Counter ticks past 70, 80, 84. | "Last month I spent twenty hours writing eighty-four ARIA attributes by hand for one French civic dashboard." |
| 0:08 - 0:18 | Cut to AltText.ai's homepage. Drop the elections-municipales-2026 dashboard image into the upload. Output: *"Dashboard displaying tourism data..."* | "Existing alt-text tools? They give you this. Dashboard displaying. Zero numbers. Useless for a blind researcher who needs the data." |
| 0:18 - 0:30 | Side-by-side comparison cards: Power BI auto, AltText.ai, Writer.com. All say things like "Dashboard with information about France." Highlight: numbers extracted = 0%. | "Power BI's auto. AltText. Writer dot com. None of them extract a single number. None of them describe a single trend. Paid or free. Same gap." |
| 0:30 - 0:45 | Statistic on screen: 1.7 million blind French citizens. Below: "Civic dashboards published in PDF, in screenshots, in Power BI - effectively unreadable." Camera zooms slowly. | "Seventeen hundred thousand blind French citizens. Civic data is mostly published as dashboards. Right now, almost none of it is accessible." |

**Beat 1 transition** (~0:43): Blackout, then white text on black: "What if open weights could do better?"

---

## Beat 2: The Solution (0:45 - 2:30)

Three sub-demos, each ~30 seconds. Same Gradio UI throughout.

### Sub-demo A: image only - model describes correctly (0:45 - 1:25)

| Time | Visual | Audio |
|---|---|---|
| 0:45 - 0:55 | Browser opens. URL bar shows `civicinsight-web--something.modal.run`. Page loads: CivicInsight Gradio UI in light mode, shahfazal.com palette. Cursor moves to Image input. | "CivicInsight. Open weights. Open source. Runs anywhere with a GPU. Let's give it a chart." |
| 0:55 - 1:05 | Drag-and-drop the **TBD-IMAGE-A** into the dashboard upload. Gradio shows the image preview at 520px height. Cursor hovers Submit. | (silent visual beat - let the upload land) |
| 1:05 - 1:15 | Click Submit. Cold-start banner visible briefly. Output panels populate: `[civicinsight-v1] This bar chart...` with actual numbers visible. Status field reads `unverified`. | "No source data attached, so the system honestly says: unverified. The description is real. The numbers come from the image itself, not a database." |
| 1:15 - 1:25 | Highlight the marker `[civicinsight-v1]` with a subtle visual underline. Pan to the verification summary: "No source data provided. Numeric values are extracted from the image and have not been verified." | "And it tells you that, up front. No false confidence." |

**Sub-demo A image selection criteria** (TBD-IMAGE-A):
- Clean, well-formed chart (line, bar, or scatter)
- Model produces an accurate description deterministically
- No fabrications or positional bugs
- Likely candidate: `browser-share.png` (clean line chart, deterministic
  output known-good from prior smoke tests)

### Sub-demo B: image + CSV - all verified (1:25 - 2:00)

| Time | Visual | Audio |
|---|---|---|
| 1:25 - 1:35 | Same UI. Upload **TBD-IMAGE-B**. Then attach a CSV in the second upload field. CSV filename visible: `<TBD-CSV-NAME>.csv`. | "Same model. Now I attach the source data alongside. CSV. From the same public portal the chart came from." |
| 1:35 - 1:50 | Click Submit. Output populates. Status field reads `verified`. Confidence reads `100%`. Per-value verification list shows multiple `Verified: '14.6M' matches source (column 'arrivals', row 0)` style lines. | "And now the system cross-references every number in the description against the CSV. Five of five verified. Each one tied to a specific row and column." |
| 1:50 - 2:00 | Slow pan over the verification details list, each `Verified:` line briefly emphasized. | "If a screen reader reads this output, the user hears the description first, then hears: five values confirmed. They know what to trust." |

**Sub-demo B image+CSV selection criteria** (TBD-IMAGE-B + TBD-CSV-NAME):
- Image whose model description is deterministic and accurate
- CSV with columns that match the image's primary data axes
- All extracted values from the description verify at the adaptive default
  tolerance (5% scaled, 0.5% raw)
- HARD REQUIREMENT per user 2026-04-27: this pair MUST exist for the
  submission to have a wow moment. Identification criteria documented in
  `docs/spec-sft-retrain.md` (post-retrain validation step).
- Candidate: post-retrain, one of the new choropleth examples paired with
  its underlying election + DVF CSV

### Sub-demo C: image + CSV catches incorrect model output (2:00 - 2:30)

| Time | Visual | Audio |
|---|---|---|
| 2:00 - 2:10 | Different image: **TBD-IMAGE-C**. CSV uploaded same way. | "Now a harder image. The model is going to read this one. And then we'll check it." |
| 2:10 - 2:25 | Submit. Output populates. Status field reads `partial`. Confidence reads less than 100%. Verification details list mostly `Verified:` lines but at least ONE line stands out: `Unverified: '<X>' has no matching value in source data.` Highlight that line. | "Partial. Four of five verified. But this one - this number? Couldn't find it in the source data. The model invented it. The system caught it." |
| 2:25 - 2:30 | Cut to a clean text overlay: "The verification layer catches the model when it's wrong." | "That is the difference. That is what blind researchers need." |

**Sub-demo C image+CSV selection criteria** (TBD-IMAGE-C + TBD-CSV-NAME):
- Image where the deterministic model produces at least one fabricated or
  incorrect numeric value
- CSV that does NOT contain that fabricated value within tolerance
- The fabrication is a value-class number (kind=value), not an axis tick
  (which gets filtered before matching)
- Candidate: one of the new dual-encoded choropleths post-retrain, IF the
  retrain leaves a known fabrication mode unfixed. If retrain fixes
  everything, fall back to a held-out where positional binding still
  produces a confident-invention failure (e.g., rural-vs-urban stacked bar
  per the pre-DPO audit).

---

## Beat 3: The Vision (2:30 - 3:00)

| Time | Visual | Audio |
|---|---|---|
| 2:30 - 2:38 | Cut to GitHub repo page: github.com/shahfazal/civicinsight. License badge: MIT. Star count visible if any. | "It is open source. MIT. Build on it. Fork it. Improve it." |
| 2:38 - 2:46 | Cut to HuggingFace Hub: huggingface.co/shahfazal/civicinsight-gemma4-e4b-it. Apache 2.0 license badge. Download button visible. | "The model is on HuggingFace. Free. Open weights. Apache two." |
| 2:46 - 2:54 | Three icons stack: terminal, cloud (Modal), HF Spaces. Text: "Run anywhere. No API keys. No subscriptions." | "Run it on your laptop with a GPU. Run it on Modal. Run it on HuggingFace Spaces. No API key. No subscription. No paywall." |
| 2:54 - 3:00 | Final card: "CivicInsight. Built on Gemma 4 by Google DeepMind. Released under MIT." Below: "github.com/shahfazal/civicinsight" Below that: small text "Submission for the Kaggle Gemma 4 Good Hackathon, May 2026". | "This is what Digital Equity looks like." |

**Beat 3 close:** Hard cut to black at 3:00.

---

## Production notes

- **Voiceover style:** measured, clear, no rushed pace. The 3:00 cap is
  tight; the script above is timed assuming ~150 words per minute.
- **No music.** Or, if any, very subtle ambient pad. The voiceover and the
  on-screen text do the work.
- **Captions.** Burned-in captions for the entire video for accessibility
  parity with the message. Match Hugo PaperMod typography (system font,
  high contrast).
- **Recording the demos:** all three sub-demos use the live Modal-deployed
  Gradio at the public URL. Pre-warm the container before recording (one
  throwaway call ~5 min before, so the cold-start banner isn't visible
  during the recording itself). If recording on a day with `keep_warm=1`
  set in the demo deployment, no pre-warm needed.
- **Take order:** record Beat 2 first (most complex, longest, most
  variable). Beats 1 and 3 are simpler cuts and can be re-recorded if Beat
  2 changes.
- **Fallback if the deployed demo fails on recording day:** record against
  the local Gradio (`python -m app.io.demo`) which calls the same Modal
  inference backend. Visual difference is negligible.

## Open items (resolve before recording)

1. **Image-A selection** (sub-demo A) - decide based on which held-out
   produces the cleanest deterministic description with marker preserved.
2. **Image-B + CSV-B pair** (sub-demo B) - the must-have happy path. This
   is the most expensive open item; depends on retrain outcome and
   post-retrain validation.
3. **Image-C + CSV-C pair** (sub-demo C) - depends on retrain outcome.
4. **Demo URL** at recording time. Either:
   - `civicinsight-web--shahfazal.modal.run` (Modal default URL),
     auth-gated until May 13, public after.
   - Custom domain if set up.
5. **Cold start UX during recording.** Either pre-warm or `keep_warm=1`
   for the recording window (May 13-15). Cost: ~$60/day for keep_warm.
6. **Captions/transcripts.** Burned-in vs CC track. Burned-in is more
   accessible (always visible) but harder to edit if voiceover changes.
7. **Recording tools.** Screen recording software (QuickTime / OBS /
   Loom). Mic. Quiet room.

## Acceptance gate before recording

- [ ] Beat 2 image+CSV pairs confirmed working end-to-end on the deployed
      Modal endpoint (3 dry runs each, all hitting expected status)
- [ ] Public URL gating set per recording-day plan (auth or open)
- [ ] Voiceover script timed against a stopwatch under 3:00 with the
      stipulated pacing
- [ ] Captions exist and match the voiceover word-for-word
