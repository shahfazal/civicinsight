"""
Modal-hosted Gradio web app.

Deploys the existing `app.io.demo.demo` Gradio Interface as a public HTTPS
endpoint via Modal's ASGI app integration. The endpoint is gated by HTTP
Basic auth (credentials in a Modal Secret called `civicinsight-demo-creds`)
until the May 13 cleanup pass flips it public for judges.

Deployment:
  1. One-time secret setup (do this once, before first deploy):
       modal secret create civicinsight-demo-creds \\
           DEMO_USER=demo \\
           DEMO_PWD=<choose a password>

  2. Deploy:
       modal deploy app/io/web.py

  3. Public URL printed by Modal at deploy time. Share URL plus credentials
     with anyone you want to preview. Bots without creds get 401.

  4. On May 13, set the env var DEMO_PUBLIC=1 in the secret (or remove the
     auth dependency in this file) to make the URL fully public.

This file is decoupled from app/io/inference.py so they can be deployed
independently. The Gradio app calls the InferenceServer over Modal's
network, so it relies on the InferenceServer being deployed too.
"""

import os
import secrets

import modal


# Image: same Python deps as inference.py plus gradio for the web layer.
# Kept slim - no GPU libraries needed here, this container is CPU-only.
web_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "gradio>=5.0.0",
        "pandas",
        "pillow==11.3.0",
        "modal",  # to call the InferenceServer
        "slowapi==0.1.9",  # per-IP rate limiting on the FastAPI wrapper
    )
    .add_local_python_source("app", copy=True)
)


# Public-traffic envelope. Tunable here, applied in fastapi_app() below.
#
# MAX_UPLOAD_BYTES: hard cap on Content-Length per request. Civic dashboard
# screenshots are typically 50KB-2MB; 5MB leaves headroom for high-DPI
# captures and the optional CSV upload while rejecting obvious abuse
# (10s-of-MB images, animated payloads) before they reach the GPU.
#
# RATE_LIMITS: generous because Gradio's SSE queue polling counts toward
# the per-IP budget. Tight limits (e.g. "10/minute") would DOS legitimate
# users mid-submission. The body-size cap and Gradio queue ceiling carry
# most of the protection; this catches obvious bot bursts.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
RATE_LIMITS = ["300/minute", "2000/day"]

app = modal.App("civicinsight-web")


# Operational toggle. Set DEMO_HOT=1 in the deploy environment to enable
# judging-friendly settings (longer warm window, more parallel containers).
# Default = cost-protected. Mirrors the toggle in inference.py.
DEMO_HOT = os.environ.get("DEMO_HOT", "0") == "1"


