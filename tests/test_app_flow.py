import os
import tempfile
import unittest

import core
import story_store
from presenter import card_dict, full_story_dict, reveal_dict
from schemas import (
    CharacterFact,
    FragmentInterpretation,
    GraftPatch,
    GraftPlan,
    InitialChapterPayload,
    InitialStoryPayload,
    PublicCapsule,
    PublicCapsulePatch,
    VisibleCharacter,
    WorldBible,
    WorldBiblePatch,
)
from utils import InputValidationError


def initial_payload():
    return InitialStoryPayload(
        public_capsule=PublicCapsule(
            title="The Late Glass",
            genre="coastal fantasy",
            tone="wistful and uncanny",
            short_summary="A keeper tends a shore where storms return lost memories.",
            visible_characters=[VisibleCharacter(name="Mara", one_line_description="A lighthouse keeper.")],
            open_questions=["What does the storm remember?"],
        ),
        world_bible=WorldBible(
            premise="Storms return memories as objects.",
            rules=["Returned memories become shore objects."],
            characters=[CharacterFact(name="Mara", facts=["She keeps the lighthouse."])],
            locations=["Lighthouse"],
            motifs=["salt"],
            open_threads=["What does the storm remember?"],
        ),
        chapters=[
            InitialChapterPayload(title="Salt Clock", summary="Mara finds a clock.", paragraphs=["A", "B", "C", "D"]),
            InitialChapterPayload(title="Lantern Room", summary="Mara hides a shard.", paragraphs=["E", "F", "G", "H"]),
            InitialChapterPayload(title="Low Tide", summary="Names return.", paragraphs=["I", "J", "K", "L"]),
        ],
    )


def graft_plan():
    return GraftPlan(
        target_chapter_id="ch02",
        target_paragraph_ids=["ch02_p0002"],
        insertion_mode="replace",
        player_safe_rationale="It belongs where the shard is hidden.",
        continuity_risks=[],
        required_preservations=[],
        fragment_interpretation=FragmentInterpretation(kind="object", summary="Blue glass reflects one day late."),
    )


def graft_patch():
    return GraftPatch(
        target_chapter_id="ch02",
        target_paragraph_ids=["ch02_p0002"],
        insertion_mode="replace",
        replacement_paragraphs=["Mara hid the blue shard under the lamp oil, where reflections arrived one day late."],
        public_reveal="Your fragment was stitched into Chapter 2, beneath the lamp oil.",
        editor_rationale_for_player="The shard sharpens the lighthouse's strange rules.",
        updated_chapter_summary="Mara hides a late-reflecting shard.",
        public_capsule_patch=PublicCapsulePatch(
            short_summary="A keeper tends a shore where storms return memories and blue glass lies.",
            visible_characters=[VisibleCharacter(name="Mara", one_line_description="A lighthouse keeper avoiding blue glass.")],
            open_questions=["Why does blue glass lag behind the day?"],
        ),
        world_bible_patch=WorldBiblePatch(
            rules_to_add=["Blue glass reflects one day late."],
            character_facts_to_add=[CharacterFact(name="Mara", facts=["She avoids blue glass."])],
            locations_to_add=[],
            motifs_to_add=["blue glass"],
            open_threads_to_add=["Why does blue glass lag behind the day?"],
            open_threads_to_resolve=[],
        ),
    )


class AppFlowTests(unittest.TestCase):
    def test_create_blinds_capsule_then_stitch_reveals_full_story(self):
        original_data_dir = os.environ.get("DATA_DIR")
        original_store_generate = story_store.generate_json
        original_core_generate = core.generate_json
        try:
            with tempfile.TemporaryDirectory() as directory:
                os.environ["DATA_DIR"] = directory
                story_store.generate_json = lambda *args, **kwargs: initial_payload()

                story = core.create("A lighthouse seed.")
                story_id = story.story_id

                # Gallery + capsule are blinded: the public capsule shows, chapters never leak.
                card = card_dict(story)
                self.assertEqual(card["capsule"]["title"], "The Late Glass")
                self.assertNotIn("chapters", card)
                self.assertTrue(any(item.story_id == story_id for item in core.gallery()))
                self.assertNotIn("chapters", card_dict(core.capsule(story_id)))

                # An open manuscript cannot be read whole before being changed.
                with self.assertRaises(InputValidationError):
                    core.read_sealed(story_id)

                def fake_core_generate(*args, **kwargs):
                    schema_model = args[1]
                    if schema_model is GraftPlan:
                        return graft_plan()
                    if schema_model is GraftPatch:
                        return graft_patch()
                    raise AssertionError(f"Unexpected schema: {schema_model}")

                core.generate_json = fake_core_generate
                result = core.stitch(story_id, "Blue glass reflects one day late.")

                full = full_story_dict(result.story)
                reveal = reveal_dict(result)

                # The stitch unseals the full manuscript and highlights the new passage.
                self.assertIn("chapters", full)
                self.assertEqual(full["graftCount"], 1)
                self.assertTrue(reveal["highlightIds"])
                highlighted = reveal["highlightIds"][0]
                paragraph_ids = [p["id"] for chapter in full["chapters"] for p in chapter["paragraphs"]]
                self.assertIn(highlighted, paragraph_ids)
                self.assertIn("Chapter 2", reveal["revealLine"])
                self.assertEqual(reveal["targetLabel"], "Chapter II · Lantern Room")

                # The graft is persisted.
                self.assertEqual(core.capsule(story_id).graft_count, 1)
        finally:
            story_store.generate_json = original_store_generate
            core.generate_json = original_core_generate
            if original_data_dir is None:
                os.environ.pop("DATA_DIR", None)
            else:
                os.environ["DATA_DIR"] = original_data_dir


if __name__ == "__main__":
    unittest.main()
