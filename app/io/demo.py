"""
Gradio demo: two upload boxes (image required, CSV optional) and a
structured output panel showing ARIA description plus verification.

Run locally:
  $ python -m app.io.demo

The Modal-deployed InferenceServer must be live (deploy via
`modal deploy app/io/inference.py`) before the demo can produce real output.

Accessibility notes:
  - Every interactive component has an explicit label and, where relevant,
    an info string giving extra context for screen readers.
  - The Per-value Verification panel renders as a real semantic <ul><li>
    list via gr.HTML rather than a multi-line textbox, so screen readers
    can navigate item by item.
  - Custom CSS injects a high-contrast focus-visible outline and a
    Skip-to-results anchor target.
  - aria-live regions, output tabindex restoration, and a descriptive
    copy-button aria-label are wired via _CUSTOM_HEAD. Auto-focus on
    submit and loading-state announcement are not yet wired; when added
    they go through _CUSTOM_JS, which web.py forwards to mount_gradio_app.

Mount-vs-launch: gr.Interface stores theme/css/head/js as attributes that
are only consumed on .launch(). When mounted via mount_gradio_app the mount
re-assigns blocks.css/theme/head/js from its own kwargs, blowing away
whatever the Interface had. So _THEME, _CUSTOM_CSS, _CUSTOM_HEAD, and
_CUSTOM_JS are exported as module-level constants and web.py re-passes them
to mount_gradio_app. Don't move them inside the Interface() call only.
"""

import html
import io

import gradio as gr
from PIL import Image

from app.agent import run as agent_run


# Theme inspired by shahfazal.com (Hugo PaperMod). Minimalist, near-white in
# light mode, system font stack, 8px corner radius. Color values lifted from
# ~/projects/shahfazal.com/themes/PaperMod/assets/css/core/theme-vars.css.
_THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.slate,
    neutral_hue=gr.themes.colors.gray,
    radius_size=gr.themes.sizes.radius_md,
    font=[
        gr.themes.GoogleFont("Inter"),
        "-apple-system",
        "BlinkMacSystemFont",
        "Segoe UI",
        "Roboto",
        "sans-serif",
    ],
).set(
    body_background_fill="rgb(255, 255, 255)",
    body_text_color="rgb(30, 30, 30)",
    background_fill_primary="rgb(255, 255, 255)",
    background_fill_secondary="rgb(245, 245, 245)",
    border_color_primary="rgb(238, 238, 238)",
    block_label_text_color="rgb(108, 108, 108)",
    block_title_text_color="rgb(30, 30, 30)",
    block_border_width="1px",
    button_primary_background_fill="rgb(30, 30, 30)",
    button_primary_text_color="rgb(255, 255, 255)",
    button_primary_background_fill_hover="rgb(60, 60, 60)",
    input_placeholder_color="rgb(96, 96, 96)",
)

_CUSTOM_CSS = """
.gradio-container { max-width: 1280px !important; margin: 0 auto !important; }
.contain { padding: var(--gap, 24px) !important; }

/* WCAG 2.4.7: visible focus indicator on every interactive element. */
*:focus-visible {
    outline: 2px solid #2563eb !important;
    outline-offset: 2px !important;
    border-radius: 2px;
}

/* Skip-to-results link: visually hidden until focused, then revealed at the
   top-left of the page so keyboard users can jump past the upload form. */
.civicinsight-skip-link {
    position: absolute;
    left: -9999px;
    top: auto;
    width: 1px;
    height: 1px;
    overflow: hidden;
    z-index: 100;
}
.civicinsight-skip-link:focus {
    position: static;
    width: auto;
    height: auto;
    display: inline-block;
    padding: 8px 12px;
    background: #2563eb;
    color: #ffffff;
    text-decoration: underline;
    border-radius: 4px;
}

/* Per-value verification list: real <ul><li>, not a textbox. Screen readers
   announce list length and per-item navigation. */
.civicinsight-verifications {
    margin: 0;
    padding-left: 1.25rem;
    list-style-type: disc;
    line-height: 1.5;
}
.civicinsight-verifications li {
    margin: 0.25rem 0;
}
.civicinsight-verifications li.civicinsight-verified {
    color: rgb(30, 30, 30);
}
.civicinsight-verifications li.civicinsight-unverified,
.civicinsight-verifications li.civicinsight-ambiguous {
    color: rgb(120, 50, 50);
}
.civicinsight-verifications-empty {
    margin: 0;
    color: var(--body-text-color);
    opacity: 0.7;
    font-style: italic;
}
"""

# Inline SVG favicon. Same indigo/white pattern as the
# elections-municipales-2026 site. Inline data URI avoids serving a
# static file via FastAPI; ships identically in local + Modal.
_FAVICON_LINK = (
    '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;utf8,'
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
    "<rect width='16' height='16' rx='3' fill='%237c6af7'/>"
    "<text x='8' y='12' font-family='system-ui,Arial,sans-serif' "
    "font-size='10' font-weight='700' letter-spacing='-0.5' fill='white' "
    "text-anchor='middle'>CI</text></svg>\">"
)

