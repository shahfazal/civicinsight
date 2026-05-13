# CivicInsight: Operational Runbook

Steady-state operational notes. Specs describe one-time work; this file describes
ongoing operations against the deployed Modal app + HF Hub.

---

## Modal cost / capacity toggle (`DEMO_HOT`)

The Modal inference and web functions both read a `DEMO_HOT` env var at deploy
time to switch between two operational modes.

### Modes

| Mode | `DEMO_HOT` | inference scaledown | inference max | web scaledown | web max | Cost ceiling |
|---|---|---|---|---|---|---|
| **Cost-protected (default)** | unset / `0` | 120s | 2 | 120s | 2 | ~$5/hr peak, near-zero idle |
| **Judging-hot** | `1` | 600s | 3 | 300s | 3 | ~$7.50/hr peak |

`timeout` does not change between modes:

- inference: 120s (warm 20-40s + cold-start 30s headroom)
- web: 180s (must be > inference timeout because web blocks on remote inference call)

### Flip ON (judging-hot)

```bash
DEMO_HOT=1 modal deploy app/io/inference.py
DEMO_HOT=1 modal deploy app/io/web.py
```

### Flip OFF (cost-protected)

```bash
modal deploy app/io/inference.py
modal deploy app/io/web.py
```

### Verify which mode is live

```bash
modal app describe civicinsight-inference   # check scaledown_window
modal app describe civicinsight-web         # check scaledown_window
```

- inference scaledown 600 + web scaledown 300 → judging-hot
- inference scaledown 120 + web scaledown 120 → cost-protected

### When to flip ON

- ~24h before public flip / Kaggle submission goes live
- When you expect an attention burst (HN post, blog launch, etc.)
- During active judging windows

### When to flip OFF

- Submission window closed AND no inference calls for 24h+
- Modal usage dashboard shows higher idle burn than expected
- Unconditionally after May 25, 2026 (1 week post-deadline) if you don't want to
  monitor activity

### Forgot-to-flip-back guard

The most likely failure mode is: you flip ON, judging happens, interest tapers, you
forget to flip back, you eat $50 over a quiet two weeks of idle GPU.

Mitigations:

- Calendar reminder for May 26: check Modal usage dashboard; flip OFF if still hot
- `/schedule` agent task at submission+10 days that pings to verify state
- Workspace budget cap stays at $100 (Modal will cut you off before runaway burn)

---

## Modal workspace budget

- Cap: **$100** for the current cycle. Starter plan caps at $200 max.
- Auto-raise: **disabled**.
- Set via Modal dashboard → Workspace settings → Usage & Billing → Overview → Workspace Budget.
- **Enforced kill switch.** The Modal dashboard wording is unambiguous: "Running apps
  will be stopped if usage reaches this limit." Hitting the cap takes the demo down.
- Two ceilings now stack:
  1. Workspace budget (this section), protects against sustained traffic over the
     billing cycle.
  2. `max_containers × per-container $/hr` (set per `@app.function`), protects
     against burst pricing. For CivicInsight inference at DEMO_HOT: A100-40GB × 3 ×
     ~$2.50/hr = ~$7.50/hr peak burn rate.
- **For judging windows where the demo MUST stay up**, consider raising the cap to
  $200 (Starter ceiling) before flipping public. Not because you expect to spend it,
  but because hitting it kills the demo mid-evaluation.

---

## HF Hub state

| Ref | Type | Purpose |
|---|---|---|
| `main` | branch | Default `from_pretrained` revision. Currently at exp4c-sft canonical. |
| `v1.0` | tag (annotated) | Stable pin for reproducible code. Points at the v1 release commit. |

**Repository visibility:** PRIVATE until May 13, 2026. Flip to public on submission day:
1. HF Hub → Settings → Change visibility → Public
2. (Optionally) verify model card renders correctly to anonymous viewers

**Pre-public-flip code references:** code that uses `from_pretrained(...)` should pin
to `revision="v1.0"` for reproducibility, not bare `revision="main"` (which can drift
in future releases). Same for the Kaggle submission notebook.

---

## Deploy commands quick reference

```bash
# Default (cost-protected)
modal deploy app/io/inference.py
modal deploy app/io/web.py

# Judging-hot
DEMO_HOT=1 modal deploy app/io/inference.py
DEMO_HOT=1 modal deploy app/io/web.py

# Verify config
modal app describe civicinsight-inference
modal app describe civicinsight-web

# List all apps in workspace
modal app list
```

---

## Smoke-test the deployed inference

After any deploy, verify with one inference request through the live URL:

