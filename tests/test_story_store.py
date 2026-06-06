import os
import tempfile
import unittest

from schemas import InitialChapterPayload, InitialStoryPayload, PublicCapsule, VisibleCharacter, WorldBible
from story_store import StoryStoreError, create_story_from_payload, get_story, save_story


def payload():
    return InitialStoryPayload(
        public_capsule=PublicCapsule(
            title="Clock Shore",
            genre="fantasy",
            tone="quiet",
            short_summary="A shore returns what clocks forget.",
            visible_characters=[VisibleCharacter(name="Ira", one_line_description="A keeper of tide clocks.")],
            open_questions=["What did the clock forget?"],
        ),
        world_bible=WorldBible(
            premise="The tide returns lost hours.",
            rules=["Returned hours become objects."],
            characters=[],
            locations=[],
            motifs=[],
            open_threads=[],
        ),
        chapters=[
            InitialChapterPayload(title="One", summary="First", paragraphs=["A", "B", "C", "D"]),
            InitialChapterPayload(title="Two", summary="Second", paragraphs=["E", "F", "G", "H"]),
            InitialChapterPayload(title="Three", summary="Third", paragraphs=["I", "J", "K", "L"]),
        ],
    )


class StoryStoreTests(unittest.TestCase):
    def test_save_story_rejects_stale_update(self):
        original_data_dir = os.environ.get("DATA_DIR")
        try:
            with tempfile.TemporaryDirectory() as directory:
                os.environ["DATA_DIR"] = directory
                story = create_story_from_payload(payload())
                save_story(story)

                current = get_story(story.story_id)
                changed = current.model_copy(update={"updated_at": "2026-06-07T00:00:01Z"})
                save_story(changed, expected_updated_at=current.updated_at)

                stale = current.model_copy(update={"updated_at": "2026-06-07T00:00:02Z"})
                with self.assertRaises(StoryStoreError):
                    save_story(stale, expected_updated_at=current.updated_at)
        finally:
            if original_data_dir is None:
                os.environ.pop("DATA_DIR", None)
            else:
                os.environ["DATA_DIR"] = original_data_dir


if __name__ == "__main__":
    unittest.main()
