# Video Submission Pipeline — CivicInsight Hackathon Demo

**Target deliverable:** 3-minute YouTube video for Kaggle Gemma 4 Good Hackathon submission
**Track targets:** Main + Digital Equity & Inclusivity + Unsloth Special Tech

The video production pipeline is open-source end to end: open-weights TTS for
the voice-over, open-source screen capture, and free desktop assembly. No
proprietary services in the loop. Reproducibility for anyone wanting to do a
similar walkthrough video for a model release.

---

## Tooling decisions (locked)

| Component        | Choice                                      | Rationale                                                                                                                  |
| ---------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Voice-over       | Kokoro TTS (`hexgrad/Kokoro-82M`)           | Apache 2.0 license, ~82M params, runs on CPU, aligns with the project's open-source narrative.                              |
| Screen recording | Cap (cap.so, free, open-source)             | Open-source aligns with project ethos. Auto cursor-zoom applied in Cap's editor post-processing.                           |
| Final assembly   | iMovie (free, pre-installed on Mac)         | Cap can't import external WAV — export Cap clips as MP4, assemble + sync `voiceover_full.wav` in iMovie.                   |
| Hosting          | YouTube (public, no login)                  | Required by Kaggle submission rules                                                                                        |
| Backup TTS       | ElevenLabs free tier                        | If Kokoro quality insufficient on key moments                                                                              |

---

## Pipeline overview

```
1. Generate VO audio (Kokoro)        ~15 min
2. Stage demo states in Modal app    ~30 min
3. Record screen demos (no audio)    ~60 min
4. Edit video + sync audio           ~90 min
5. Add title card + end card         ~30 min
6. Export + review                   ~15 min
7. Upload to YouTube                 ~10 min

Total: ~4 hours
```

---

## Part 1: Voice-over (2:47.0 measured audio)

### Full script with timing markers

The script is structured in **13 numbered chunks (0-12)** for clean Kokoro generation. Between chunk 1 and chunk 2 in iMovie, drop the captured VoiceOver clip ("Please use the arrow keys to pan the chart, region") onto the timeline so it plays after Echo says "VoiceOver reads the chart as:" and before "That's it." Allow ~4s for the VO clip insert.

Timing markers below are the **video-timeline positions** (audio chunk + 0.5s inter-chunk pause + ~4s VO clip between 1 and 2).

```
[CHUNK 0 — 0:00-0:08, ~22 words]  (TITLE CARD intro HTML)
Welcome to CivicInsight — an open-source vision-language model
that makes civic data dashboards more readily accessible to screen reader users.

[CHUNK 1 — 0:09-0:18, ~28 words]
Civic data is meant to inform public decision-making.
This is a New York City Open Data dashboard showing For-Hire Vehicle volume.
VoiceOver reads the chart as:

[VO CLIP — 0:18-0:22, ~4s — captured system audio from the bug recording]
"Please use the arrow keys to pan the chart, region"

[CHUNK 2 — 0:23-0:34, ~33 words; explicit 0.3s pause after "That's it."]
That's it. Big players like Power B I and Tableau invest in accessibility,
but not all dashboards surface the actual values, peaks, lows,
or anything else about what the data is saying.

[CHUNK 3 — 0:35-0:46, ~28 words]
I hit this wall myself making my own civic visualization accessible.
Generic alt-text tools help, but on civic dashboards specifically
the outputs tend to be sparse, inconsistent, or behind paywalls.

[CHUNK 4 — 0:47-0:57, ~25 words]
Frontier-model APIs work well, but they require ongoing API spend
and send dashboard data to third parties —
not always acceptable for civic or public-sector use.

[CHUNK 5 — 0:58-1:07, ~20 words]  (HF model card walkthrough)
CivicInsight is a different approach.
A fine-tuned Gemma 4 model paired with deterministic verification.
MIT-licensed, runs locally, no third-party calls.

[CHUNK 6 — 1:08-1:23, ~40 words]
Here's the model on a simulated French electric vehicle charger dashboard.
I upload the image. The fine-tuned model produces an ARIA description —
chart type, color scale, the selected commune, the tooltip value.
It correctly identifies Corté as selected, with 9 chargers.

[CHUNK 7 — 1:24-1:35, ~26 words]
Same image, different selection state.
This time Porto-Vecchio is selected, showing 14 chargers.
The model genuinely reads what's actually in the image —
not pattern-matching, not memorizing.

[CHUNK 8 — 1:35-1:49, ~41 words]
Now a richer case.
Global C O 2 emissions by fuel type, sourced from Our World In Data.
The model produces a clean description — chart title, axes,
the selected Coal line, the tooltip showing eight thousand three hundred thirty-six
megatonnes in nineteen eighty-six.

[CHUNK 9 — 1:50-2:08, ~51 words]
Without source data, every number is just trust the model.
With the CSV attached, the verification layer cross-references each value.
Eight thousand three hundred thirty-six matches the source — verified.
The axis bounds and series count have no match — flagged unverified.
Twenty-five percent confidence, partial status.
The user knows what to trust.

[CHUNK 10 — 2:09-2:26, ~53 words; ellipses preserve prosody on the triplet]
What about an image that isn't civic data at all?
A cheetah portrait, with the same prompt.
The model doesn't refuse. It doesn't hallucinate chart structure.
Format conventions hold... marker... slot... prose voice...
all transferred from 61 training examples.
Base vision capability stays intact. This is what fine-tuning at small scale should do.

[CHUNK 11 — 2:27-2:41, ~36 words]  (closing montage)
The whole stack is open.
The model is on HuggingFace, MIT-licensed.
The code will be on GitHub by submission, also MIT-licensed.
A live demo runs on Modal during judging.
You can also run inference locally — no API keys, no third-party calls.

[CHUNK 12 — 2:42-2:52, ~30 words]
Civic data deserves to be accessible to everyone.
CivicInsight is one piece of that —
honest about what it can and can't do,
pairable with verification when the source data exists.

[END CARD — 2:52-3:00, ~8s]  (end-card.html)
[silence — visual end card with URLs and outro]
```