1. Open the Modal-hosted Gradio URL (auth-gated until May 13)
2. Upload one test image (e.g., a baseline standardized image)
3. Confirm inference returns within timeout (typically 20-40s warm, ~60s cold)
4. Confirm output starts with `[civicinsight-v1]`

If timeout repeatedly fires for normal images, the timeout was set too aggressively;
investigate which side (inference or web) is timing out via Modal dashboard logs.

---

## Pre-flip warm-up (run before the checklist starts)

Three preparatory passes before kicking off the 15-step checklist:

1. **Sync the canonical Kaggle submission notebook.** The local copy at `notebooks/civicinsight-gemma-4-good-hackathon-submission.ipynb` has edits not yet on Kaggle (verification-pipeline framing, JSON reformat for legible diffs, agent docstring updates). Push:

   ```bash
   kaggle kernels push -p notebooks/
   ```

   See the `reference_kaggle_cli` memory for the auth flow.

2. **Run the Kaggle notebook end-to-end at least twice.** Run All on Kaggle T4 x2 to confirm:
   - Pinned stack installs cleanly (no version drift on Kaggle base image)
   - HF model loads (only works after checklist step 7 if model is still private; pre-step-7, use HF_TOKEN Kaggle Secret)
   - All 5 demos (Demo 0 zero-shot + 4 verification-pipeline demos) produce expected outputs
   - Runtime fits inside Kaggle's 12-hour session ceiling
   - No T4 OOMs across the full pipeline

3. **Modal logistics.**
   - `modal app describe civicinsight-inference` and `modal app describe civicinsight-web`, confirm current state (cost-protected expected; scaledown 120s, max_containers 2)
   - Verify Modal workspace budget is set to **$200** (checklist step 3 bumps this; can be done ahead of time)
   - Glance at Modal dashboard Usage tab for any unexpected burn in the current cycle
   - Confirm `civicinsight-data` volume is healthy and the adapter checkpoint path resolves

---

## Pre-public-flip checklist (May 13, 2026)

Day-of tasks, in order:

1. Run privacy scrub on git history and tree (see "Privacy scrub" below)
2. Smoke-test current deploy (confirm cost-protected mode still working)
3. **Raise the Modal workspace budget to $200** (Starter ceiling) via Modal dashboard → Workspace settings → Usage & Billing → Workspace Budget → Save. The budget is an enforced kill switch (`reference_modal_cost_ceiling`); hitting the cap mid-judging takes the demo down. Headroom is cheap insurance.
4. Flip `DEMO_HOT=1` and redeploy both functions
5. Verify with `modal app describe`
6. Set `DEMO_PUBLIC=1` in the `civicinsight-demo-creds` Modal Secret (removes Basic Auth gate)
7. Redeploy `app/io/web.py` to pick up the new secret value
8. Flip HF repo to PUBLIC
9. **Delete the HF login cells from the canonical Kaggle notebook.** Once the HF model is public, the auth dance is dead code and it _breaks_ anonymous forkers (a judge who clicks Copy & Edit without an HF_TOKEN secret will hit `UserSecretsClient().get_secret("HF_TOKEN")` and crash). On the Kaggle UI for the notebook at `kaggle.com/code/shahfazalmohammed/civicinsight-gemma-4-good-hackathon-submission`:
    - Delete cell 4 (markdown: "### HuggingFace login" header + the body)
    - Delete cell 5 (code: `UserSecretsClient().get_secret("HF_TOKEN")` + `login(token=hf_token)`)
    - Save Version
    - Download via Kaggle UI to overwrite `notebooks/civicinsight-gemma-4-good-hackathon-submission.ipynb` locally; commit so the tracked file matches what's live on Kaggle.
10. Flip the YouTube demo video from private to public (or unlisted at minimum). Confirm the URL plays anonymously in an incognito window.
11. **Final pre-push checks** (run all three; abort the push if anything trips):
    - `git log -10 --format=%B | grep -iE "$HOME|@gmail|@hotmail|@yahoo"`, empty output expected. Squash commit messages are NOT covered by the May 12 privacy scrub since they didn't exist yet.
    - `git ls-files | grep -iE "(\.env|credentials|secret|token)"`, empty output expected.
    - Final tree privacy scrub: re-run the one-shot scrub script below.
12. Push GitHub repo to public remote (pre-push hook auto-disables on or after May 15)
13. Smoke-test the now-public URL anonymously (no Basic Auth prompt)
14. Verify Kaggle notebook prerequisites:
    - Any attached Kaggle datasets the canonical notebook depends on are public and findable by anonymous viewers.
    - The notebook's HF model reference resolves anonymously (only works AFTER step 8 + the step 9 cell deletion).
    - Cover image prepared for Kaggle submission (required to submit per competition rules; ~1200×630 png/jpg).
