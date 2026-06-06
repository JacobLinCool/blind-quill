import unittest

from patcher import apply_patch
from schemas import (
    Canon,
    CharacterFact,
    Chapter,
    FragmentInterpretation,
    GraftPatch,
    GraftPlan,
    Paragraph,
    PublicCapsule,
    PublicCapsulePatch,
    Story,
    VisibleCharacter,
    WorldBible,
    WorldBiblePatch,
)


def sample_story(graft_count=0, max_grafts=30):
    return Story(
        story_id="abc123",
        created_at="2026-06-07T00:00:00Z",
        updated_at="2026-06-07T00:00:00Z",
        status="open",
        max_grafts=max_grafts,
        graft_count=graft_count,
        public_capsule=PublicCapsule(
            title="The Late Glass",
            genre="fantasy",
            tone="wistful",
            short_summary="A keeper tends a shore where memory washes in.",
            visible_characters=[VisibleCharacter(name="Mara", one_line_description="A careful keeper.")],
            open_questions=["What does the sea remember?"],
        ),
        canon=Canon(
            chapters=[
                Chapter(
                    chapter_id="ch01",
                    title="Salt Clock",
                    summary="Mara finds a clock in the tide.",
                    paragraph_seq=2,
                    paragraphs=[
                        Paragraph(paragraph_id="ch01_p0001", text="The tide brought a brass clock."),
                        Paragraph(paragraph_id="ch01_p0002", text="Mara hid it below the lantern."),
                    ],
                )
            ]
        ),
        world_bible=WorldBible(
            premise="Memory arrives by tide.",
            rules=["Storms carry old memories."],
            characters=[CharacterFact(name="Mara", facts=["She keeps the lighthouse."])],
            locations=["Lighthouse"],
            motifs=["salt"],
            open_threads=["What does the sea remember?"],
        ),
        graft_log=[],
    )


def sample_plan(mode="replace"):
    return GraftPlan(
        target_chapter_id="ch01",
        target_paragraph_ids=[] if mode == "append_to_chapter" else ["ch01_p0002"],
        insertion_mode=mode,
        player_safe_rationale="It belongs beside the lantern.",
        continuity_risks=[],
        required_preservations=[],
        fragment_interpretation=FragmentInterpretation(kind="object", summary="Blue glass shows late reflections."),
    )


def sample_patch(mode="replace"):
    target_ids = [] if mode == "append_to_chapter" else ["ch01_p0002"]
    return GraftPatch(
        target_chapter_id="ch01",
        target_paragraph_ids=target_ids,
        insertion_mode=mode,
        replacement_paragraphs=["Mara hid the blue glass below the lantern, where every reflection arrived a day late."],
        public_reveal="Your fragment was stitched below the lantern.",
        editor_rationale_for_player="The glass makes the lighthouse rule stranger.",
        updated_chapter_summary="Mara hides late-reflecting glass beneath the lantern.",
        public_capsule_patch=PublicCapsulePatch(
            short_summary="A keeper tends a shore where memory and late reflections wash in.",
            visible_characters=[VisibleCharacter(name="Mara", one_line_description="A careful keeper of late reflections.")],
            open_questions=["What does the sea remember?"],
        ),
        world_bible_patch=WorldBiblePatch(
            rules_to_add=["Blue glass reflects one day late."],
            character_facts_to_add=[CharacterFact(name="Mara", facts=["She avoids blue glass."])],
            locations_to_add=[],
            motifs_to_add=["blue glass"],
            open_threads_to_add=["Why is blue glass delayed?"],
            open_threads_to_resolve=[],
        ),
    )


class PatcherTests(unittest.TestCase):
    def test_replace_patch_generates_new_ids_and_logs_graft(self):
        result = apply_patch(sample_story(), sample_plan(), sample_patch(), "blue glass")
        story = result.story
        self.assertEqual(story.graft_count, 1)
        self.assertEqual(result.highlight_paragraph_ids, ["ch01_p0003"])
        self.assertEqual(story.canon.chapters[0].paragraphs[1].paragraph_id, "ch01_p0003")
        self.assertEqual(story.graft_log[0].generated_paragraph_ids, ["ch01_p0003"])
        self.assertIn("Blue glass reflects one day late.", story.world_bible.rules)

    def test_append_patch_seals_at_limit(self):
        result = apply_patch(sample_story(graft_count=29, max_grafts=30), sample_plan("append_to_chapter"), sample_patch("append_to_chapter"), "blue glass")
        self.assertEqual(result.story.status, "sealed")
        self.assertEqual(result.story.graft_count, 30)


if __name__ == "__main__":
    unittest.main()
