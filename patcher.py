from __future__ import annotations

from schemas import (
    AppliedPatchResult,
    CharacterFact,
    Chapter,
    GraftPatch,
    GraftPlan,
    GraftRecord,
    Paragraph,
    PublicCapsule,
    Story,
    WorldBible,
)
from utils import new_graft_id, require_open_for_graft, utc_now_iso


class PatchApplicationError(ValueError):
    pass


def apply_patch(story: Story, plan: GraftPlan, patch: GraftPatch, user_fragment: str) -> AppliedPatchResult:
    require_open_for_graft(story.status, story.graft_count, story.max_grafts)
    _validate_patch_matches_plan(plan, patch)

    updated = story.model_copy(deep=True)
    chapter = _find_chapter(updated, plan.target_chapter_id)
    target_indexes = _target_indexes(chapter, plan.target_paragraph_ids, plan.insertion_mode)
    generated = _new_paragraphs(chapter, patch.replacement_paragraphs)

    if plan.insertion_mode == "replace":
        start = target_indexes[0]
        end = target_indexes[-1] + 1
        chapter.paragraphs[start:end] = generated
    elif plan.insertion_mode == "insert_before":
        chapter.paragraphs[target_indexes[0]:target_indexes[0]] = generated
    elif plan.insertion_mode == "insert_after":
        insert_at = target_indexes[-1] + 1
        chapter.paragraphs[insert_at:insert_at] = generated
    elif plan.insertion_mode == "append_to_chapter":
        chapter.paragraphs.extend(generated)
    else:
        raise PatchApplicationError(f"Unsupported insertion mode: {plan.insertion_mode}")

    chapter.summary = patch.updated_chapter_summary
    capsule_before = updated.public_capsule
    updated.public_capsule = PublicCapsule(
        title=capsule_before.title,
        genre=capsule_before.genre,
        tone=capsule_before.tone,
        short_summary=patch.public_capsule_patch.short_summary,
        visible_characters=patch.public_capsule_patch.visible_characters,
        open_questions=patch.public_capsule_patch.open_questions,
    )
    updated.world_bible = _merge_world_bible(updated.world_bible, patch)

    now = utc_now_iso()
    generated_ids = [paragraph.paragraph_id for paragraph in generated]
    graft_record = GraftRecord(
        graft_id=new_graft_id(),
        created_at=now,
        user_fragment=user_fragment,
        target_chapter_id=plan.target_chapter_id,
        target_paragraph_ids=list(plan.target_paragraph_ids),
        insertion_mode=plan.insertion_mode,
        generated_paragraph_ids=generated_ids,
        public_reveal=patch.public_reveal,
        editor_rationale_for_player=patch.editor_rationale_for_player,
        capsule_before=capsule_before,
        capsule_after=updated.public_capsule,
    )
    updated.graft_log.append(graft_record)
    updated.graft_count += 1
    updated.updated_at = now
    if updated.graft_count >= updated.max_grafts:
        updated.status = "sealed"

    return AppliedPatchResult(
        story=updated,
        graft_record=graft_record,
        target_chapter_title=chapter.title,
        highlight_paragraph_ids=generated_ids,
    )


def _validate_patch_matches_plan(plan: GraftPlan, patch: GraftPatch) -> None:
    if patch.target_chapter_id != plan.target_chapter_id:
        raise PatchApplicationError("Patch target chapter does not match the graft plan.")
    if patch.insertion_mode != plan.insertion_mode:
        raise PatchApplicationError("Patch insertion mode does not match the graft plan.")
    if patch.target_paragraph_ids != plan.target_paragraph_ids:
        raise PatchApplicationError("Patch target paragraphs do not match the graft plan.")


def _find_chapter(story: Story, chapter_id: str) -> Chapter:
    for chapter in story.canon.chapters:
        if chapter.chapter_id == chapter_id:
            return chapter
    raise PatchApplicationError(f"Target chapter does not exist: {chapter_id}")


def _target_indexes(chapter: Chapter, target_ids: list[str], mode: str) -> list[int]:
    if mode == "append_to_chapter":
        if target_ids:
            _ordered_contiguous_indexes(chapter, target_ids)
        return []
    if not target_ids:
        raise PatchApplicationError(f"{mode} requires at least one target paragraph.")
    return _ordered_contiguous_indexes(chapter, target_ids)


def _ordered_contiguous_indexes(chapter: Chapter, target_ids: list[str]) -> list[int]:
    id_to_index = {paragraph.paragraph_id: index for index, paragraph in enumerate(chapter.paragraphs)}
    missing = [paragraph_id for paragraph_id in target_ids if paragraph_id not in id_to_index]
    if missing:
        raise PatchApplicationError(f"Target paragraph does not exist: {', '.join(missing)}")

    indexes = [id_to_index[paragraph_id] for paragraph_id in target_ids]
    if indexes != sorted(indexes):
        raise PatchApplicationError("Target paragraphs must appear in manuscript order.")
    expected = list(range(indexes[0], indexes[0] + len(indexes)))
    if indexes != expected:
        raise PatchApplicationError("Target paragraphs must be contiguous.")
    return indexes


def _new_paragraphs(chapter: Chapter, texts: list[str]) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    for text in texts:
        chapter.paragraph_seq += 1
        paragraphs.append(Paragraph(paragraph_id=f"{chapter.chapter_id}_p{chapter.paragraph_seq:04d}", text=text))
    return paragraphs


def _merge_world_bible(world_bible: WorldBible, patch: GraftPatch) -> WorldBible:
    bible = world_bible.model_copy(deep=True)
    bible.rules = _dedupe([*bible.rules, *patch.world_bible_patch.rules_to_add])
    bible.locations = _dedupe([*bible.locations, *patch.world_bible_patch.locations_to_add])
    bible.motifs = _dedupe([*bible.motifs, *patch.world_bible_patch.motifs_to_add])

    resolved = set(patch.world_bible_patch.open_threads_to_resolve)
    remaining_threads = [thread for thread in bible.open_threads if thread not in resolved]
    bible.open_threads = _dedupe([*remaining_threads, *patch.world_bible_patch.open_threads_to_add])
    bible.characters = _merge_character_facts(bible.characters, patch.world_bible_patch.character_facts_to_add)
    return bible


def _merge_character_facts(existing: list[CharacterFact], additions: list[CharacterFact]) -> list[CharacterFact]:
    merged = [character.model_copy(deep=True) for character in existing]
    by_name = {character.name.casefold(): character for character in merged}
    for addition in additions:
        key = addition.name.casefold()
        if key in by_name:
            by_name[key].facts = _dedupe([*by_name[key].facts, *addition.facts])
        else:
            new_character = addition.model_copy(deep=True)
            merged.append(new_character)
            by_name[key] = new_character
    return merged


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
