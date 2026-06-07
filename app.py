"""Blind Quill — gradio.Server backend for the custom "Invisible Bindery" frontend.

The UI lives in web/ (a React-via-Babel prototype handed off from Claude Design).
Here we serve that frontend and expose the bindery as queued Gradio API endpoints,
so the rich custom UI keeps Gradio's queue, concurrency control, and ZeroGPU.
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path

import gradio as gr
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from gradio import Server

import core
from model_client import ModelClientError
from patcher import PatchApplicationError
from presenter import card_dict, full_story_dict, reveal_dict
from story_store import StoryStoreError
from utils import InputValidationError

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
        result = _guard(core.stitch, story_id, fragment)
        return {"story": full_story_dict(result.story), "reveal": reveal_dict(result)}

    @app.api(name="read_manuscript")
    def read_manuscript(story_id: str) -> dict:
        story = _guard(core.read_sealed, story_id)
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
    app.launch(server_name="0.0.0.0", server_port=_port(), show_error=True)
