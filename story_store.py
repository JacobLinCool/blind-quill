from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from filelock import FileLock

from model_client import generate_json
from prompts import build_create_story_messages
from schemas import (
    Canon,
    Chapter,
    InitialStoryPayload,
    Paragraph,
    Story,
    StorySummary,
)
from utils import new_story_id, utc_now_iso, validate_seed, validate_story_id


class StoryStoreError(RuntimeError):
    pass


def data_dir() -> Path:
    configured = os.environ.get("DATA_DIR")
    if configured:
        return Path(configured)
    persistent_space_dir = Path("/data")
    if persistent_space_dir.exists():
        return persistent_space_dir
    return Path(__file__).resolve().parent / "data"


def store_path() -> Path:
    return data_dir() / "stories.json"


def list_open_stories() -> list[StorySummary]:
    return [summary for summary in list_story_summaries() if summary.status == "open"]


def list_story_summaries() -> list[StorySummary]:
    stories = _read_stories()
    summaries = [_summary_from_story(story) for story in stories.values()]
    return sorted(summaries, key=lambda item: item.updated_at, reverse=True)


def story_exists(story_id: str) -> bool:
    clean_id = validate_story_id(story_id)
    return clean_id in _read_stories()


def get_story(story_id: str) -> Story:
    clean_id = validate_story_id(story_id)
    stories = _read_stories()
    if clean_id not in stories:
        raise StoryStoreError("Story was not found.")
    return stories[clean_id]


def save_story(story: Story, expected_updated_at: str | None = None) -> None:
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".lock")
    with lock:
        stories = _read_stories_unlocked(path)
        existing = stories.get(story.story_id)
        if expected_updated_at is not None:
            if existing is None:
                raise StoryStoreError("Story was not found.")
            if existing.updated_at != expected_updated_at:
                raise StoryStoreError("This manuscript changed while your graft was being stitched. Reload it and try again.")
        stories[story.story_id] = story
        _write_stories_unlocked(path, stories)


def create_story(seed: str) -> Story:
    clean_seed = validate_seed(seed)
    payload = generate_json(
        build_create_story_messages(clean_seed),
        InitialStoryPayload,
        "InitialStoryPayload",
        max_new_tokens=12000,
    )
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".lock")
    with lock:
        stories = _read_stories_unlocked(path)
        story = _story_from_payload(payload, _unique_story_id_from(stories))
        stories[story.story_id] = story
        _write_stories_unlocked(path, stories)
    return story


def create_story_from_payload(payload: InitialStoryPayload) -> Story:
    return _story_from_payload(payload, _unique_story_id())


def _story_from_payload(payload: InitialStoryPayload, story_id: str) -> Story:
    now = utc_now_iso()
    chapters: list[Chapter] = []
    for chapter_index, chapter_payload in enumerate(payload.chapters, start=1):
        chapter_id = f"ch{chapter_index:02d}"
        paragraphs = [
            Paragraph(paragraph_id=f"{chapter_id}_p{paragraph_index:04d}", text=text)
            for paragraph_index, text in enumerate(chapter_payload.paragraphs, start=1)
        ]
        chapters.append(
            Chapter(
                chapter_id=chapter_id,
                title=chapter_payload.title,
                summary=chapter_payload.summary,
                paragraph_seq=len(paragraphs),
                paragraphs=paragraphs,
            )
        )
    return Story(
        story_id=story_id,
        created_at=now,
        updated_at=now,
        status="open",
        max_grafts=30,
        graft_count=0,
        public_capsule=payload.public_capsule,
        canon=Canon(chapters=chapters),
        world_bible=payload.world_bible,
        graft_log=[],
    )


def _read_stories() -> dict[str, Story]:
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".lock")
    with lock:
        return _read_stories_unlocked(path)


def _read_stories_unlocked(path: Path) -> dict[str, Story]:
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StoryStoreError(f"Story store is not valid JSON: {path}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("stories"), dict):
        raise StoryStoreError("Story store must contain a top-level 'stories' object.")

    stories: dict[str, Story] = {}
    for story_id, story_data in payload["stories"].items():
        story = Story.model_validate(story_data)
        if story.story_id != story_id:
            raise StoryStoreError(f"Story key does not match story_id for {story_id}.")
        stories[story_id] = story
    return stories


def _write_stories_unlocked(path: Path, stories: dict[str, Story]) -> None:
    payload: dict[str, Any] = {
        "stories": {
            story_id: story.model_dump(mode="json")
            for story_id, story in sorted(stories.items(), key=lambda item: item[0])
        }
    }
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _summary_from_story(story: Story) -> StorySummary:
    capsule = story.public_capsule
    return StorySummary(
        story_id=story.story_id,
        title=capsule.title,
        genre=capsule.genre,
        tone=capsule.tone,
        short_summary=capsule.short_summary,
        graft_count=story.graft_count,
        max_grafts=story.max_grafts,
        status=story.status,
        updated_at=story.updated_at,
    )


def _unique_story_id() -> str:
    return _unique_story_id_from(_read_stories())


def _unique_story_id_from(existing: dict[str, Story]) -> str:
    for _ in range(16):
        story_id = new_story_id()
        if story_id not in existing:
            return story_id
    raise StoryStoreError("Could not allocate a unique story ID.")
