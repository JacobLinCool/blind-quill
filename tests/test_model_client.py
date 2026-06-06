import json
import unittest

from model_client import extract_json, strip_thinking


class ModelClientParsingTests(unittest.TestCase):
    def test_strip_closed_thinking_block(self):
        raw = '<think>private reasoning</think>\n{"ok": true}'
        self.assertEqual(strip_thinking(raw), '{"ok": true}')

    def test_strip_unclosed_thinking_before_json(self):
        raw = '<think>private reasoning\n{"ok": true}'
        self.assertEqual(strip_thinking(raw), '{"ok": true}')

    def test_extract_json_uses_decoder(self):
        raw = 'Here: {"text": "brace { inside string", "ok": true} trailing'
        self.assertEqual(json.loads(extract_json(raw))["text"], "brace { inside string")


if __name__ == "__main__":
    unittest.main()
