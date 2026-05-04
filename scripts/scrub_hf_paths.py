"""
One-shot scrub of Modal-volume paths from published HF model artifacts.

Run: python scripts/scrub_hf_paths.py

Effect:
    1. Rewrites adapter_config.json: base_model_name_or_path to unsloth/gemma-4-e4b-it
    2. Deletes training_args.bin (leaks /mnt/civicinsight/checkpoints/... path)
    3. Deletes and recreates v1.0 tag at new main HEAD
    4. Re-audits v1.0 to confirm no Modal paths remain

Idempotent: re-running after a successful scrub is a no-op
(adapter_config.json already correct, training_args.bin already deleted).

The bug being scrubbed: training-time call to FastVisionModel.from_pretrained(
"/mnt/civicinsight/model", ...) caused Unsloth/PEFT to bake the absolute Modal
volume path into adapter_config.json's base_model_name_or_path. External loads
on Kaggle (where no Modal volume exists) fail with HFValidationError.
"""
from __future__ import annotations

import json
import sys
from io import BytesIO

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError

REPO = "shahfazal/civicinsight-gemma4-e4b-it"
EXPECTED_OLD_PATH = "/mnt/civicinsight/model"
NEW_BASE_MODEL = "unsloth/gemma-4-e4b-it"
TAG = "v1.0"
TAG_MESSAGE = (
    "v1.0 (retagged): first canonical CivicInsight release. "
    "SFT on 64 civic-data examples. Modal-volume paths scrubbed from metadata."
)


def main() -> int:
    api = HfApi()

    try:
        api.repo_info(REPO)
    except RepositoryNotFoundError:
        print(f"ERROR: Repo {REPO} not found or not accessible.", file=sys.stderr)
        return 1

    # Step 1: rewrite adapter_config.json
    print("[1/4] Fetching current adapter_config.json from main...")
    config_path = hf_hub_download(
        repo_id=REPO,
        filename="adapter_config.json",
        revision="main",
    )
    with open(config_path) as f:
        config = json.load(f)

    current = config.get("base_model_name_or_path")
    print(f"      Current base_model_name_or_path: {current!r}")

    if current == NEW_BASE_MODEL:
        print("      Already correct. Skipping rewrite.")
    elif current == EXPECTED_OLD_PATH:
        config["base_model_name_or_path"] = NEW_BASE_MODEL
        print(f"      Rewriting to: {NEW_BASE_MODEL!r}")

        api.upload_file(
            path_or_fileobj=BytesIO(
                json.dumps(config, indent=2).encode() + b"\n"
            ),
            path_in_repo="adapter_config.json",
            repo_id=REPO,
            commit_message="fix: scrub local Modal paths from adapter metadata",
        )
        print("      Uploaded.")
    else:
        print(
            f"ERROR: Unexpected current value: {current!r}. "
            f"Expected {EXPECTED_OLD_PATH!r}. Aborting.",
            file=sys.stderr,
        )
        return 1

    # Step 2: delete training_args.bin
    print("[2/4] Deleting training_args.bin...")
    try:
        api.delete_file(
            path_in_repo="training_args.bin",
            repo_id=REPO,
            commit_message="fix: remove training_args.bin (leaks Modal paths)",
        )
        print("      Deleted.")
    except EntryNotFoundError:
        print("      Already absent. Skipping.")

    # Step 3: delete and recreate v1.0 tag
    print(f"[3/4] Moving tag {TAG} to current main HEAD...")
    try:
        api.delete_tag(repo_id=REPO, tag=TAG)
        print(f"      Old {TAG} tag deleted.")
    except EntryNotFoundError:
        print(f"      No existing {TAG} tag.")

    api.create_tag(
        repo_id=REPO,
        tag=TAG,
        revision="main",
        tag_message=TAG_MESSAGE,
    )
    print(f"      New {TAG} tag created at current HEAD.")

    # Step 4: re-audit
    print(f"[4/4] Re-auditing {TAG} for Modal paths...")
    config_path = hf_hub_download(
        repo_id=REPO,
        filename="adapter_config.json",
        revision=TAG,
    )
    with open(config_path) as f:
        post_config = json.load(f)

    bm = post_config.get("base_model_name_or_path")
    if bm == NEW_BASE_MODEL:
        print(f"      OK: adapter_config.json clean (base_model_name_or_path = {bm!r})")
    else:
        print(
            f"      FAIL: adapter_config.json NOT clean: {bm!r}",
            file=sys.stderr,
        )
        return 1

    try:
        hf_hub_download(
            repo_id=REPO,
            filename="training_args.bin",
            revision=TAG,
        )
        print("      FAIL: training_args.bin still present.", file=sys.stderr)
        return 1
    except EntryNotFoundError:
        print("      OK: training_args.bin absent.")

    print("\nDone. v1.0 retagged and clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
