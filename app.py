"""Blind Quill — gradio.Server backend for the custom "Invisible Bindery" frontend.

The UI lives in web/ as the production React-via-Babel frontend.
Here we serve that frontend and expose the bindery as queued Gradio API endpoints,
so the rich custom UI keeps Gradio's queue, concurrency control, and ZeroGPU.

`stitch` is a streaming generator endpoint: it yields progress events while the
editor works and a final result event, so slow local (CPU/MPS) runs show real
progress. The Gradio JS client consumes the stream via `submit`.
"""

from __future__ import annotations

import os
import queue
import threading
import traceback
from pathlib import Path
from typing import Iterator

import gradio as gr
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from gradio import Server

import core
from model_client import ModelClientError, execution_mode
from observability import configure_logging, get_logger
from patcher import PatchApplicationError
from presenter import card_dict, full_story_dict, reveal_dict
from story_store import StoryStoreError
from utils import InputValidationError

configure_logging()

WEB_DIR = Path(__file__).resolve().parent / "web"

_USER_FACING_ERRORS = (
    InputValidationError,
    StoryStoreError,
    PatchApplicationError,
    ModelClientError,
    ValueError,
)


def _guard(call, *args, **kwargs):
    """Run a flow, converting known failures into client-visible gr.Error messages."""
    try:
        return call(*args, **kwargs)
    except gr.Error:
        raise
    except _USER_FACING_ERRORS as exc:
        raise gr.Error(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - last-resort guard for the API layer
        traceback.print_exc()
        raise gr.Error("The bindery hit an internal error. Please try again.") from exc


def _to_user_error(exc: BaseException) -> gr.Error:
    if isinstance(exc, gr.Error):
        return exc
    if isinstance(exc, _USER_FACING_ERRORS):
        return gr.Error(str(exc))
    traceback.print_exc()
    return gr.Error("The bindery hit an internal error. Please try again.")


def _result_event(result) -> dict:
    return {"type": "result", "story": full_story_dict(result.story), "reveal": reveal_dict(result)}


# Message fragments that ZeroGPU uses when a user's own quota (or credits) is
# spent. These are recoverable per-user limits, so we fall back to CPU rather
# than surfacing them as errors. See spaces/zero/client.py.
_QUOTA_MARKERS = ("quota exceeded", "credits exceeded", "exceeded your", "runs limit")

_CPU_FALLBACK_NOTICE = (
    "No ZeroGPU quota for this session — running locally on CPU. This is slower; "
    "the progress below is live."
)


def _is_quota_error(exc: BaseException) -> bool:
    if not isinstance(exc, gr.Error):
        return False
    text = " ".join(
        str(part) for part in (getattr(exc, "title", ""), getattr(exc, "message", ""), exc)
    ).lower()
    return any(marker in text for marker in _QUOTA_MARKERS)


def _stream_stitch(story_id: str, fragment: str, force_cpu: bool, notice: str | None = None) -> Iterator[dict]:
    """Run `core.stitch` in a worker thread and stream its progress events.

    Used for in-process execution (local CUDA/MPS/CPU, or the CPU fallback after
    a ZeroGPU quota miss). A worker thread is safe here precisely because no
    `@spaces.GPU` call is involved — that path must stay on the request thread.
    `notice` is attached to every event so the UI can explain a fallback.
    """
    events: "queue.Queue" = queue.Queue()
    done = object()
    holder: dict = {}

    def worker() -> None:
        try:
            holder["result"] = core.stitch(
                story_id, fragment, on_progress=events.put, force_cpu=force_cpu
            )
        except BaseException as exc:  # noqa: BLE001 - surfaced to the main thread below
            holder["error"] = exc
        finally:
            events.put(done)

    thread = threading.Thread(target=worker, name="bq-stitch", daemon=True)
    thread.start()
    while True:
        event = events.get()
        if event is done:
            break
        yield {**event, "notice": notice} if notice else event
    thread.join()

    if "error" in holder:
        raise holder["error"]
    yield _result_event(holder["result"])


def _stitch_events(story_id: str, fragment: str) -> Iterator[dict]:
    """Yield progress events then a result event for one stitch.

    On a ZeroGPU Space the stitch is attempted synchronously on the request
    thread (ZeroGPU needs that thread's context to bill the right user). If the
    user's per-user quota is spent, ZeroGPU raises and we transparently re-run on
    CPU with live streamed progress. Local execution always streams.
    """
    try:
        if execution_mode() == "zerogpu":
            try:
                # Fast path: the user has quota, generation runs on the GPU.
                result = core.stitch(story_id, fragment)
                yield _result_event(result)
                return
            except gr.Error as exc:
                if not _is_quota_error(exc):
                    raise
                get_logger().warning("ZeroGPU quota exhausted for this request; falling back to CPU.")
            yield from _stream_stitch(story_id, fragment, force_cpu=True, notice=_CPU_FALLBACK_NOTICE)
            return

        yield from _stream_stitch(story_id, fragment, force_cpu=False)
    except gr.Error:
        raise
    except BaseException as exc:  # noqa: BLE001 - convert to a client-visible error
        raise _to_user_error(exc) from exc


def build_server() -> Server:
    app = Server(title="Blind Quill")

    @app.api(name="list_stories")
    def list_stories() -> dict:
        stories = _guard(core.gallery)
        return {"stories": [card_dict(story) for story in stories]}

    @app.api(name="get_capsule")
    def get_capsule(story_id: str) -> dict:
        story = _guard(core.capsule, story_id)
        return {"story": card_dict(story)}

    @app.api(name="create_story", concurrency_limit=1, concurrency_id="bindery")
    def create_story(seed: str) -> dict:
        story = _guard(core.create, seed)
        return {"story": full_story_dict(story)}

    @app.api(name="stitch", concurrency_limit=1, concurrency_id="bindery")
    def stitch(story_id: str, fragment: str) -> dict:
        # A generator endpoint: each yield streams to the client via `submit`.
        yield from _stitch_events(story_id, fragment)

    @app.api(name="read_manuscript")
    def read_manuscript(story_id: str) -> dict:
        story = _guard(core.read_manuscript, story_id)
        return {"story": full_story_dict(story)}

    app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")

    @app.get("/", response_class=HTMLResponse)
    def homepage() -> str:
        return (WEB_DIR / "index.html").read_text(encoding="utf-8")

    return app


def _port() -> int:
    for key in ("GRADIO_SERVER_PORT", "PORT"):
        value = os.environ.get(key)
        if value:
            try:
                return int(value)
            except ValueError:
                pass
    return 7860


def _should_launch() -> bool:
    if os.environ.get("BQ_NO_LAUNCH") == "1":
        return False
    # Run as a script locally, or imported by the Hugging Face Spaces runtime.
    return __name__ == "__main__" or bool(os.environ.get("SPACE_ID"))


app = build_server()

if _should_launch():
    get_logger().info("Launching Blind Quill on port %d (execution=%s)", _port(), execution_mode())
    app.launch(server_name="0.0.0.0", server_port=_port(), show_error=True)