@app.function(
    image=web_image,
    secrets=[modal.Secret.from_name("civicinsight-demo-creds")],
    timeout=180,                # must be > inference timeout (120s) since this
                                # endpoint blocks waiting on a remote inference
                                # call. 180s = 120s inference + 60s buffer for
                                # cold-start + Gradio latency + response assembly.
    scaledown_window=300 if DEMO_HOT else 120,
                                # DEMO_HOT=1: 5 min idle (judging window — avoid
                                # FastAPI/Gradio cold-start fanout when inference
                                # container is already warm).
                                # Default: 2 min idle (cost protection).
    max_containers=1,
                                # MUST stay at 1 regardless of DEMO_HOT. Gradio's
                                # queue is per-container in-memory state. With >1
                                # web container, /queue/join lands on container A
                                # and /queue/data?session_hash=... lands on B,
                                # which has no record of that session, raising 404
                                # mid-SSE-stream and breaking the UI submit flow.
                                # /upload_progress 404s have the same root cause.
                                # Web is CPU-only, single container handles full
                                # demo traffic. Inference container still parallel.
                                # DEMO_HOT toggle for web's max_containers retired.
    cpu=1,
    memory=1024,
)
@modal.asgi_app()
def fastapi_app():
    import base64
    import logging
    import time

    from fastapi import FastAPI, HTTPException, Request, status
    from gradio.routes import mount_gradio_app
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import PlainTextResponse

    from app.io.demo import _CUSTOM_CSS, _CUSTOM_HEAD, _CUSTOM_JS, _THEME, demo

    expected_user = os.environ.get("DEMO_USER", "demo")
    expected_pass = os.environ.get("DEMO_PWD", "")
    is_public = os.environ.get("DEMO_PUBLIC", "0") == "1"

    fast_app = FastAPI()

    # ── Public-traffic hardening ─────────────────────────────────────────
    # Modal proxies inbound requests, so request.client.host is the proxy.
    # Use the first hop in X-Forwarded-For for per-IP keying.
    def real_ip(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    class MaxBodySize(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            cl = request.headers.get("content-length")
            if cl and int(cl) > MAX_UPLOAD_BYTES:
                return PlainTextResponse(
                    f"Payload exceeds {MAX_UPLOAD_BYTES} bytes",
                    status_code=413,
                )
            return await call_next(request)

    access_log = logging.getLogger("civicinsight.access")
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)

    class AccessLog(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            t0 = time.monotonic()
            response = await call_next(request)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            access_log.info(
                f"ts={int(time.time())} ip={real_ip(request)} "
                f"method={request.method} path={request.url.path} "
                f"status={response.status_code} ms={elapsed_ms} "
                f"bytes={request.headers.get('content-length', '-')}"
            )
            return response

    limiter = Limiter(key_func=real_ip, default_limits=RATE_LIMITS)
    fast_app.state.limiter = limiter
    fast_app.add_exception_handler(
        RateLimitExceeded,
        lambda req, exc: PlainTextResponse(
            "Rate limited. Please slow down and try again shortly.",
            status_code=429,
        ),
    )

    # Middleware ordering note: add_middleware is LIFO, so the last add
    # is the outermost. Stack here (outer → inner):
    #   AccessLog       — sees every final response, including 413/429
    #   MaxBodySize     — rejects oversize before rate-limit budget burns
    #   SlowAPIMiddleware — per-IP envelope on what's left
    fast_app.add_middleware(SlowAPIMiddleware)
    fast_app.add_middleware(MaxBodySize)
    fast_app.add_middleware(AccessLog)
    # ─────────────────────────────────────────────────────────────────────

    def verify_creds(request: Request) -> str:
        # Gradio's auth_dependency calls this with a Request directly (not via
        # FastAPI's Depends() resolution), so we parse the Authorization header
        # manually instead of using HTTPBasic. Returns the username on success;
        # raises 401 with WWW-Authenticate: Basic on failure to trigger the
        # browser's Basic-auth dialog.
        if is_public:
            return "anonymous"
        unauthorized = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            raise unauthorized
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            username, _, password = decoded.partition(":")
        except Exception:
            raise unauthorized
        user_ok = secrets.compare_digest(username, expected_user)
        pass_ok = bool(expected_pass) and secrets.compare_digest(password, expected_pass)
        if not (user_ok and pass_ok):
            raise unauthorized
        return username

    # footer_links controls which links render in the Gradio footer. Each
    # entry must be one of "api", "gradio", or "settings". Omitting "api"
    # hides the "Use via API" link without removing the Gradio attribution.
    # See https://www.gradio.app/docs/gradio/mount_gradio_app
    # Combined with api_name=False on the Interface (in app/io/demo.py),
    # this blocks both discovery (no docs page) and the named gradio_client
    # endpoint that bots would target for burst access.
    #
    # theme/css/head/js are forwarded explicitly: gr.Interface stores them
    # as attributes that only take effect on .launch(). The mount path
    # overwrites blocks.theme/css/head/js from these kwargs, so without
    # forwarding the a11y CSS would never reach the browser.
    return mount_gradio_app(
        fast_app,
        demo,
        path="/",
        auth_dependency=None if is_public else verify_creds,
        footer_links=["gradio", "settings"],
        theme=_THEME,
        css=_CUSTOM_CSS,
        head=_CUSTOM_HEAD,
        js=_CUSTOM_JS,
    )
