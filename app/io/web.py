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
    )
    .add_local_python_source("app", copy=True)
)

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
    from fastapi import FastAPI, HTTPException, Request, status
    from gradio.routes import mount_gradio_app

    from app.io.demo import demo

    expected_user = os.environ.get("DEMO_USER", "demo")
    expected_pass = os.environ.get("DEMO_PWD", "")
    is_public = os.environ.get("DEMO_PUBLIC", "0") == "1"

    fast_app = FastAPI()

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
    return mount_gradio_app(
        fast_app,
        demo,
        path="/",
        auth_dependency=None if is_public else verify_creds,
        footer_links=["gradio", "settings"],
    )