**Total spoken word count:** ~410 words
**Speaking pace:** ~155 wpm (Kokoro `am_echo` at speed=1.15)
**Total audio length:** 2:47.0 (measured, voiceover_full.wav)
**Video timeline:** ~2:51 (audio + ~4s VO clip insert) — leaves ~8s for end card

---

### Generation

The script above is the canonical source of truth for wording. A small Python
driver script generates per-chunk WAVs via the Kokoro Python bindings, then
concatenates into one full voice-over WAV with controlled inter-chunk silence.
The driver lives in a sibling video-production tree (kept separate from this
repo so the model code stays small); the pattern is straightforward enough to
reconstruct from the locked-decisions list below.

**Locked decisions:**

- Voice: `am_echo` (Kokoro)
- Speed: `1.15`
- Inter-chunk pause: `0.5s`
- Chunk 2: 0.3s embedded pause after "That's it." (Kokoro elides the period otherwise)
- Chunk 10: ellipses around "marker... slot... prose voice..." (preserves prosody better than splitting)
- Measured total: `2:47.0` audio; `~2:51` video timeline (after VO clip insert)
- Pronunciation hacks: `Power B I` (letter-by-letter), `C O 2` (letter-by-letter), `Corté` (accent for proper "kor-tay")

Outputs: a single `voiceover_full.wav` plus 13 per-chunk WAVs (`chunk_00.wav`
through `chunk_12.wav`) so individual chunks can be regenerated and spliced
back without re-running everything.

### Optional: human voice for closing line

For one personal moment, the closing line in chunk 12 is the natural candidate:

> "Civic data deserves to be accessible to everyone. CivicInsight is one piece of that — honest about what it can and can't do, pairable with verification when the source data exists."

Record on phone/laptop mic, replace `chunk_12.wav`, re-run generator with that chunk swapped in or splice manually. Skip if not wanted.

---

## Part 2: Demo staging (~30 min before recording)

### Pre-stage these states in advance

Modal app must be at `shahfazal--civicinsight-web-fastapi-app.modal.run` with `DEMO_HOT=1` flag, so containers stay warm and don't cold-start during recording.

Required input files (all staged in `~/projects/civicinsight/kaggle-dataset/`):