# Five things Gradio does not give us declaratively:
#   1. Tab navigation into outputs. Gradio's read-only output textareas are
#      either tabindex="-1" or rendered as non-focusable divs, so plain Tab
#      skips them entirely. We make the outer container focusable instead,
#      which is content-agnostic and survives Gradio's internal re-renders.
#   2. Single, clean screen-reader announcement when the final ARIA
#      description arrives. We cannot put aria-live directly on the visible
#      output: Gradio overwrites the textbox value with "processing | 7.2s"
#      tick-by-tick, and any aria-live region speaks every tick. Instead we
#      use an offscreen announcer div, write to it only when the textarea
#      content is NOT a progress string, and let the live region speak
#      the final result exactly once.
#   3. Loading-state announcement on submit. Without it, a screen reader
#      user clicks Submit and hears nothing for up to 3 minutes, with no
#      cue that work is in progress. We hook the submit button click and
#      write a short progress message to the same announcer.
#   4. Auto-focus on the ARIA Description when results land. After clicking
#      Submit the browser keeps focus on the button, so screen reader users
#      have to manually navigate to find the result. We move focus to the
#      ARIA Description container the moment new content arrives.
#   5. A meaningful aria-label on the copy button. Gradio's default is
#      just "Copy", so VoiceOver announces "Copy button" with no context.
# Tabindex is re-applied on every mutation because Gradio overwrites it
# during component re-renders. The announcer div, submit hook, and
# copy-button label are one-time and gated by a dataset flag.
_CUSTOM_HEAD = _FAVICON_LINK + """
<script>
(function() {
  const OUTPUT_IDS = [
    "civicinsight-aria-description",
    "civicinsight-data-status",
    "civicinsight-confidence",
    "civicinsight-verification-summary",
    "civicinsight-verification-details",
    "civicinsight-structural-issues",
  ];
  const PRIMARY_ID = "civicinsight-aria-description";
  const SUBMIT_ID = "civicinsight-submit";
  const ANNOUNCER_ID = "civicinsight-announcer";
  const PROGRESS_RE = /^\\s*processing\\s*\\|/i;
  const LOADING_MSG =
    "Generating description. First request after a quiet period " +
    "may take up to 3 minutes.";

  var lastAnnounced = "";

  function ensureAnnouncer() {
    var a = document.getElementById(ANNOUNCER_ID);
    if (a) return a;
    a = document.createElement("div");
    a.id = ANNOUNCER_ID;
    a.setAttribute("aria-live", "polite");
    a.setAttribute("aria-atomic", "true");
    a.setAttribute("role", "status");
    a.style.cssText = "position:absolute;left:-9999px;width:1px;" +
      "height:1px;overflow:hidden;clip:rect(0 0 0 0);";
    document.body.appendChild(a);
    return a;
  }

  function applyA11y() {
    OUTPUT_IDS.forEach(function(id) {
      var el = document.getElementById(id);
      if (!el) return;
      if (el.getAttribute("tabindex") !== "0") {
        el.setAttribute("tabindex", "0");
      }
      if (el.hasAttribute("disabled")) {
        el.removeAttribute("disabled");
      }
    });

    var submitBtn = document.getElementById(SUBMIT_ID);
    if (submitBtn && submitBtn.dataset.a11ySubmitWired !== "1") {
      submitBtn.addEventListener("click", function() {
        // Snapshot current ARIA Description as already-spoken. Gradio
        // leaves the previous result in the textarea until the new run
        // overwrites it; without this snapshot we re-announce stale text.
        var p = document.getElementById(PRIMARY_ID);
        var pTa = p && p.querySelector("textarea");
        lastAnnounced = (pTa ? pTa.value || "" : "").trim();
        ensureAnnouncer().textContent = LOADING_MSG;
      });
      submitBtn.dataset.a11ySubmitWired = "1";
    }

    var primary = document.getElementById(PRIMARY_ID);
    if (primary) {
      var ta = primary.querySelector("textarea");
      if (ta) {
        var val = (ta.value || "").trim();
        if (val && !PROGRESS_RE.test(val) && val !== lastAnnounced) {
          ensureAnnouncer().textContent = val;
          lastAnnounced = val;
          try { primary.focus(); } catch (e) {}
        }
      }
    }

    var copyBtn = document.querySelector(
      "#civicinsight-aria-description button[aria-label='Copy']"
    );
    if (copyBtn && copyBtn.dataset.a11yApplied !== "1") {
      copyBtn.setAttribute(
        "aria-label",
        "Copy ARIA description to clipboard"
      );
      copyBtn.dataset.a11yApplied = "1";
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyA11y);
  } else {
    applyA11y();
  }
  var obs = new MutationObserver(applyA11y);
  obs.observe(document.body, { childList: true, subtree: true });
})();
</script>
"""

_CUSTOM_JS: str | None = None


_TITLE = "CivicInsight: Accessible Civic Data"

