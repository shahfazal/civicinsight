# Gradio demo accessibility pass

**Status:** Implemented. See `app/io/demo.py` and `app/io/web.py`. All originally-scoped items landed: ARIA labels, focus-visible CSS, semantic per-value list, skip-to-results link, placeholder contrast, webcam source removal, aria-live announcement (via offscreen announcer that filters Gradio progress text), auto-focus on result arrival, loading-state announcement on submit, tabindex restoration on output containers (so plain Tab navigates into them), descriptive aria-label on the copy button, and a custom indigo "CI" favicon.

**Mount-vs-launch parity:** local `python -m app.io.demo` now runs through `mount_gradio_app` + uvicorn, identical to the Modal `web.py` deployment path. Theme, CSS, head HTML, and JS reach the browser the same way in dev and prod.

**Lighthouse score:** 0.96 / 1.00 pre-fix.

- Color-contrast finding (empty-state placeholder of the per-value list) addressed by switching from `rgb(96, 96, 96)` to `var(--body-text-color)` with `opacity: 0.7`, so the muted appearance tracks Gradio's theme in both dark and light mode.
- Label-content-name-mismatch on Gradio's stock upload buttons addressed via JS pass: read each upload button's visible text and copy it into `aria-label` so voice-control users saying "click upload" match what the screen reader hears.

**Demo polish landed alongside a11y:**

- **Inference overlay.** Modal-style backdrop with a centered card (title, generic timing copy, animated spinner) shown on submit. `role="status"` + `aria-live="polite"` on the overlay so screen readers announce the loading state through the overlay itself rather than the offscreen announcer alone. Dismissable via ESC, backdrop click, or X button. Honors `prefers-reduced-motion`. Auto-hides when the result arrives.

**Page-refresh warning: deliberately not implemented.** The natural mechanism (`window.beforeunload`) is incompatible with Gradio's streaming inference response on Chrome. Even when the user clicks Cancel on the browser's confirmation dialog, Chrome aborts the in-flight streaming connection as part of its pre-unload optimization. The result: the user follows the warning correctly and still loses their inference work. We removed the handler rather than punish cooperative users. Pre-submit overlay copy ("Please do not refresh this page") is the only mitigation. Reconnection / cancel-and-rerun UX is scoped as v2.

**Items deferred to v2 (post-submission):**

- Cancel-and-rerun UX with state restoration after accidental refresh.
- Mobile screen reader testing (TalkBack, mobile VoiceOver) and high-contrast mode support remain unscoped.
- Comprehensive WCAG AA audit beyond Lighthouse's automated checks remains v2.


**Context:** The Gradio demo at `app/io/demo.py` is the primary user-facing surface for CivicInsight. The project is built around accessibility (ARIA descriptions for civic data dashboards). Per Faz's review with the build agent: "the page itself is NOT completely a11y good." A Digital Equity & Inclusivity track submission with an inaccessible demo interface is a credibility risk. Judges who care about the track will check.

**Goal:** Address the most glaring accessibility issues in the Gradio demo so the interface is at least defensible at WCAG AA level for primary user flows. Document remaining limitations honestly in the writeup.

**Scope constraint:** This is NOT a full WCAG audit. Time-boxed at 2-3 hours. Goal is "no glaring issues" not "fully accessible." Document what's not addressed.

---

## What this fixes (priority order)

### Priority 1: ARIA labels on every interactive element

Every Gradio component the user interacts with should have a clear, screen-reader-readable label. Default Gradio labels are often present but minimal.

