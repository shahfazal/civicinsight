"""
Modal client wrapper for the canonical v1 model (exp4c-sft).

The model lives on Modal in the volume `civicinsight-data` at:
  /mnt/civicinsight/checkpoints/exp4c-sft/checkpoint-80/

Deployment:
  $ modal deploy app/io/inference.py

After deployment, callers (agent.py) invoke `infer(image_bytes)` which looks
up the deployed class and calls .generate.remote(...). The class uses
@modal.enter() so the model loads once per container and stays warm for
~2 min idle (controlled by scaledown_window). Cold start adds ~30s; warm
calls are ~5 to 30s depending on image complexity.

The decoded output has the chat-template "user / Generate... / model"
prefix stripped so the caller sees only the assistant turn (the prose
starting with [civicinsight-v1]).
"""

import io
import os
import struct
import zlib

import modal


VOLUME_NAME = "civicinsight-data"
MOUNT_PATH = "/mnt/civicinsight"
ADAPTER_PATH = f"{MOUNT_PATH}/checkpoints/exp4c-sft/checkpoint-80"

DEFAULT_PROMPT = "Generate an aria-label for this data visualization image."

# Operational toggle. Set DEMO_HOT=1 in the deploy environment to enable
# judging-friendly settings (longer warm window, more parallel containers).
# Default = cost-protected. See docs/runbook.md "Modal cost / capacity
# toggle (DEMO_HOT)" section for details.
DEMO_HOT = os.environ.get("DEMO_HOT", "0") == "1"

# Image versions pinned to match the exp4c-sft training run (07c notebook,
# Apr 28), source: requirements-exp4c-WORKING.txt (pip freeze captured by
# 07c cell 19 at end of training).
#
# These pins control adapter-shape compatibility at load time. The critical
# trio is unsloth, unsloth-zoo, peft — they jointly determine which modules
# get LoRA wrappers when FastVisionModel.from_pretrained reconstructs the
# model. Drift in any of these can produce partial adapter loads (missing
# layer-24-41 k_proj/v_proj weights), where the runtime model expects more
# LoRA modules than the saved checkpoint provides.
modal_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    .pip_install(
        "unsloth==2026.4.8",
        "unsloth-zoo==2026.4.9",
        # transformers must be <=5.5.0 per unsloth-zoo 2026.4.9's dep
        # constraint. The pip freeze in requirements-exp4c-WORKING.txt
        # captured 5.7.0 from a different kernel state that violated this
        # constraint; the 07c training log empirically confirms 5.5.0.
        "transformers==5.5.0",
        "trl==0.22.2",
        "peft==0.19.1",
        "torch==2.10.0",
        "torchvision==0.25.0",
        "bitsandbytes==0.49.2",
        "accelerate==1.10.1",
        "safetensors==0.7.0",
        "huggingface-hub==1.12.0",
        "pillow==11.3.0",
    )
)

app = modal.App("civicinsight-inference")
volume = modal.Volume.from_name(VOLUME_NAME)


