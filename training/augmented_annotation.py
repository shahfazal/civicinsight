"""
augmented_annotation.py — Draft ARIA descriptions for civic dashboard screenshots using Claude.

Sends each image to the Claude API and saves a structured JSON draft for human editing.
Resumable: skips images already present in annotations_draft.json.

Usage:
    python3 training/augmented_annotation.py examples/raw/

Requires: ANTHROPIC_API_KEY in .env
"""

import os
import base64
import anthropic
import sys
import json
from dotenv import load_dotenv
import time

load_dotenv()

SYSTEM_PROMPT = (
    "You are an accessibility expert extracting data from civic dashboard screenshots. "
    "Your output will be used as training data to help blind researchers understand French civic data. "
    "Analyze the image carefully and return ONLY a valid JSON object — no markdown, no explanation — with these fields:\n"
    "  chart_type: the type of visualization (e.g. 'Stacked bar chart', 'Choropleth map', 'Line chart')\n"
    "  numbers: list of objects, each with 'label' (where you read it: 'Y-axis', 'X-axis', 'tooltip', 'legend', 'KPI') "
    "           and 'value' (exact as shown on chart). Preserve original formatting (14 600 not 14,600; 2,3% not 2.3%)\n"
    "  layers: describe any visual layering — highlighted segments, faded regions, color bands, selected series\n"
    "  filters: any filters or selections visible — legend pills, dropdown selections, highlighted categories\n"
    "  aria_label: a 2-4 sentence prose description suitable for a screen reader. Include the chart type, "
    "              subject, key numbers with their labels, and the main trend or insight\n"
    "  confidence: 'high', 'medium', or 'low' — your confidence that all numbers are correctly extracted\n"
    "If you cannot read a value with confidence, omit it rather than guess."
)

IMAGE_TYPE = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "bmp": "image/bmp"
}


def annotate(image_path, client):
    with open(image_path, "rb") as f:
        image_data = f.read()

    img64 = base64.b64encode(image_data).decode("utf-8")
    ext = image_path.split(".")[-1]
    img_type = IMAGE_TYPE.get(ext)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img_type,
                        "data": img64,
                    }
                },
                {
                    "type": "text",
                    "text": "Analyze this chart and return the JSON."
                }
            ]
        }]
    )
    return message.content[0].text, message.usage


if __name__ == "__main__":
    client = anthropic.Anthropic()
    folder_path = sys.argv[1]

    draft_file_path = folder_path + "/annotations_draft.json"
    if os.path.exists(draft_file_path):
        with open(draft_file_path) as f:
            results = json.load(f)
    else:
        results = []

    images = [f for f in os.listdir(folder_path) if f.endswith(".png")]
    done = [r["_source_image"] for r in results]

    for image in images:
        if image in done:
            continue
        start = time.time()
        print(f"{image} is being sent ... \n")
        result, usage = annotate(folder_path + "/" + image, client)
        elapsed = time.time() - start
        cost = (usage.input_tokens / 1_000_000) * 3 + (usage.output_tokens / 1_000_000) * 15
        print(f"{image} - {elapsed:.2f}s - ${cost:.4f}")
        if result.startswith("```"):
            result = result.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(result)
        result["_source_image"] = image
        results.append(result)
        with open(draft_file_path, "w") as f:
            json.dump(results, f)