15. Submit Kaggle entry pointing at the public HF model + Modal demo URL + GitHub repo + writeup. Attach the cover image. Confirm submission status (not draft). **Three tracks in play**, make sure all the relevant selections / flags are set on the form:
    - **Main Track**, automatic; every entry competes.
    - **Impact Track / Digital Equity & Inclusivity**, select this focus area.
    - **Special Technology Track / Unsloth**, flag or tag if the form offers it; the doc says Main + Special Technology are explicitly stackable.

    **After submitting**: copy the Kaggle entry URL, paste it into `README.md` (replace the placeholder Quick link), and push a follow-up commit.
16. Set calendar reminder for ~May 26 to flip back to cost-protected

---

## Privacy scrub (run before public push)

The repo has been local-only since project start. Before flipping to public,
sweep for personal information, secrets, and machine-local paths that may
have leaked into commit messages, source files, or docs.

### What's safe to expose

- Author handle: `shahfazal` (your public GitHub identity, already on HF Hub)
- Real name in author/citation contexts: handled in BibTeX and acknowledgements
- Project paths: `civicinsight/`, `app/`, etc. (intentional)
- Modal app names: `civicinsight-inference`, `civicinsight-web` (already public via
  the demo URL once flipped)
- HF repo name: `shahfazal/civicinsight-gemma4-e4b-it` (already on public HF)

### What needs scrubbing

Run these greps from the repo root and review each hit:

```bash
# Local machine paths ($HOME expands to your absolute home dir)
git grep -i "$HOME" -- ':!**/dist-info/**'
git log --all -p | grep -i "$HOME"

# API keys, tokens, secrets (substrings that often leak)
git grep -i "api[_-]key\|secret\|password\|token" -- ':!docs/**' ':!**/dist-info/**'
git log --all -p | grep -iE "(api[_-]key|sk-[a-z0-9]+|hf_[a-z0-9]+)"

# Personal references in commit messages (substitute your own substrings)
git log --all --format="%h %s" | grep -iE "$USER|@gmail|@hotmail|@yahoo" | head

# Modal volume internal paths (acceptable but worth knowing)
git grep "/mnt/civicinsight"
```

### What should be in the public push

- Source code: `app/`, `tests/`, `training/`, `notebooks/`
- Docs: `docs/` (review each for personal context)
- Public-facing README.md
- `.gitignore`, `requirements.txt`, `requirements-exp4c-WORKING.txt`
- `CLAUDE.md` is the project's internal operational doc, review whether to
  publish it. It mentions absolute home-directory paths that you'd want
  to redact.

### What should NOT be pushed

- Anything in `.gitignore` (already excluded)
- Personal `NOTES.md`, `TODO.md`, `scratch/` (all gitignored)
- API keys, `.env`, `*.key`, `credentials.json` (gitignored)
- The `examples/raw/` directory (large, gitignored, content lives on Modal volume)
- Memory files in `~/.claude/projects/.../memory/` (already outside repo, no risk)

### One-shot scrub script

```bash
echo "=== Local paths in tree ==="
git grep -n "$HOME" || echo "(clean)"
echo ""
echo "=== Local paths in history ==="
git log --all -p 2>/dev/null | grep -c "$HOME" | xargs -I{} echo "  {} occurrences"
echo ""
echo "=== Potentially sensitive substrings in tree ==="
git grep -nE "api[_-]key|secret|password|token|hf_[a-zA-Z0-9]" -- ':!docs/**' || echo "(clean)"
echo ""
echo "=== Personal references in commits ==="
git log --all --format="%h %s" | grep -i "$USER" | head -10
```

If any flagged content is in commit MESSAGES (not just files), the cleanest
remediation is `git filter-repo` (or `git rebase -i` for recent commits).
For content in files, edit + amend or commit a fix.

### When to run

- **First pass:** May 12 evening (day before public flip). Gives you time
  to remediate without deadline pressure.
- **Final pass:** May 13 morning before the actual `git push`.

If anything turns up, fix it locally before the push. The pre-push hook stays
active until midnight May 15 (so accidentally trying to push before May 13
will still be blocked).

---


## Post-judging cleanup (~May 26 or when interest tapers)

1. `modal app describe` to confirm current state
2. If still in judging-hot mode: `modal deploy` both functions without `DEMO_HOT=1`
3. Verify `modal app describe` shows scaledown back at 120
4. Modal dashboard: check Workspace → Usage to confirm idle burn has dropped
