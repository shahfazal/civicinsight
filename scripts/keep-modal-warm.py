"""
Keep Modal inference + web containers warm during a video recording session.

Pings the deployed civicinsight-inference InferenceServer.generate every
5 minutes with a tiny test image. Each ping triggers full vision-encoder
+ short generation, which exercises the GPU container and resets its
scaledown_window timer. Web container stays warm as a side effect since
each Gradio submit also touches it.

Usage:
    python3 scripts/keep-modal-warm.py
    (Ctrl-C to stop)

Cost: ~$0.003 per ping (~5s of A100-40GB time). Over a 3-hour session
that's ~36 pings ~= $0.10.

Assumes both apps deployed with DEMO_HOT=1:
    DEMO_HOT=1 modal deploy app/io/inference.py
    DEMO_HOT=1 modal deploy app/io/web.py

After recording, revert both with plain `modal deploy ...` (no env var).
"""
from __future__ import annotations

import struct
import sys
import time
import zlib
from datetime import datetime

import modal


APP_NAME = "civicinsight-inference"
CLASS_NAME = "InferenceServer"
INTERVAL_SECONDS = 5 * 60


def _make_tiny_png() -> bytes:
    """
    Build a valid 1x1 white PNG using stdlib only (no Pillow dependency).
    The model decodes this fine; we ignore its output. Embedding a hex
    literal turned out to be brittle (off-by-one CRCs/lengths produce
    'broken data stream' from the image processor).
    """
    def chunk(tag: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return length + tag + data + crc

    signature = b"\x89PNG\r\n\x1a\n"
    # IHDR: width=1, height=1, bit-depth=8, color-type=2 (RGB), rest=0
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    # Single white pixel: filter byte 0x00, then RGB(0xff, 0xff, 0xff)
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff", 9))
    iend = chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


TINY_PNG = _make_tiny_png()


def heartbeat() -> None:
    """Look up the deployed InferenceServer and ping it forever."""
    cls = modal.Cls.from_name(APP_NAME, CLASS_NAME)
    server = cls()

    print(f"Heartbeat started against {APP_NAME}.{CLASS_NAME} every {INTERVAL_SECONDS}s")
    print("Press Ctrl-C to stop.\n")

    while True:
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            t0 = time.time()
            server.generate.remote(image_bytes=TINY_PNG, max_new_tokens=8)
            elapsed = time.time() - t0
            print(f"[{ts}] ping OK ({elapsed:.1f}s)", flush=True)
        except Exception as e:
            print(f"[{ts}] ping FAILED: {type(e).__name__}: {e}", flush=True)

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        heartbeat()
    except KeyboardInterrupt:
        print("\nHeartbeat stopped. Remember to revert DEMO_HOT after recording:")
        print("    modal deploy app/io/inference.py")
        print("    modal deploy app/io/web.py")
        sys.exit(0)
