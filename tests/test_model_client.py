import json
import unittest

from pydantic import BaseModel

import model_client
from model_client import extract_json, strip_thinking


class TinyPayload(BaseModel):
    ok: bool


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

    def test_generate_json_uses_json_mode_for_initial_and_repair_calls(self):
        saved_generate_text = model_client.generate_text
        calls = []

        def fake_generate_text(*args, **kwargs):
            calls.append(kwargs)
            return "not json" if len(calls) == 1 else '{"ok": true}'

        try:
            model_client.generate_text = fake_generate_text
            result = model_client.generate_json([], TinyPayload, "TinyPayload")
        finally:
            model_client.generate_text = saved_generate_text

        self.assertTrue(result.ok)
        self.assertEqual([call["json_mode"] for call in calls], [True, True])

    def test_json_mode_disables_qwen_thinking_template(self):
        import torch

        saved_load_model = model_client.load_model

        class FakeInputs(dict):
            def to(self, _device):
                return self

        class FakeProcessor:
            def __init__(self):
                self.template_kwargs = []

            def apply_chat_template(self, messages, **kwargs):
                self.template_kwargs.append(kwargs)
                return FakeInputs({"input_ids": torch.tensor([[1, 2]])})

            def decode(self, generated, skip_special_tokens=False):
                return "{}"

        class FakeModel:
            device = "cpu"

            def generate(self, **kwargs):
                return torch.tensor([[1, 2, 3]])

        processor = FakeProcessor()
        try:
            model_client.load_model = lambda: (processor, FakeModel())
            model_client._generate_in_process([], 8, json_mode=True)
            model_client._generate_in_process([], 8, json_mode=False)
        finally:
            model_client.load_model = saved_load_model

        self.assertEqual(
            [kwargs["enable_thinking"] for kwargs in processor.template_kwargs],
            [False, True],
        )


if __name__ == "__main__":
    unittest.main()
