"""
Modal client wrapper for the locked Exp 4b SFT model.

The model lives on Modal in the volume `civicinsight-data` at:
  /mnt/civicinsight/checkpoints/exp4-visionunfrozen/checkpoint-65/

Deployment:
  $ modal deploy app/io/inference.py

After deployment, callers (agent.py) invoke `infer(image_bytes)` which looks
up the deployed class and calls .generate.remote(...). The class uses
@modal.enter() so the model loads once per container and stays warm for ~10
minutes (controlled by scaledown_window). Cold start adds ~30s; warm calls
are ~5 to 30s depending on image complexity.

The decoded output has the chat-template "user / Generate... / model"
prefix stripped so the caller sees only the assistant turn (the prose
starting with [civicinsight-v1]).
"""

import io

import modal


VOLUME_NAME = "civicinsight-data"
MOUNT_PATH = "/mnt/civicinsight"
ADAPTER_PATH = f"{MOUNT_PATH}/checkpoints/exp4-visionunfrozen/checkpoint-65"

DEFAULT_PROMPT = "Generate an aria-label for this data visualization image."

# Image config mirrors notebook 07's install cell. Tighten via pip pin file
# if dependency drift becomes an issue.
modal_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install("unsloth", "pillow==11.3.0")
    .pip_install("transformers", "trl")
)

app = modal.App("civicinsight-inference")
volume = modal.Volume.from_name(VOLUME_NAME)


@app.cls(
    image=modal_image,
    gpu="A100-40GB",           # 40GB VRAM, ~$2.50/hr. A10G ($1.10) was too slow on
                               # long-output charts (rural-vs-urban took 92s warm).
                               # A100-80GB ($4.50) is overkill for 4-bit Gemma 4 E4B.
    volumes={MOUNT_PATH: volume},
    timeout=180,               # hard ceiling per request (was 300). Sized for first-
                               # request "warmup" inference; warm calls complete in ~20-40s.
                               # Abuse cost ceiling: 180s on A10G is ~$0.055/runaway request.
    scaledown_window=600,      # 10 min idle to scale down. DEV VALUE - bumped from
                               # 120 because 2 min was too aggressive for iterative
                               # local testing (got cold-start every time you stepped
                               # away briefly). REVERT to 120 before May 14 to bound
                               # idle GPU cost during the public judging window.
    max_containers=3,          # cap parallel containers at 3. Bounds runaway abuse
                               # (~$7.50/hr peak ceiling) while leaving room for
                               # judges hitting the demo concurrently. With max=1,
                               # observed queue waits of 1-3 min behind in-flight
                               # requests; max=3 effectively eliminates queueing
                               # for typical Kaggle-judging concurrency.
)
class InferenceServer:
    """Holds the loaded model so consecutive calls reuse it."""

    @modal.enter()
    def load_model(self):
        from unsloth import FastVisionModel
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
