# CivicInsight: Agentic Retrieval Architecture

**Context:** The Gemma 4 Good Hackathon description explicitly calls for "agentic retrieval to ensure accurate, grounded outputs." This spec adds a grounding layer on top of the fine-tuned E4B model. The Unsloth prize ($10k) rewards the best fine-tuned model. The agentic retrieval layer is what makes the overall submission competitive for the Main Track and Digital Equity prizes.

**Design constraint:** No self-healing retry loops at inference time. A blind user should not wait 2+ minutes for a description. Single-pass extraction, then grounding via data retrieval. Fast path stays fast.

---

## Architecture Overview

```
User Input                          Output
-----------                         ------
[Dashboard Screenshot] (required)   [ARIA Description]
[Source CSV/URL]       (optional)    [Verification Report]
                                    [Confidence Indicators]

                 +-------------------+
                 |   AGENT ROUTER    |
                 | (decides pipeline)|
                 +--------+----------+
                          |
              +-----------+-----------+
              |                       |
     [Image Only Path]      [Image + Data Path]
              |                       |
              v                       v
     +--------+--------+    +--------+--------+
     | Step 1: EXTRACT  |    | Step 1: EXTRACT  |
     | Fine-tuned E4B   |    | Fine-tuned E4B   |
     | Single pass      |    | Single pass      |
     +---------+--------+    +---------+--------+
               |                       |
               v                       v
     +---------+--------+    +---------+--------+
     | Step 2: VALIDATE  |    | Step 2: VALIDATE  |
     | Structure check   |    | Structure check   |
     | (rule-based)      |    | (rule-based)      |
     +---------+--------+    +---------+--------+
               |                       |
               v                       v
     +---------+--------+    +---------+--------+
     | Step 3: FORMAT    |    | Step 3: GROUND    |
     | ARIA output +     |    | Cross-ref CSV     |
     | unverified flag   |    | Flag discrepancies |
     +------------------+    | Correct values     |
                              +---------+--------+
                                        |
                                        v
                              +---------+--------+
                              | Step 4: FORMAT    |
                              | ARIA output +     |
                              | verification      |
                              +------------------+
```

---

## What Makes This Agentic (Not Just a Pipeline)

A static pipeline runs the same steps every time. An agent observes and decides. Here is where the decisions happen:

### Decision 1: Route Selection
The agent inspects the input and selects a path:
- Image only --> unverified extraction path
- Image + CSV --> grounded verification path
- Image + URL --> fetch data first, then grounded path

### Decision 2: Complexity Assessment
After the E4B extraction, the agent inspects the output:
- Single chart detected --> return as-is after validation
- Multi-panel dashboard detected --> decompose description into sections, label each panel
- No chart detected (e.g., a photo, a text document) --> return early with "This does not appear to be a data visualization"

### Decision 3: Confidence Routing
After structure validation:
- All expected fields present (title, chart type, values, trends) --> high confidence, proceed
- Missing numeric values --> flag as "Values could not be extracted from visual encoding. Provide source data for verification."
- Missing chart type --> flag as "Chart type uncertain"

These are genuine conditional branches, not retries. The system's behavior changes based on what it observes.

---

## Component Specs

### 1. Agent Router (`app/agent.py`)

```python
class CivicInsightAgent:
    """Agentic retrieval layer for grounded ARIA descriptions."""

    def __init__(self, model):
        self.model = model  # Fine-tuned Gemma 4 E4B
        self.validator = StructureValidator()
        self.grounder = DataGrounder()

    def run(self, image, source_data=None):
        """Main agent loop. Observes, decides, acts."""

        # Step 1: Extract (single pass, no retry)
        raw_description = self.model.generate(image)

        # Step 2: Validate structure (rule-based, milliseconds)
        validation = self.validator.check(raw_description)

        # Decision: is source data available for grounding?
        if source_data is not None:
            # Step 3a: Ground against real data
            grounded = self.grounder.verify(raw_description, source_data)
            return self.format_output(
                description=grounded.corrected_description,
                confidence=grounded.confidence,
                verification=grounded.report,
                data_status="verified"
            )
        else:
            # Step 3b: Return with unverified flag
            return self.format_output(
                description=raw_description,
                confidence=validation.confidence,
                verification=None,
                data_status="unverified - provide source data for verification"
            )
```