@app.cls(
    image=modal_image,
    gpu="A100-40GB",           # 40GB VRAM, ~$2.50/hr. A10G ($1.10) was too slow on
                               # long-output charts (rural-vs-urban took 92s warm).
                               # A100-80GB ($4.50) is overkill for 4-bit Gemma 4 E4B.
    volumes={MOUNT_PATH: volume},
    timeout=120,               # hard ceiling per request. Warm calls complete in
                               # ~20-40s; cold start adds ~30s. 120s leaves headroom
                               # for worst-case cold-start while bounding runaway
                               # generation cost (~$0.09/runaway request on A100-40GB).
    scaledown_window=600 if DEMO_HOT else 120,
                               # DEMO_HOT=1: 10 min idle (judging window — keep warm
                               # between bursts so judges don't eat cold starts).
                               # Default: 2 min idle (cost protection during quiet
                               # periods).
    max_containers=3 if DEMO_HOT else 2,
                               # DEMO_HOT=1: 3 containers, ~$7.50/hr peak ceiling,
                               # zero queueing for typical judging concurrency.
                               # Default: 2 containers, ~$5/hr peak, rare queueing.
)
class InferenceServer:
    """Holds the loaded model so consecutive calls reuse it."""

    @modal.enter()
    def load_model(self):
        import warnings

        from unsloth import FastVisionModel

        # PEFT prints a UserWarning about missing adapter keys for layers 24-41
        # k_proj/v_proj. This is expected and benign: the SFT checkpoint
        # legitimately does not contain those slots (matformer-aware
        # target_modules resolution at training time). The model loads
        # correctly on the layers that were trained. Suppressing so Modal
        # function logs stay readable. Parallels the Kaggle notebook.
        warnings.filterwarnings(
            "ignore",
            message="Found missing adapter keys",
            category=UserWarning,
        )

        self.model, self.tokenizer = FastVisionModel.from_pretrained(
            ADAPTER_PATH,
            load_in_4bit=True,
        )
        FastVisionModel.for_inference(self.model)

    @modal.method()
    def generate(
        self,
        image_bytes: bytes,
        prompt: str = DEFAULT_PROMPT,
        max_new_tokens: int = 600,
    ) -> str:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))

        message = [{
            "role": "user",
            "content": [
                {"type": "image", "image": img},
                {"type": "text", "text": prompt},
            ],
        }]

        inputs = self.tokenizer.apply_chat_template(
            message,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.model.device)

        # do_sample=False forces greedy decoding for byte-stable output across
        # runs. Without this, Gemma 4's default generation_config samples, so
        # the same image yields different descriptions on repeat calls. The
        # public demo and the verification narrative both rely on determinism.
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
        )
        decoded = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return strip_chat_wrapping(decoded)


def strip_chat_wrapping(decoded: str) -> str:
    """
    Remove the chat-template wrapping ("user / prompt / model") and return
    only the assistant turn. Looks for the literal "model\\n" delimiter that
    Gemma's chat template produces after skip_special_tokens=True.
    """
    if "model\n" in decoded:
        return decoded.split("model\n", 1)[1].strip()
    return decoded.strip()


def infer(image_bytes: bytes, prompt: str = DEFAULT_PROMPT) -> str:
    """
    Local-side entry point. Looks up the deployed InferenceServer class and
    invokes its generate method. Raises a Modal lookup error if the function
    has not been deployed yet (run `modal deploy app/io/inference.py`).
    """
    server_cls = modal.Cls.from_name("civicinsight-inference", "InferenceServer")
    return server_cls().generate.remote(image_bytes, prompt)


# 1x1 white PNG built with stdlib only (no Pillow needed in the heartbeat
# image). Same approach used by scripts/keep-modal-warm.py for the
# laptop-side variant.
def _make_tiny_png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return length + tag + data + crc

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff", 9))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


WEB_URL = "https://shahfazal--civicinsight-web-fastapi-app.modal.run/"

# Scheduled heartbeat. Only attached when DEMO_HOT=1, so post-judging
# redeploys without DEMO_HOT remove the schedule automatically. Each tick
# resets the scaledown timers on both the inference (GPU) and web (CPU)
# containers — judges who arrive at random times across the judging window
# always land on warm containers. Cost: ~5s of A100-40GB + a CPU HEAD every
# 4 minutes = ~$1/day.
_HEARTBEAT_KWARGS = (
    {"schedule": modal.Period(minutes=4)} if DEMO_HOT else {}
)


@app.function(
    image=modal.Image.debian_slim(python_version="3.12").pip_install("httpx==0.28.1"),
    timeout=60,
    **_HEARTBEAT_KWARGS,
)
def heartbeat():
    """Keep inference and web containers warm during judging windows."""
    import httpx

    # 1. Warm inference: invoke our own GPU container via .remote().
    # InferenceServer is in the same app so we can reference it directly.
    try:
        InferenceServer().generate.remote(
            image_bytes=_make_tiny_png(),
            max_new_tokens=8,
        )
    except Exception as exc:
        print(f"heartbeat: inference warmup failed: {type(exc).__name__}: {exc}")

    # 2. Warm web: HEAD the Gradio URL so its scaledown timer resets too.
    # Failure here is non-fatal; inference warmup is the costly one we care
    # about.
    try:
        httpx.head(WEB_URL, timeout=30.0)
    except Exception as exc:
        print(f"heartbeat: web warmup failed: {type(exc).__name__}: {exc}")
