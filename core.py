"""Blind Quill orchestration: create, browse, stitch, read.

Pure flow logic that returns backend objects (Story / AppliedPatchResult). The
web layer (app.py) presents these through presenter.py; this module never builds
HTML or knows about the transport. `generate_json` is referenced here so tests
can stub the model without touching production code.

`stitch` accepts an optional `on_progress` callback so a slow run (local CPU/MPS)
can stream real progress to the UI. It still returns an AppliedPatchResult
synchronously; progress is a side channel, off by default.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from model_client import generate_json
from observability import RunProfiler
from patcher import apply_patch
from prompts import build_plan_graft_messages, build_write_patch_messages
from schemas import AppliedPatchResult, GraftPatch, GraftPlan, Story
from story_store import create_story, get_story, list_stories, save_story
from utils import require_open_for_graft, validate_fragment, validate_story_id

# A progress event sink. The event dict is documented in `_ProgressEmitter`.
ProgressCallback = Callable[[dict[str, Any]], None]

# The two model stages of a stitch, weighted by token budget so overall progress
# advances proportionally to the work each stage represents.
_STAGES = [
    {
        "key": "planning",
        "phase": "reading",
        "label": "Reading the manuscript and choosing where your fragment belongs",
        "tokens": 4096,
    },
    {
        "key": "writing",
        "phase": "stitching",
        "label": "Stitching your fragment into the canon",
        "tokens": 8192,
    },
]


def gallery() -> list[Story]:
    return list_stories()


def create(seed: str) -> Story:
    return create_story(seed)


def capsule(story_id: str) -> Story:
    return get_story(validate_story_id(story_id))


def read_manuscript(story_id: str) -> Story:
    return get_story(validate_story_id(story_id))


def stitch(
    story_id: str,
    fragment: str,
    on_progress: ProgressCallback | None = None,
    force_cpu: bool = False,
) -> AppliedPatchResult:
    # force_cpu re-runs a ZeroGPU request on the CPU after its per-user quota ran
    # out; it is ignored for local execution, which already picks its device.
    profiler = RunProfiler("stitch", label=f"story={story_id}")
    emitter = _ProgressEmitter(on_progress, profiler)

    with profiler.stage("validate"):
        clean_id = validate_story_id(story_id)
        clean_fragment = validate_fragment(fragment)
        story = get_story(clean_id)
        # Refuse a sealed manuscript before spending two model calls on it.
        require_open_for_graft(story.status, story.graft_count, story.max_grafts)

    emitter.begin_stage(0)
    with profiler.stage("plan"):
        plan = generate_json(
            build_plan_graft_messages(story, clean_fragment),
            GraftPlan,
            "GraftPlan",
            max_new_tokens=_STAGES[0]["tokens"],
            on_step=lambda done, total: emitter.token_step(0, done, total),
            force_cpu=force_cpu,
        )
    profiler.note_message()
    emitter.finish_stage(0)

    emitter.begin_stage(1)
    with profiler.stage("patch"):
        patch = generate_json(
            build_write_patch_messages(story, plan, clean_fragment),
            GraftPatch,
            "GraftPatch",
            max_new_tokens=_STAGES[1]["tokens"],
            on_step=lambda done, total: emitter.token_step(1, done, total),
            force_cpu=force_cpu,
        )
    profiler.note_message()
    emitter.finish_stage(1)

    with profiler.stage("apply"):
        result = apply_patch(story, plan, patch, clean_fragment)
    with profiler.stage("save"):
        save_story(result.story, expected_updated_at=story.updated_at)

    emitter.finishing()
    profiler.summary()
    return result


class _ProgressEmitter:
    """Turns per-stage token counts into overall progress events.

    Emits dicts of the shape::

        {type, stage, phase, label, stageIndex, stageTotal,
         fraction, tokensDone, tokensTotal, etaSeconds, messagesProcessed}

    `fraction` is overall completion in [0, 1]; ETA is derived from elapsed time
    and overall fraction, so it works whether progress is token-driven (local) or
    only stage-driven (ZeroGPU). A no-op when no callback was provided.
    """

    # Apply/save are sub-second; reserve a small tail so 100% means "done".
    _LAST_STAGE_CAP = 0.98

    def __init__(self, on_progress: ProgressCallback | None, profiler: RunProfiler) -> None:
        self.cb = on_progress
        self.profiler = profiler
        self.start = time.perf_counter()
        total_tokens = sum(stage["tokens"] for stage in _STAGES)
        self.weights = [stage["tokens"] / total_tokens for stage in _STAGES]
        self.base: list[float] = []
        running = 0.0
        for weight in self.weights:
            self.base.append(running)
            running += weight
        self._last_overall = 0.0

    def begin_stage(self, index: int) -> None:
        self._emit(index, self.base[index], done=0, total=_STAGES[index]["tokens"])

    def token_step(self, index: int, done: int, total: int) -> None:
        fraction_in = (done / total) if total else 0.0
        self._emit(index, self.base[index] + fraction_in * self.weights[index], done=done, total=total)

    def finish_stage(self, index: int) -> None:
        overall = self.base[index] + self.weights[index]
        is_last = index == len(_STAGES) - 1
        self._emit(
            index,
            min(overall, self._LAST_STAGE_CAP) if is_last else overall,
            done=_STAGES[index]["tokens"],
            total=_STAGES[index]["tokens"],
        )

    def finishing(self) -> None:
        self._emit(len(_STAGES), 1.0)

    def _emit(self, stage_index: int, overall: float, done: int | None = None, total: int | None = None) -> None:
        if self.cb is None:
            return
        # Clamp to [0, 1] and never report a fraction below the last one, so the
        # progress bar only ever moves forward.
        overall = max(0.0, min(1.0, overall))
        overall = max(overall, self._last_overall)
        self._last_overall = overall
        elapsed = time.perf_counter() - self.start
        eta = elapsed * (1.0 - overall) / overall if overall > 0.02 else None

        if stage_index < len(_STAGES):
            stage = _STAGES[stage_index]
            display_index = stage_index + 1
        else:
            stage = {"key": "finishing", "phase": "stitching", "label": "Finishing the stitch"}
            display_index = len(_STAGES)

        self.cb(
            {
                "type": "progress",
                "stage": stage["key"],
                "phase": stage["phase"],
                "label": stage["label"],
                "stageIndex": display_index,
                "stageTotal": len(_STAGES),
                "fraction": round(overall, 4),
                "tokensDone": done,
                "tokensTotal": total,
                "etaSeconds": round(eta, 1) if eta is not None else None,
                "messagesProcessed": self.profiler.messages,
            }
        )
