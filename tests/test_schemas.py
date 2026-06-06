import unittest

from schemas import PublicCapsule, PublicCapsulePatch


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


if __name__ == "__main__":
    unittest.main()
