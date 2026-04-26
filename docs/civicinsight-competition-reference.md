# CivicInsight: Gemma 4 Good Hackathon -- Competition Reference

**Source:** https://www.kaggle.com/competitions/gemma-4-good-hackathon
**Sponsor:** Google LLC
**Prize Pool:** $200,000
**Start:** April 2, 2026
**Deadline:** May 18, 2026, 11:59 PM UTC
**Personal Deadline:** May 15, 2026

---

## 1. Description

Every challenge has a perfect match, and the clock is ticking. Real innovation happens when we build for the places that need it most. This might be a classroom with spotty internet, a medical site far from a data center, or a community where privacy is non-negotiable.

With the release of Gemma 4, a new family of open models is officially in your hands. Leverage local frontier intelligence, native function calling, and multimodal understanding to tackle the issues that affect your community.

### Focus Areas

- **Health & Sciences:** Bridge the gap between humans and data. Build tools that accelerate discovery or democratize knowledge.
- **Global Resilience:** Build the systems of tomorrow -- from offline, edge-based disaster response to long-range climate mitigation.
- **Future of Education:** Reimagine the learning journey by building multi-tool agents that adapt to the individual and empower the educator.
- **Digital Equity & Inclusivity:** Break down barriers through linguistic diversity, intuitive interfaces, and tools that help close the AI skills gap.
- **Safety & Trust:** Pioneer frameworks for transparency and reliability, ensuring AI remains grounded and explainable.

### What They Want to See

- How you enhance Gemma 4 models through post-training, domain adaptation, and agentic retrieval.
- Optimizing E2B/E4B for edge-based solutions OR deploying 26B/31B for complex tasks.
- If training a model: publish weights and benchmarks.
- If building an app: explain architecture and demonstrate real-world utility via functional demo.
- Tell a story. Show the problem and how your Gemma 4 application solves it.
- The "wow" factor: technical execution is vital, but the ability to communicate your vision through a compelling video and writeup is what sets winners apart.

---

## 2. Submission Requirements

A valid submission must contain:

### a. Kaggle Writeup
- 1,500 words max (penalty if exceeded).
- Blog/paper-style technical report.
- Must explain: architecture, how Gemma 4 was used, challenges overcome, why technical choices were right.
- Primary purpose: prove to judges that the video demo is backed by real engineering.
- Must select a Track.
- Cover image required.

### b. Video (attached to Media Gallery)
- **THIS IS THE MOST IMPORTANT PART.**
- 3 minutes or less.
- Published to YouTube, publicly viewable without login.
- Goal: tell a story, show the problem, demonstrate how Gemma 4 app solves it.

### c. Public Code Repository
- Link to GitHub or Kaggle Notebook.
- Well-documented, clearly shows Gemma 4 implementation.
- Publicly accessible, no login or paywall.
- "Source of Truth" -- used to validate authenticity.

### d. Live Demo
- URL or files for working demo.
- Publicly accessible, no login or paywall.
- Allows judges to experience the project firsthand.

### e. Media Gallery
- Images and/or videos.
- Cover image required to submit.

### Submission Mechanics
- One submission per team.
- Can un-submit, edit, and re-submit unlimited times before deadline.
- Draft/un-submitted writeups at deadline will NOT be considered.

---

## 3. Tracks & Awards

### Main Track -- $100,000
Best overall projects (vision + technical execution + real-world impact).

| Place  | Prize   |
|--------|---------|
| First  | $50,000 |
| Second | $25,000 |
| Third  | $15,000 |
| Fourth | $10,000 |

### Impact Track -- $50,000
One prize per focus area, $10,000 each:
- Health & Sciences
- Global Resilience
- Future of Education
- **Digital Equity & Inclusivity** << CivicInsight target
- Safety & Trust

### Special Technology Track -- $50,000
$10,000 each. **Projects can win BOTH Main Track AND Special Technology.**

- **Cactus:** Best local-first mobile/wearable app routing tasks between models.
- **LiteRT:** Best use of Google AI Edge's LiteRT implementation.
- **llama.cpp:** Best implementation on resource-constrained hardware.
- **Ollama:** Best project running Gemma 4 locally via Ollama.
- **Unsloth:** Best fine-tuned Gemma 4 model using Unsloth, optimized for a specific impactful task. << CivicInsight target

---

## 4. Evaluation Criteria

| Criteria                        | Points | Description |
|---------------------------------|--------|-------------|
| Impact & Vision                 | 40     | How clearly/compellingly does the project address a real-world problem? Is the vision inspiring? Tangible potential for positive change? |
| Video Pitch & Storytelling      | 30     | How exciting, engaging, and well-produced is the video? Does it tell a powerful story? |
| Technical Depth & Execution     | 30     | How innovative is the use of Gemma 4's features? Is the tech real, functional, well-engineered, and not faked? |

**Key insight:** 70% of the score is the video (Impact + Storytelling). Technical execution is verification.

---

## 5. Key Rules for CivicInsight

- **External data allowed:** Must be publicly available and equally accessible to all participants at no cost.
- **Winner license:** CC-BY 4.0 (compatible with MIT repo and Apache 2.0 Gemma weights).
- **Winner obligations:** Must deliver final model code, training code, inference code, computational environment description, and reproducibility documentation.
- **No competition data provided:** Bring your own everything.
- **Solo entry:** Max team size 5, solo is fine.
- **Taxes:** Prizes are taxable income. US residents receive IRS Form 1099.

---

## 6. CivicInsight Prize Surface

Three simultaneous targets:

1. **Main Track** (up to $50k) -- competing against all entries
2. **Digital Equity & Inclusivity** ($10k) -- screen reader accessibility for civic data
3. **Unsloth Special Technology** ($10k) -- fine-tuned Gemma 4 via Unsloth for specific impactful task

Prizes stack: Main + Special Technology confirmed stackable.

---

## 7. CivicInsight Deliverables Checklist

- [ ] Fine-tuned model published: huggingface.co/shahfazal/civicinsight-gemma4-e4b-it
- [ ] Benchmarks: zero-shot vs fine-tuned on 9 failure modes
- [ ] GitHub repo: github.com/shahfazal/civicinsight (well-documented)
- [ ] Training log: GPU type, Unsloth version, hyperparameters, dataset
- [ ] Dataset: publicly published (HuggingFace or Kaggle)
- [ ] Gradio demo: HuggingFace Space, public, no login
- [ ] YouTube video: 3 min max, problem story + live demo
- [ ] Kaggle writeup: 1,500 words, Digital Equity track, cover image
- [ ] Media gallery: cover image + supporting screenshots

---

## 8. Time Allocation Guide (based on 70/30 scoring split)

| Activity | % of remaining time | Notes |
|----------|-------------------|-------|
| Dataset creation + training + validation | ~55% | The tech must be real |
| Video scripting + recording + editing | ~20% | Don't leave for last day |
| Gradio demo on HF Spaces | ~5% | Half a day, reuse Landsat Letters pattern |
| Writeup (1,500 words) | ~10% | Architecture, Gemma 4 usage, challenges |
| Submission assembly + buffer | ~10% | Kaggle writeup, attachments, testing |