### 2. Structure Validator (`app/validator.py`)

Rule-based, no model calls. Runs in milliseconds.

```python
class StructureValidator:
    """Deterministic checks on model output quality."""

    REQUIRED_FIELDS = ["chart_type", "title"]
    NUMERIC_PATTERN = r'\d+[\d,.]*'

    def check(self, description: str) -> ValidationResult:
        issues = []
        confidence = 1.0

        # Check: does the output contain any numbers?
        numbers_found = re.findall(self.NUMERIC_PATTERN, description)
        if not numbers_found:
            issues.append("No numeric values extracted")
            confidence -= 0.4  # Major quality signal

        # Check: does it mention a chart type?
        chart_types = ["bar", "line", "scatter", "pie", "gauge",
                       "map", "choropleth", "table", "heatmap", "box"]
        has_chart_type = any(ct in description.lower() for ct in chart_types)
        if not has_chart_type:
            issues.append("No chart type identified")
            confidence -= 0.2

        # Check: does it mention trends or comparisons?
        trend_words = ["increase", "decrease", "up", "down", "higher",
                       "lower", "peak", "lowest", "growth", "decline"]
        has_trends = any(tw in description.lower() for tw in trend_words)
        if not has_trends:
            issues.append("No trends or comparisons identified")
            confidence -= 0.1

        # Check: reasonable length (too short = likely failed)
        word_count = len(description.split())
        if word_count < 20:
            issues.append("Description suspiciously short")
            confidence -= 0.3

        return ValidationResult(
            confidence=max(0.0, confidence),
            issues=issues,
            has_numbers=bool(numbers_found),
            number_count=len(numbers_found)
        )
```

### 3. Data Grounder (`app/grounder.py`)

This is the agentic retrieval component. Cross-references model output against source data.

```python
class DataGrounder:
    """Cross-reference extracted values against source data."""

    def verify(self, description: str, source_data) -> GroundingResult:
        """
        Compare model-extracted values against ground truth.
        source_data: pandas DataFrame from uploaded CSV
        """
        # Extract all numbers from the model's description
        extracted_values = self.parse_numbers(description)

        # Extract all numbers from the source CSV
        source_values = self.get_source_values(source_data)

        # Cross-reference: which extracted values appear in source?
        verified = []
        discrepancies = []
        unmatched = []

        for value, context in extracted_values:
            match = self.find_closest_match(value, source_values)
            if match and match.exact:
                verified.append((value, context, "confirmed"))
            elif match and match.close:
                discrepancies.append({
                    "extracted": value,
                    "source": match.value,
                    "context": context,
                    "difference": abs(value - match.value)
                })
            else:
                unmatched.append((value, context))

        # Build corrected description
        corrected = self.apply_corrections(description, discrepancies)

        # Build verification report
        report = self.build_report(verified, discrepancies, unmatched)

        # Confidence based on verification ratio
        total = len(verified) + len(discrepancies) + len(unmatched)
        confidence = len(verified) / total if total > 0 else 0.0

        return GroundingResult(
            corrected_description=corrected,
            confidence=confidence,
            report=report,
            verified_count=len(verified),
            corrected_count=len(discrepancies),
            unverified_count=len(unmatched)
        )
```

### 4. Gradio Demo (`app/demo.py`)

Two upload fields. The second one is what makes this agentic.

```python
import gradio as gr

def process(image, csv_file=None):
    agent = CivicInsightAgent(model)

    source_data = None
    if csv_file is not None:
        source_data = pd.read_csv(csv_file)

    result = agent.run(image, source_data)

    # Format for display
    aria_label = result["description"]
    confidence = f"{result['confidence']:.0%}"
    status = result["data_status"]

    verification = ""
    if result.get("verification"):
        verification = result["verification"]

    return aria_label, confidence, status, verification

demo = gr.Interface(
    fn=process,
    inputs=[
        gr.Image(type="pil", label="Dashboard Screenshot"),
        gr.File(label="Source Data CSV (optional)", file_types=[".csv"])
    ],
    outputs=[
        gr.Textbox(label="ARIA Description"),
        gr.Textbox(label="Confidence"),
        gr.Textbox(label="Data Verification Status"),
        gr.Textbox(label="Verification Report")
    ],
    title="CivicInsight: Accessible Civic Data",
    description="Upload a civic dashboard screenshot to generate an ARIA-ready description. Optionally attach source data for grounded verification."
)
```