| File                                   | Used in                            | State for recording                                                  |
| -------------------------------------- | ---------------------------------- | -------------------------------------------------------------------- |
| `corse-ev-corte.png`                   | Chunk 6 demo                       | Simulated Corsica EV chargers map with Corté tooltip showing         |
| `corse-ev-porto-vecchio.png`           | Chunk 7 demo                       | Same map, Porto-Vecchio tooltip showing 14 chargers                  |
| `co2-line-dash-coal.png`               | Chunks 8+9 demo (continuous)       | OWID CO2 emissions chart, Coal series selected, tooltip at 1986/8336 |
| `co2-data-ground-truth.csv`            | Chunk 9 verification               | Source CSV — produces 1 verified / 3 unverified result               |
| `cheetah.png`                          | Chunk 10 demo                      | Public domain cheetah portrait                                       |
| NYC OpenData FHV dashboard             | Chunk 1 visual + VO clip capture   | data.cityofnewyork.us FHV trip volume, VoiceOver tabbed onto chart   |
| shahfazal.com elections viz            | Chunk 3 visual                     | shahfazal.com/elections-municipales-2026 (Plotly viz)                |
| AltText.ai / Writer.com / PBI alt-text | Chunk 3 visual (montage)           | Browser tabs ready for quick Cmd-Tab montage                         |
| Claude API pricing page                | Chunk 4 visual                     | claude.com/pricing or Anthropic privacy clause                       |

### Pre-recording checklist

```
[ ] Modal app deployed with DEMO_HOT=1
[ ] Modal app warmed up (one inference call right before recording)
[ ] Browser cache cleared
[ ] All input images on disk in known location
[ ] CSV file ready
[ ] No notifications visible (Do Not Disturb on)
[ ] Single monitor (avoid window-switching)
[ ] Quiet room
[ ] Cap installed (cap.so) — auto-zoom is a post-process in the editor, not live
```

---

## Part 3: Storyboard (shot-by-shot)

Each row = one chunk's visual beat. Cursor movement and zoom are critical.

| #   | Time      | Visual                                                                                                                                                                                                              | Cursor / camera notes                                                               | Audio                |
| --- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | -------------------- |
| 1   | 0:00-0:08 | **TITLE CARD intro** — render `video_assets/title_card/title-card.html` in Chrome fullscreen, Cap-record. Title + accent rule + subtitle, dark PaperMod theme, fade-up + Ken Burns. No badges.                       | Static capture, no cursor                                                           | Chunk 0              |
| 2   | 0:09-0:18 | NYC OpenData FHV dashboard with VoiceOver active. VO caption box visible: "Please use the arrow keys to pan the chart, region". Cursor on chart, blue focus ring around the chart region.                            | Cursor parked on chart; let VoiceOver focus settle                                  | Chunk 1              |
| 3   | 0:18-0:22 | **VO CLIP** — system audio captured during the chunk-1 recording plays here on its own iMovie audio track. Visual: continuation of the NYC dashboard frame.                                                          | No new cursor movement                                                              | (captured VO speech) |
| 4   | 0:23-0:34 | Stay on NYC dashboard with cursor wandering: filters panel briefly, table-toggle button bottom-left, hover the chart's table view. Reinforces "this dashboard tried but failed".                                     | Slow, deliberate cursor moves; minimum 1s between micro-targets                     | Chunk 2              |
| 5   | 0:35-0:46 | shahfazal.com/elections-municipales-2026 (Plotly viz with 84 ARIA attrs) for ~3s. Then quick montage: AltText.ai → Writer.com → Power BI alt-text page. Each ~2-3s.                                                  | Smooth dissolves / Cmd+Tab between tabs                                             | Chunk 3              |
| 6   | 0:47-0:57 | Claude API pricing page (claude.com/pricing). Cursor lingers on a per-token rate. Then slow zoom on the data-handling/privacy clause.                                                                                | Static or slow zoom — keep it deliberate                                            | Chunk 4              |
| 7   | 0:58-1:07 | **HF model card walkthrough** — huggingface.co/shahfazal/civicinsight-gemma4-e4b-it. Cursor on MIT license badge, then model size/params, then the README highlights.                                                | Cap auto-zoom on cursor stops                                                       | Chunk 5              |
| 8   | 1:08-1:23 | Modal app fresh. Drag `corse-ev-corte.png`. Result loads, right panel populates. Cursor lands on ARIA description: "[civicinsight-v1]" marker, then "Corté ... 9 chargers" portion.                                  | Drag-drop, hold 2s after upload, slow cursor to right panel for auto-zoom           | Chunk 6              |
| 9   | 1:24-1:35 | Clear app. Drag `corse-ev-porto-vecchio.png`. Result loads. Cursor pans to "Porto-Vecchio... 14 chargers".                                                                                                            | Cursor drag-drop, then slow pan to new tooltip text                                 | Chunk 7              |
| 10  | 1:35-1:49 | Clear app. Drag `co2-line-dash-coal.png` (NO CSV yet). Result loads. Cursor pans to "Coal line... 8,336 in 1986" portion of ARIA description.                                                                        | Cursor drag-drop, hold 2s, slow pan to highlighted phrase                           | Chunk 8              |
| 11  | 1:50-2:08 | **Continuous from row 10**. Cursor drags `co2-data-ground-truth.csv` into Source data CSV field, click Submit. Verification panel renders. Cursor pans to "1 of 4 numeric values verified", then to the "8,336 matches source — verified" green line vs surrounding red unverified entries. | Continuous take with row 10 — no app reset between                                  | Chunk 9              |
| 12  | 2:09-2:26 | Clear app. Drag `cheetah.png`. Result loads. Cursor pans to ARIA description: "[civicinsight-v1]" marker + "close-up portrait" slot opener. Pause briefly on the "marker", "slot", "prose voice" beats as Echo names them. | Drag-drop, slow pan, hold on key phrases per the ellipsis-paced narration           | Chunk 10             |
| 13  | 2:27-2:41 | Three quick browser-tab cuts: HF model card (cursor on MIT license) → terminal showing `git log --oneline \| head -8` (real local commits) → Modal demo URL in address bar.                                          | Pre-stage tabs (Cmd+1/2/3); deliberate switches with ~4s per tab                    | Chunk 11             |
| 14  | 2:42-2:52 | Final emotional close. Stay on Modal URL with cursor parked, slow zoom-out via Cap auto-zoom. Or reuse the intro title-card frame as a visual bookend.                                                               | Static or very slow zoom-out                                                        | Chunk 12             |
| 15  | 2:52-3:00 | **END CARD** — render `video_assets/end_card/end-card.html` in Chrome fullscreen, Cap-record ~15s. URLs (HF / GitHub / Modal), hackathon attribution (Main Track • Digital Equity & Inclusivity • Unsloth), handle.   | Static capture, no cursor                                                           | Silence (or outro music) |

