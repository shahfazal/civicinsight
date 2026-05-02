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

- Cap: **$100** (lowered from $200 default)
- Auto-raise: **disabled**
- Set via Modal dashboard → Workspace settings → Usage & Billing → Plans
- Ceiling protection of last resort. With both functions in cost-protected mode,
  realistic burn over the public window is well under $20.

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

## Pre-public-flip checklist (May 13, 2026)

Day-of tasks, in order:

1. Run privacy scrub on git history and tree (see "Privacy scrub" below)
2. Smoke-test current deploy (confirm cost-protected mode still working)
3. Flip `DEMO_HOT=1` and redeploy both functions
4. Verify with `modal app describe`
5. Set `DEMO_PUBLIC=1` in the `civicinsight-demo-creds` Modal Secret (removes Basic Auth gate)
6. Redeploy `app/io/web.py` to pick up the new secret value
7. Flip HF repo to PUBLIC
8. Push GitHub repo to public remote (pre-push hook auto-disables on or after May 15)
9. Smoke-test the now-public URL anonymously (no Basic Auth prompt)
10. Submit Kaggle entry pointing at the public HF model + Modal demo URL
11. Set calendar reminder for ~May 26 to flip back to cost-protected

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
# Local machine paths
git grep -i "/users/faz" -- ':!**/dist-info/**'
git grep -i "~" -- ':!**/dist-info/**'
git log --all -p | grep -i "/users/faz"

# API keys, tokens, secrets (substrings that often leak)
git grep -i "api[_-]key\|secret\|password\|token" -- ':!docs/**' ':!**/dist-info/**'
git log --all -p | grep -iE "(api[_-]key|sk-[a-z0-9]+|hf_[a-z0-9]+)"

# Personal references in commit messages
git log --all --format="%h %s" | grep -i "faz\|shahfazal" | head

# Modal volume internal paths (acceptable but worth knowing)
git grep "/mnt/civicinsight"
```

### What should be in the public push

- Source code: `app/`, `tests/`, `training/`, `notebooks/`
- Docs: `docs/` (review each for personal context)
- Public-facing README.md
- `.gitignore`, `requirements.txt`, `requirements-exp4c-WORKING.txt`
- `CLAUDE.md` is the project's internal operational doc — review whether to
  publish it. It mentions `~/` paths that you'd want to redact.

### What should NOT be pushed

- Anything in `.gitignore` (already excluded)
- Personal `NOTES.md`, `TODO.md`, `scratch/` (all gitignored)
- API keys, `.env`, `*.key`, `credentials.json` (gitignored)
- The `examples/raw/` directory (large, gitignored, content lives on Modal volume)
- Memory files in `~/.claude/projects/.../memory/` (already outside repo, no risk)

### One-shot scrub script

```bash
echo "=== Local paths in tree ==="
git grep -n "~" || echo "(clean)"
echo ""
echo "=== Local paths in history ==="
git log --all -p 2>/dev/null | grep -c "~" | xargs -I{} echo "  {} occurrences"
echo ""
echo "=== Potentially sensitive substrings in tree ==="
git grep -nE "api[_-]key|secret|password|token|hf_[a-zA-Z0-9]" -- ':!docs/**' || echo "(clean)"
echo ""
echo "=== Personal references in commits ==="
git log --all --format="%h %s" | grep -i "faz" | head -10
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
