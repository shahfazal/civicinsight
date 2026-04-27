"""
Gradio demo: two upload boxes (image required, CSV optional) and a
structured output panel showing ARIA description plus verification.

Run locally:
  $ python -m app.io.demo

The Modal-deployed InferenceServer must be live (deploy via
`modal deploy app/io/inference.py`) before the demo can produce real output.
"""

import io

import gradio as gr
from PIL import Image

from app.agent import run as agent_run


_TITLE = "CivicInsight: Accessible Civic Data"
_DESCRIPTION = (
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


def process(image: Image.Image, csv_path):
    """
    Gradio handler. Receives a PIL image and an optional CSV file path.
    Returns the FormattedOutput pieces as separate UI strings.
    """
    if image is None:
        return (
            "Please upload a dashboard image to begin.",
            "no-input",
            "Not applicable",
            "",
            "",
            "",
        )

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    out = agent_run(image_bytes=image_bytes, csv_path=csv_path)

    details = "\n".join(out.verification_details) if out.verification_details else "No per-value details."
    issues = "\n".join(out.structural_issues) if out.structural_issues else "None"

    return (
        out.aria_label,
        out.data_status,
        _format_confidence(out.confidence),
        out.verification_summary,
        details,
        issues,
    )


demo = gr.Interface(
    fn=process,
    inputs=[
        gr.Image(type="pil", label="Dashboard screenshot"),
        gr.File(type="filepath", label="Source data CSV (optional)", file_types=[".csv"]),
    ],
    outputs=[
        gr.Textbox(label="ARIA Description", lines=4),
        gr.Textbox(label="Data Status"),
        gr.Textbox(label="Confidence"),
        gr.Textbox(label="Verification Summary", lines=2),
        gr.Textbox(label="Per-value Verification", lines=8),
        gr.Textbox(label="Structural Issues"),
    ],
    title=_TITLE,
    description=_DESCRIPTION,
    flagging_mode="never",
)


if __name__ == "__main__":
    demo.launch()