Components to verify:
- Image upload box ("Dashboard screenshot")
- CSV upload box ("Source data CSV (optional)")
- Submit button (if present, or ensure the form's submit action is announced)
- Output text area (the ARIA description itself)
- Output text fields (Data Status, Confidence, Verification Summary, Per-value Verification)

Implementation: each `gr.File()`, `gr.Image()`, `gr.Textbox()` accepts a `label` parameter. Confirm every component has a meaningful label, not a default like "Output" or "Input".

For complex outputs (the per-value verification table), add `info=` parameters to give context.

### Priority 2: Loading state announced to screen readers

When the user submits and inference starts (potentially 30-90 seconds), a screen reader user has no idea what's happening. Default Gradio spinners are visual.

Implementation:
- Add an `aria-live="polite"` region that announces "Generating description, please wait. This may take 30 to 90 seconds." when inference begins
- Optionally announce progress updates if the inference function can yield intermediate states
- Announce completion: "Description ready" when output is rendered

In Gradio 4+, this is typically done via `gr.HTML` with the live region OR via the queue progress callbacks.

### Priority 3: Focus visibility

Test by tabbing through every interactive element. Each focused element should have a visible indicator (outline, border, contrast change).

Common Gradio default: focus is barely visible on the dark theme. Fix via custom CSS:

```css
*:focus-visible {
    outline: 2px solid #4A9EFF;
    outline-offset: 2px;
}
```

Inject this via Gradio's `css=` parameter on the `gr.Interface()` constructor.

### Priority 4: Color contrast

The current dark theme may have insufficient contrast for some text/background combinations. WCAG AA requires:
- 4.5:1 for normal text
- 3:1 for large text and UI components

Test using WebAIM's contrast checker. Common issue points on Gradio dark theme:
- Placeholder text in input fields
- Disabled state buttons
- Subtle borders

Fix: adjust the affected colors in custom CSS, OR document the limitation in the writeup if a comprehensive theme overhaul isn't feasible.

### Priority 5: File upload accessibility

The "Drop File Here / Click to Upload" area is the primary entry point. Verify:
- It's reachable by keyboard (Tab key)
- It announces its purpose to screen readers ("File upload area for dashboard screenshot")
- After file selection, the filename is announced to confirm
- File type restrictions are announced (e.g., "PNG and JPG accepted")

---

## Testing protocol

### Mandatory: macOS VoiceOver test

Faz is on macOS. VoiceOver is built-in (Cmd+F5).

Test flow:
1. Open the Gradio demo URL with VoiceOver active
2. Navigate by Tab key through every interactive element
3. Confirm each element announces clearly
4. Upload an image, confirm filename and upload status are announced
5. Trigger inference, confirm loading state is announced
6. Wait for completion, confirm output is reachable and readable
7. Optionally upload a CSV, repeat

Document each announcement that's broken or missing. Fix the top 3-5 issues.

### Optional: NVDA test on Windows (if accessible)

NVDA is the most common free Windows screen reader. Different rendering quirks than VoiceOver.

If a Windows machine is available, repeat the protocol with NVDA. If not, skip and document in limitations.

### Skip: JAWS, mobile screen readers, high-contrast mode

These are out of scope for the time budget. Document as known gaps.

---

## What's intentionally NOT in scope

These are real accessibility issues but won't be addressed in this pass:

- Full keyboard-only navigation polish (focus order, escape key handling, modal dialog focus traps)
- Mobile screen reader testing (TalkBack on Android, VoiceOver on iOS)
- High-contrast mode support
- Reduced-motion preferences
- Alternative output formats (audio, braille-friendly markup)
- Full RTL language support
- WCAG AAA compliance

Each is documented in the writeup limitations section as v2 work.

---

## Honest writeup framing

Add to the writeup's limitations or accessibility section:

> "The Gradio demo interface received a focused accessibility pass covering ARIA labels, focus visibility, loading state announcement, and color contrast. Tested with macOS VoiceOver. A comprehensive WCAG AA audit, mobile screen reader testing, and high-contrast mode support are scoped as v2 work. The system's primary deliverable, accessible ARIA descriptions for civic data, does not depend on the demo UI; the descriptions can be embedded in any accessible interface."

This frames honestly: accessibility was considered in v1, has documented gaps, the project's core deliverable is unaffected. Beats either "fully accessible" overclaim or silent omission.

---

## Estimated time

| Step | Time |
|---|---|
| VoiceOver test of current state, document issues | 45 min |
| Fix top 3-5 issues (ARIA labels + focus CSS + loading announcement) | 60-90 min |
| Re-test with VoiceOver, confirm fixes | 30 min |
| Document remaining limitations in writeup | 15 min |
| **Total** | **~2.5-3 hours** |

---

## Decision: when to do this

Should happen BEFORE the demo URL goes public to judges. Concretely: before May 13 (HF public flip date used as the milestone for "things must be defensible").

Can be sequenced anywhere in the work week. Doesn't depend on benchmark, retraining, or video work.

If time is tight: the ARIA labels + focus CSS are the highest-value items (~1 hour). Skip the loading announcement and color contrast if needed. Document everything skipped.