---

## What This Means for the Video (70% of Score)

The video story arc has three beats:

**Beat 1 (0:00-0:45): The Problem**
"I spent 20 hours manually writing 84 ARIA attributes for one French elections dashboard. Existing tools generate descriptions like 'Dashboard displaying tourism data' -- useless for a blind researcher who needs actual numbers."

**Beat 2 (0:45-2:00): The Solution**
Live demo. Upload a civic dashboard the model has never seen.
- First: image only. Model generates ARIA description with extracted values. Note the "unverified" flag.
- Then: attach the source CSV. Watch the agent cross-reference, confirm values, catch one that the model got wrong, and correct it. The flag changes to "verified."

**Beat 3 (2:00-2:45): The Vision**
"Every civic dashboard should be accessible. CivicInsight is open source, MIT licensed, runs on Gemma 4 open weights. No API keys, no paywalls. Download and run. This is what Digital Equity looks like."

---

## What This Means for the Writeup (1,500 words)

Structure:

1. **Problem** (200 words): 1.7M blind French citizens, inaccessible dashboards, manual ARIA is unsustainable.
2. **Approach** (300 words): Fine-tuned Gemma 4 E4B via Unsloth. Domain adaptation on civic dashboards. Why open weights matter for accessibility.
3. **Agentic Retrieval** (300 words): The grounding layer. Route selection, validation, CSV cross-reference. Why single-pass + grounding beats retry loops for accessibility UX.
4. **Results** (300 words): Zero-shot failure modes (9 identified). Fine-tuned improvements. Before/after on visually encoded values. Benchmark numbers.
5. **Technical Choices** (200 words): Why E4B (edge-deployable). Why Markdown over JSON. Why deterministic validation. Why not Claude API (paywalled).
6. **Impact** (100 words): Open source, MIT, no paywalls. Reproducible. Extensible to any dashboard platform.

---

## Implementation Priority

For the 26 days remaining:

| Priority | Task | Why |
|----------|------|-----|
| P0 | Dataset creation (50+ examples) | No dataset = no model = no demo |
| P0 | Unsloth fine-tuning on RunPod | Core deliverable for Unsloth prize |
| P0 | Benchmarks (zero-shot vs fine-tuned) | Required by competition |
| P1 | Structure Validator | Rule-based, fast to build, adds "agentic" credential |
| P1 | Data Grounder | The "wow" moment in the video demo |
| P1 | Gradio demo on HF Spaces | Required deliverable (live demo) |
| P1 | Video (3 min) | 70% of score |
| P2 | Writeup (1,500 words) | 30% of score, verification only |
| P2 | Publish weights to HuggingFace | Required if training a model |

**The agentic layer (Validator + Grounder) is P1, not P0.** Get the model working first. The grounding layer makes the demo compelling but doesn't exist without a working model underneath.

---

## File Structure Update

```
civicinsight/
+-- app/
|   +-- agent.py           # CivicInsightAgent (router + orchestration)
|   +-- validator.py        # StructureValidator (rule-based checks)
|   +-- grounder.py         # DataGrounder (CSV cross-reference)
|   +-- demo.py             # Gradio interface
+-- training/
|   +-- standardize_images.py
|   +-- augmented_annotation.py
|   +-- parse_markdown.py
|   +-- dataset.json
+-- examples/
|   +-- raw/
|   +-- standardized/
|   +-- golden_set/
+-- notebooks/
|   +-- fine_tuning.ipynb   # Unsloth training notebook (RunPod)
|   +-- evaluation.ipynb    # Zero-shot vs fine-tuned benchmarks
+-- docs/
|   +-- competition-reference.md
|   +-- technical-writeup.md
+-- README.md
+-- requirements.txt
+-- CLAUDE.md
```
