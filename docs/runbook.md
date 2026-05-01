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

1. Smoke-test current deploy (confirm cost-protected mode still working)
2. Flip `DEMO_HOT=1` and redeploy both functions
3. Verify with `modal app describe`
4. Set `DEMO_PUBLIC=1` in the `civicinsight-demo-creds` Modal Secret (removes Basic Auth gate)
5. Redeploy `app/io/web.py` to pick up the new secret value
6. Flip HF repo to PUBLIC
7. Smoke-test the now-public URL anonymously (no Basic Auth prompt)
8. Submit Kaggle entry pointing at the public HF model + Modal demo URL
9. Set calendar reminder for ~May 26 to flip back to cost-protected

---

## Post-judging cleanup (~May 26 or when interest tapers)

1. `modal app describe` to confirm current state
2. If still in judging-hot mode: `modal deploy` both functions without `DEMO_HOT=1`
3. Verify `modal app describe` shows scaledown back at 120
4. Modal dashboard: check Workspace → Usage to confirm idle burn has dropped