### Critical timing notes

- After upload, wait 2 full seconds before cursor moves (let the page settle)
- After result loads, hold 1 second on full panel before zoom begins
- During zoom, hold 2 seconds at zoomed level on key text before panning
- Cursor should NEVER move during voice-over emphasis points

### Recording approach

**Record visuals first, no audio. Then sync audio in post.**

This decouples cursor accuracy from voice-over accuracy. Mistakes in either layer are independent — re-record the affected layer only.

For each demo:

1. Practice the cursor path 2-3 times
2. Record 2-3 clean takes
3. Pick best take
4. Move on

Don't try to nail it on the first try.

---

## Part 4: Editing — Cap (visuals) → iMovie (assembly + audio)

Cap doesn't accept external audio imports, so the pipeline splits in two:

### Step 1: Cap — process and export each clip

For each recording (Act 1 clips, 5 demo clips, Act 4 closing clips):

```
1. Open the recording in Cap Studio Mode
2. Verify auto-zoom segments look right (cursor stops should zoom)
3. Trim head/tail
4. Mute the captured audio track (we don't need system audio)
5. Export → MP4, 1920×1080, 30fps
6. Save to video_assets/clips/clip_NN.mp4
```

### Step 2: iMovie — assemble with voiceover

```
1. Open iMovie → New Project → Movie
2. Import all clip_NN.mp4 files (drag into media library)
3. Drag clips onto the timeline in storyboard order
4. Drag voiceover_full.wav onto the music/VO track (below video)
5. Align: chunk 0 audio starts at 0:00, each subsequent chunk aligns to its storyboard slot. Drop the captured VO clip into the gap between chunk_01.wav and chunk_02.wav.
6. If a clip is shorter than its audio chunk, hold the last frame (right-click → Detach Audio → extend)
7. If longer, trim the clip
8. Add title card (Titles → choose Standard) at 0:30-0:38
9. Add end card at 2:45-3:00
10. Export → File → Share → File → 1080p, High quality
```

If audio is too long for visuals, hold a still-frame; if too short, lengthen cursor pauses in Cap and re-export the affected clip.

### Title card (0:30-0:38, ~8 seconds)

```
Title:    CivicInsight
Subtitle: Open-source civic data accessibility
Badges:   [MIT licensed] [Runs locally] [Verifies output]

Background: subtle gradient, dark
Animation: title fades in over 1s, subtitle 0.5s after
Hold:      ~6 seconds before transition
```

### End card (2:45-3:00, ~15 seconds)

```
CivicInsight

Model:   huggingface.co/shahfazal/civicinsight-gemma4-e4b-it
Code:    github.com/shahfazal/civicinsight
Demo:    [Modal app URL]

Submitted to Gemma 4 Good Hackathon — Digital Equity Track

[github.com/shahfazal]

Background: same as title card for visual continuity
Animation: fade in over 1s, hold for 14s
```

