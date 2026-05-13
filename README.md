# CivicInsight - ARIA-ready descriptions for civic data visualizations

[![License: MIT](https://img.shields.io/badge/License-MIT-violet.svg)](LICENSE)

A fine-tuned Gemma 4 E4B model paired with a deterministic verification layer, producing alt-text for civic data dashboards that screen reader users can both **understand** and **verify**. MIT-licensed, runs locally on commodity GPU, no API keys, no third-party calls.

Submitted to the **Kaggle Gemma 4 Good Hackathon** - Main Track, Impact Track (Digital Equity & Inclusivity), and Special Technology Track (Unsloth).

![CivicInsight title card alongside a screenshot of the demo: a CO2 emissions line chart on the left, and the model's ARIA description on the right with data status "partial", confidence "25%", and verification summary "1 of 4 numeric values verified against source data".](docs/images/hero.png)

## Quick links

- **Live demo**: https://shahfazal--civicinsight-web-fastapi-app.modal.run
- **Model**: [`shahfazal/civicinsight-gemma4-e4b-it`](https://huggingface.co/shahfazal/civicinsight-gemma4-e4b-it) on HuggingFace
- **Notebook**: [`notebooks/civicinsight-gemma-4-good-hackathon-submission.ipynb`](notebooks/civicinsight-gemma-4-good-hackathon-submission.ipynb)
- **Technical writeup**: [`docs/writeup.md`](docs/writeup.md)
- **Kaggle submission**: [CivicInsight on the Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon/writeups/civicinsight) (Main Track + Impact Track + Special Technology Track)

## What this is

Civic dashboards (election results, hospital metrics, air quality, school performance) are often inaccessible to screen reader users. Charts surface as "image" or "chart" with no underlying values. Generic alt-text tools produce sparse, value-free descriptions; frontier-model APIs work but require ongoing API spend and route data to third parties.

CivicInsight produces ARIA-ready descriptions that include actual values, selection states, tooltip content, and chart-type structure. Outputs are verified against an optional source CSV before being shown to the user, so the description carries a `verified` / `partial` / `unverified` signal rather than asking the reader to trust raw model output.

See [`docs/writeup.md`](docs/writeup.md) for the full architecture rationale, the held-out audit findings, and the Unsloth contribution arc.

## Try it

Visit the [live demo](https://shahfazal--civicinsight-web-fastapi-app.modal.run), drop in any chart screenshot, and get back an ARIA description. Add a source CSV (optional) and you also get per-value verification against the data. No login required (publicly accessible from May 13, 2026).

## How it works

Two layers:

1. **Fine-tuned Gemma 4 E4B** ([`app/io/inference.py`](app/io/inference.py)), vision-unfrozen LoRA r=16 on 61 civic dashboards. Emits a `[civicinsight-v1]` marker as its first token, used downstream as a structural fingerprint.
2. **Deterministic verifier** ([`app/core/`](app/core/) + [`app/grounding/`](app/grounding/)), six small Python modules (`extract`, `validator`, `source`, `match`, `format`, `agent`). No LLM in the routing loop. When a source CSV is supplied, every numeric claim in the description is cross-referenced with scale-aware tolerance (5% for K/M/B/T-scaled, 0.5% for raw).

The web demo ([`app/io/web.py`](app/io/web.py)) wraps a Gradio Interface in a Modal-hosted FastAPI app with body-size cap, per-IP rate limit, and access logging.

> **Why verification?** The model's failure modes are catalogued in the [pre-DPO held-out audit](docs/civicinsight-pre-dpo-audit.md), including a fabricated-tooltip case where the model invented Ireland's GDP from pretraining and presented it as chart data. The verifier catches exactly that class of error.

## Run it

The fine-tuned adapter is published at [`shahfazal/civicinsight-gemma4-e4b-it`](https://huggingface.co/shahfazal/civicinsight-gemma4-e4b-it) on HuggingFace Hub. Load it like any other Unsloth-compatible vision model:

```python
from unsloth import FastVisionModel
from PIL import Image

model, tokenizer = FastVisionModel.from_pretrained(
    "shahfazal/civicinsight-gemma4-e4b-it",
    revision="v1.0",
    load_in_4bit=True,
)
FastVisionModel.for_inference(model)

image = Image.open("your-chart.png")
messages = [{"role": "user", "content": [
    {"type": "image", "image": image},
    {"type": "text", "text": "Generate an aria-label for this data visualization image."},
]}]
inputs = tokenizer.apply_chat_template(messages, add_generation_prompt=True,
    tokenize=True, return_dict=True, return_tensors="pt").to(model.device)
outputs = model.generate(**inputs, max_new_tokens=600)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

Runs on a single 40GB GPU (A100, RTX 6000 Ada) at 4-bit, or fits a 16GB GPU (T4, RTX 4090) with adjusted settings. The canonical [Kaggle submission notebook](notebooks/civicinsight-gemma-4-good-hackathon-submission.ipynb) shows the full inference + verification pipeline end-to-end and runs on Kaggle's free T4 x2.

To run the verification layer on top of model output, see [`app/agent.py`](app/agent.py).

### Author's deployment (reference)

The public demo runs on [Modal](https://modal.com), which requires a Modal account, a populated `civicinsight-data` volume, and a HuggingFace Secret. Most users will not need to redeploy:

```bash
modal deploy app/io/inference.py   # A100-40GB inference container
modal deploy app/io/web.py         # Gradio + FastAPI web layer
```

## Documentation

- [Grounding architecture](docs/civicinsight-grounding-spec.md): how the model output is paired with rule-based verification against an optional source CSV.
- [Pre-DPO held-out audit](docs/civicinsight-pre-dpo-audit.md): line-by-line review of model failures across five held-out images. Motivates the verification layer.
- [Zero-shot evaluation report](docs/zero-shot-evaluation-report.md): summary of the 27-image base-model audit (9 real-world dashboards + 18 synthetic). Verbatim outputs in `notebooks/kaggle/01-zero-shot-evaluation.ipynb`.
- [Operational runbook](docs/runbook.md): Modal cost / capacity toggles, pre-public-flip checklist, privacy scrub.

## Attribution

Built on [Gemma 4 E4B](https://huggingface.co/google/gemma-4-e4b-it) by Google DeepMind (Apache 2.0). The CivicInsight adapter is MIT-licensed and authored by Faz ([@shahfazal](https://github.com/shahfazal)). Not affiliated with Google.

The DPO training depended on a fix to the DPOTrainer multi-process hang on Gemma 4 vision: bug filed at [unslothai/unsloth#5196](https://github.com/unslothai/unsloth/issues/5196), fix merged at [#5199](https://github.com/unslothai/unsloth/pull/5199) on April 29, 2026.

## License

Code: MIT. See [LICENSE](LICENSE).
Model adapter: MIT. Base Gemma 4 E4B weights: Apache 2.0 (Google).
