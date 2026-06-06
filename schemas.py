from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
StoryStatus = Literal["open", "sealed"]
InsertionMode = Literal["replace", "insert_before", "insert_after", "append_to_chapter"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class VisibleCharacter(StrictModel):
    name: NonEmptyStr
    one_line_description: NonEmptyStr


class PublicCapsule(StrictModel):
    title: NonEmptyStr
    genre: NonEmptyStr
    tone: NonEmptyStr
    short_summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
    visible_characters: list[VisibleCharacter] = Field(default_factory=list)
    open_questions: list[NonEmptyStr] = Field(default_factory=list, max_length=3)


class CharacterFact(StrictModel):
    name: NonEmptyStr
    facts: list[NonEmptyStr] = Field(min_length=1)


class WorldBible(StrictModel):
    premise: NonEmptyStr
    rules: list[NonEmptyStr] = Field(default_factory=list)
    characters: list[CharacterFact] = Field(default_factory=list)
    locations: list[NonEmptyStr] = Field(default_factory=list)
    motifs: list[NonEmptyStr] = Field(default_factory=list)
    open_threads: list[NonEmptyStr] = Field(default_factory=list)


class Paragraph(StrictModel):
    paragraph_id: NonEmptyStr
    text: NonEmptyStr


class Chapter(StrictModel):
    chapter_id: NonEmptyStr
    title: NonEmptyStr
    summary: NonEmptyStr
    paragraph_seq: int = Field(ge=0)
    paragraphs: list[Paragraph] = Field(min_length=1)


class Canon(StrictModel):
    chapters: list[Chapter] = Field(min_length=1)


class GraftRecord(StrictModel):
    graft_id: NonEmptyStr
    created_at: NonEmptyStr
    user_fragment: NonEmptyStr
    target_chapter_id: NonEmptyStr
    target_paragraph_ids: list[NonEmptyStr]
    insertion_mode: InsertionMode
    generated_paragraph_ids: list[NonEmptyStr]
    public_reveal: NonEmptyStr
    editor_rationale_for_player: NonEmptyStr
    capsule_before: PublicCapsule
    capsule_after: PublicCapsule


class Story(StrictModel):
    story_id: NonEmptyStr
    created_at: NonEmptyStr
    updated_at: NonEmptyStr
    status: StoryStatus
    max_grafts: int = Field(default=30, gt=0)
    graft_count: int = Field(default=0, ge=0)
    public_capsule: PublicCapsule
    canon: Canon
    world_bible: WorldBible
    graft_log: list[GraftRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def graft_count_cannot_exceed_max(self) -> Story:
        if self.graft_count > self.max_grafts:
            raise ValueError("graft_count cannot exceed max_grafts.")
        return self


class StorySummary(StrictModel):
    story_id: NonEmptyStr
    title: NonEmptyStr
    genre: NonEmptyStr
    tone: NonEmptyStr
    short_summary: NonEmptyStr
    graft_count: int = Field(ge=0)
    max_grafts: int = Field(gt=0)
    status: StoryStatus
    updated_at: NonEmptyStr


class InitialChapterPayload(StrictModel):
    title: NonEmptyStr
    summary: NonEmptyStr
    paragraphs: list[NonEmptyStr] = Field(min_length=4, max_length=8)


class InitialStoryPayload(StrictModel):
    public_capsule: PublicCapsule
    world_bible: WorldBible
    chapters: list[InitialChapterPayload] = Field(min_length=3, max_length=5)


class FragmentInterpretation(StrictModel):
    kind: Literal[
        "character_trait",
        "event",
        "object",
        "location",
        "secret",
        "theme",
        "dialogue",
        "other",
    ]
    summary: NonEmptyStr


class GraftPlan(StrictModel):
    target_chapter_id: NonEmptyStr
    target_paragraph_ids: list[NonEmptyStr]
    insertion_mode: InsertionMode
    player_safe_rationale: NonEmptyStr
    continuity_risks: list[NonEmptyStr] = Field(default_factory=list)
    required_preservations: list[NonEmptyStr] = Field(default_factory=list)
    fragment_interpretation: FragmentInterpretation


class PublicCapsulePatch(StrictModel):
    short_summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
    visible_characters: list[VisibleCharacter]
    open_questions: list[NonEmptyStr] = Field(max_length=3)


class WorldBiblePatch(StrictModel):
    rules_to_add: list[NonEmptyStr]
    character_facts_to_add: list[CharacterFact]
    locations_to_add: list[NonEmptyStr]
    motifs_to_add: list[NonEmptyStr]
    open_threads_to_add: list[NonEmptyStr]
    open_threads_to_resolve: list[NonEmptyStr]


class GraftPatch(StrictModel):
    target_chapter_id: NonEmptyStr
    target_paragraph_ids: list[NonEmptyStr]
    insertion_mode: InsertionMode
    replacement_paragraphs: list[NonEmptyStr] = Field(min_length=1, max_length=3)
    public_reveal: NonEmptyStr
    editor_rationale_for_player: NonEmptyStr
    updated_chapter_summary: NonEmptyStr
    public_capsule_patch: PublicCapsulePatch
    world_bible_patch: WorldBiblePatch


class AppliedPatchResult(StrictModel):
    story: Story
    graft_record: GraftRecord
    target_chapter_title: NonEmptyStr
    highlight_paragraph_ids: list[NonEmptyStr]
