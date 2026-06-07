"""Blind Quill orchestration: create, browse, stitch, read.

Pure flow logic that returns backend objects (Story / AppliedPatchResult). The
web layer (app.py) presents these through presenter.py; this module never builds
HTML or knows about the transport. `generate_json` is referenced here so tests
can stub the model without touching production code.
"""

from __future__ import annotations

from model_client import generate_json
from patcher import apply_patch
from prompts import build_plan_graft_messages, build_write_patch_messages
from schemas import AppliedPatchResult, GraftPatch, GraftPlan, Story
from story_store import create_story, get_story, list_stories, save_story
from utils import require_open_for_graft, validate_fragment, validate_story_id


def gallery() -> list[Story]:
    return list_stories()


def create(seed: str) -> Story:
    return create_story(seed)


def capsule(story_id: str) -> Story:
    return get_story(validate_story_id(story_id))


def read_manuscript(story_id: str) -> Story:
    return get_story(validate_story_id(story_id))


def stitch(story_id: str, fragment: str) -> AppliedPatchResult:
    clean_id = validate_story_id(story_id)
    clean_fragment = validate_fragment(fragment)
    story = get_story(clean_id)
    # Refuse a sealed manuscript before spending two model calls on it.
    require_open_for_graft(story.status, story.graft_count, story.max_grafts)
    plan = generate_json(
        build_plan_graft_messages(story, clean_fragment),
        GraftPlan,
        "GraftPlan",
        max_new_tokens=4096,
    )
    patch = generate_json(
        build_write_patch_messages(story, plan, clean_fragment),
        GraftPatch,
        "GraftPatch",
        max_new_tokens=8192,
    )
    result = apply_patch(story, plan, patch, clean_fragment)
    save_story(result.story, expected_updated_at=story.updated_at)
    return result
