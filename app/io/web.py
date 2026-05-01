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
    max_containers=3 if DEMO_HOT else 2,
                                # CPU-only, cost is symbolic. Aligned with the
                                # inference cap so a request can fan out cleanly
                                # without the web layer becoming the bottleneck.
    cpu=1,
    memory=1024,
)
@modal.asgi_app()
def fastapi_app():
    from fastapi import Depends, FastAPI, HTTPException, status
    from fastapi.security import HTTPBasic, HTTPBasicCredentials
    from gradio.routes import mount_gradio_app

    from app.io.demo import demo

    expected_user = os.environ.get("DEMO_USER", "demo")
    expected_pass = os.environ.get("DEMO_PWD", "")
    is_public = os.environ.get("DEMO_PUBLIC", "0") == "1"

    fast_app = FastAPI()
    security = HTTPBasic()

    def verify_creds(creds: HTTPBasicCredentials = Depends(security)):
        if is_public:
            return
        user_ok = secrets.compare_digest(creds.username, expected_user)
        pass_ok = expected_pass and secrets.compare_digest(creds.password, expected_pass)
        if not (user_ok and pass_ok):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Basic"},
            )

    # mount_gradio_app accepts auth_dependency to gate access. When DEMO_PUBLIC=1
    # is set, verify_creds is a no-op so the URL is fully public (May 13 onward).
    return mount_gradio_app(
        fast_app,
        demo,
        path="/",
        auth_dependency=None if is_public else verify_creds,
    )