### Cursor zoom (post-process)

Cap's auto-zoom is applied during editor processing, not live capture. Record raw with steady cursor movements; Cap detects cursor stops and inserts zoom segments automatically when you process the recording. Trust the default unless a zoom misses or feels jarring — adjust segments manually in the timeline editor.

Recording-time implication: pause cursor for ~2s on each element you want zoomed (right-panel ARIA text, verification line, license badge). Move cursor away to signal zoom-out.

### Music

Optional but recommended: subtle background music under voice-over.

Royalty-free options:

- YouTube Audio Library: search "documentary" or "ambient"
- Pixabay Music: filter by "no attribution required"
- Suno-generated track (your own prompt, MIT-aligned)

Volume: -20 dB below voice-over peak. Should be barely audible.

Cut music slightly before voice-over starts and ends.

---

## Part 5: Export and review

### Export settings

```
Format:     MP4
Resolution: 1920×1080
Frame rate: 30fps
Bitrate:    Variable, ~8 Mbps target
Audio:      AAC, 192 kbps
Filename:   civicinsight-demo-final.mp4
Duration:   ≤3:00 (verify before export)
```

### Pre-upload review checklist

```
[ ] Total duration ≤ 3:00 (ideally 2:55-3:00)
[ ] Audio clear, no clipping
[ ] No personal info visible (email signatures, browser bookmarks, file names with PII)
[ ] All URLs in end card readable when paused
[ ] Cursor movements feel deliberate, not fidgety
[ ] All demos show clean Modal app states (no error messages, no stale UI)
[ ] Subtitles or captions optional but help accessibility (consider adding via YouTube auto-caption + manual review)
```

---

## Part 6: YouTube upload

```
[ ] Upload as Public (NOT Unlisted — Kaggle requires no-login access)
[ ] Title: "CivicInsight: Open-Source Civic Data Accessibility — Gemma 4 Good Hackathon"
[ ] Description: link to Kaggle writeup, GitHub, HuggingFace
[ ] Tags: gemma, accessibility, civic-data, vision-language, open-source
[ ] Set as Not Made for Kids
[ ] Disable comments if preferred (optional)
[ ] Upload caption file or use YouTube auto-captions (recommended for accessibility)
[ ] Verify URL is publicly accessible from incognito browser
```

---

## Risk mitigation

### If Kokoro audio quality is unacceptable

Currently locked: `am_echo` @ 1.15. Fallback chain:

1. **Try different voice** in Kokoro (a/b tested: am_michael, am_adam, am_eric, bm_george, bm_fable for male alternatives)
2. **Adjust speed** (0.95 for slower/clearer; 1.20 if too slow — though 1.15 already calibrated against the 3:00 budget)
3. **Try ElevenLabs free tier** (Rachel or Adam voice, 10k chars/month free, ~410 words easily fits)
4. **Hybrid**: Use Kokoro for most chunks, ElevenLabs for the emotional close (chunk 12) only

### If video time runs over 3:00

Cuts in priority order (least to most important):

1. Trim chunk 3 (problem montage) by 2-3 seconds
2. Reduce title card (chunk 0) hold time
3. Reduce end card hold time
4. Trim cursor pause times by 0.5s each
5. Shorten the captured VO clip (chunk-1→chunk-2 gap) from ~4s to ~3s

DO NOT cut: any of the demos themselves (chunks 6-10), the architectural-claim moment in chunk 9 (CO2 verification), or the closing emotional line in chunk 12.

### If demos fail during recording

Modal cold-start can introduce delay. Mitigation:

- Pre-warm app with dummy upload 30 seconds before recording
- Record demos one at a time, allowing pre-warm between
- If a demo takes >5 seconds to respond, edit out the wait time in post

### If running out of time near deadline

Minimum viable video (still submittable):

- Skip Act 1 problem montage; replace with single 5-second screen reader clip
- Skip end card animation; use static URLs for 5 seconds
- Use single take per demo; don't retake
- Skip background music

This shaves ~2 hours of work; quality drops but the submission is valid.

---

## Out of scope

These are explicitly not in this pipeline:

- Modifications to the Modal app or the model itself
- Rewriting the voice-over script (locked above)
- Adding new demos beyond the four listed
- Subtitle/caption generation (YouTube auto-captions are sufficient)
- Multi-language versions
- Promotional materials beyond the 3-minute video itself
