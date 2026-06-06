import unittest

from schemas import PublicCapsule, PublicCapsulePatch
from pydantic import ValidationError


class SchemaNormalizationTests(unittest.TestCase):
    def test_public_capsule_open_questions_are_capped(self):
        capsule = PublicCapsule(
            title="Title",
            genre="Genre",
            tone="Tone",
            short_summary="Summary",
            visible_characters=[],
            open_questions=["one", "two", "three", "four"],
        )
        self.assertEqual(capsule.open_questions, ["one", "two", "three"])

    def test_public_capsule_patch_open_questions_are_capped(self):
        patch = PublicCapsulePatch(
            short_summary="Summary",
            visible_characters=[],
            open_questions=["one", "two", "three", "four"],
        )
        self.assertEqual(patch.open_questions, ["one", "two", "three"])

    def test_public_capsule_patch_summary_rejects_editorial_rationale(self):
        with self.assertRaises(ValidationError):
            PublicCapsulePatch(
                short_summary="This moment offers a perfect opportunity to introduce the player's fragment.",
                visible_characters=[],
                open_questions=[],
            )


if __name__ == "__main__":
    unittest.main()