# Description is rendered as Markdown/HTML by Gradio. The skip link is
# wrapped in a div with our class so the hide-until-focus CSS applies. The
# anchor target (#civicinsight-aria-description) is the elem_id of the first
# result component below.
_DESCRIPTION = (
    '<div><a class="civicinsight-skip-link" '
    'href="#civicinsight-aria-description">Skip to results</a></div>\n\n'
    "Upload a civic dashboard screenshot to generate an ARIA-ready description. "
    "Optionally attach the source data as a CSV: each extracted number will be "
    "cross-referenced against the data and flagged if it cannot be confirmed.\n\n"
    "**A note on timing.** First request after a quiet period takes 1-3 minutes "
    "while the model loads onto the GPU. Subsequent requests within ~2 minutes "
    "complete in 30-90 seconds depending on chart complexity. The cold-start "
    "cost is real GPU time and is intentionally accepted to keep this demo "
    "free-to-host (no API keys, no subscription)."
)


def _format_confidence(confidence) -> str:
    if confidence is None:
        return "Not applicable (no source data provided)"
    return f"{confidence:.0%}"


def _verification_details_html(details: list[str]) -> str:
    """Render per-value verification lines as a semantic <ul><li> list."""
    if not details:
        return (
            '<p class="civicinsight-verifications-empty" '
            'role="status">No per-value details.</p>'
        )

    items = []
    for line in details:
        if line.startswith("Verified"):
            cls = "civicinsight-verified"
        elif line.startswith("Ambiguous"):
            cls = "civicinsight-ambiguous"
        else:
            cls = "civicinsight-unverified"
        items.append(f'<li class="{cls}">{html.escape(line)}</li>')

    return (
        '<ul class="civicinsight-verifications" '
        f'aria-label="Per-value verification, {len(items)} items">'
        + "".join(items)
        + "</ul>"
    )


def process(image: Image.Image, csv_data):
    """
    Gradio handler. Receives a PIL image and optional CSV file content as
    bytes (gr.File with type="binary" returns bytes directly, not a path).
    Returns the FormattedOutput pieces as separate UI strings, with the
    per-value verification rendered as semantic HTML for accessibility.

    The bytes-based CSV path is robust to Gradio's temp-file cleanup, which
    can fire mid-inference for long-running requests and leave a stale path
    behind. Bytes stay in memory across the full request.
    """
    if image is None:
        return (
            "Please upload a dashboard image to begin.",
            "no-input",
            "Not applicable",
            "",
            _verification_details_html([]),
            "",
        )

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    out = agent_run(image_bytes=image_bytes, csv_bytes=csv_data)

    issues = "\n".join(out.structural_issues) if out.structural_issues else "None"

    return (
        out.aria_label,
        out.data_status,
        _format_confidence(out.confidence),
        out.verification_summary,
        _verification_details_html(out.verification_details),
        issues,
    )


demo = gr.Interface(
    fn=process,
    inputs=[
        gr.Image(
            type="pil",
            label="Dashboard screenshot",
            height=520,
            # Restrict to upload + clipboard. The webcam source default is
            # noise for a screenshot-driven app and adds a focus stop that
            # keyboard users have to skip past.
            sources=["upload", "clipboard"],
        ),
        gr.File(type="binary", label="Source data CSV (optional)", file_types=[".csv"]),
    ],
    outputs=[
        gr.Textbox(
            label="ARIA Description",
            lines=4,
            buttons=["copy"],
            elem_id="civicinsight-aria-description",
        ),
        gr.Textbox(
            label="Data Status",
            info="One of verified, partial, unverified, or no-input.",
            elem_id="civicinsight-data-status",
        ),
        gr.Textbox(
            label="Confidence",
            info="Percent of extracted numbers confirmed against source CSV.",
            elem_id="civicinsight-confidence",
        ),
        gr.Textbox(
            label="Verification Summary",
            lines=2,
            elem_id="civicinsight-verification-summary",
        ),
        gr.HTML(
            label="Per-value Verification",
            value=_verification_details_html([]),
            elem_id="civicinsight-verification-details",
        ),
        gr.Textbox(
            label="Structural Issues",
            info="Schema or formatting problems detected in the model output.",
            elem_id="civicinsight-structural-issues",
        ),
    ],
    title=_TITLE,
    description=_DESCRIPTION,
    flagging_mode="never",
    theme=_THEME,
    css=_CUSTOM_CSS,
    # TEMP: api_visibility removed (defaults to "public") to verify whether
    # the SSE 404 on Submit was caused by api_visibility="private" blocking
    # the UI's own queue/SSE plumbing. Revert to "private" or "undocumented"
    # once we confirm the cause and pick the right setting.
    submit_btn=gr.Button("Submit", variant="primary", elem_id="civicinsight-submit"),
)


if __name__ == "__main__":
    # Local runner mirrors the production mount path (web.py) so theme,
    # CSS, head, and JS reach the browser identically. .launch() in
    # Gradio 6 cannot consume head/js, only mount_gradio_app can.
    import uvicorn
    from fastapi import FastAPI
    from gradio.routes import mount_gradio_app

    fast_app = FastAPI()
    mount_gradio_app(
        fast_app,
        demo,
        path="/",
        theme=_THEME,
        css=_CUSTOM_CSS,
        head=_CUSTOM_HEAD,
        js=_CUSTOM_JS,
    )
    uvicorn.run(fast_app, host="127.0.0.1", port=7860)
