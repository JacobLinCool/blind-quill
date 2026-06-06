from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from prompts import build_repair_json_messages


MODEL_ID = "Qwen/Qwen3.5-2B"

SchemaT = TypeVar("SchemaT", bound=BaseModel)

_processor = None
_model = None

try:
    import spaces
except ImportError:
    spaces = None


def _gpu(duration: int):
    if spaces is None:
        return lambda function: function
    return spaces.GPU(duration=duration)


class ModelClientError(RuntimeError):
    pass


def generate_json(
    messages: list[dict[str, Any]],
    schema_model: type[SchemaT],
    schema_name: str,
    max_new_tokens: int = 8192,
) -> SchemaT:
    raw = generate_text(messages, max_new_tokens=max_new_tokens)
    cleaned = strip_thinking(raw)
    try:
        return _validate_json(cleaned, schema_model)
    except (json.JSONDecodeError, ValueError, ValidationError) as first_error:
        repair_messages = build_repair_json_messages(
            cleaned,
            schema_name,
            json.dumps(schema_model.model_json_schema(), ensure_ascii=False, indent=2),
            str(first_error),
        )
        repaired = strip_thinking(generate_text(repair_messages, max_new_tokens=4096))
        try:
            return _validate_json(repaired, schema_model)
        except (json.JSONDecodeError, ValueError, ValidationError) as repair_error:
            raise ModelClientError(f"Model did not return valid {schema_name} JSON.") from repair_error


@_gpu(duration=300)
def generate_text(messages: list[dict[str, Any]], max_new_tokens: int = 8192) -> str:
    processor, model = load_model()
    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    import torch

    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            # Qwen3.5 thinking mode remains enabled by default; no sampling controls are set here.
        )
    generated = outputs[0][inputs["input_ids"].shape[-1] :]
    return processor.decode(generated, skip_special_tokens=False)


def load_model():
    global _processor, _model
    if _model is not None:
        return _processor, _model

    try:
        from transformers import AutoModelForImageTextToText, AutoProcessor
    except ImportError as exc:
        raise ModelClientError(
            "Missing model dependencies. Install requirements.txt before running Blind Quill."
        ) from exc

    _processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    _model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=True,
    )
    return _processor, _model


def strip_thinking(text: str) -> str:
    without_closed_blocks = re.sub(r"<think\b[^>]*>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    start_match = re.search(r"<think\b[^>]*>", without_closed_blocks, flags=re.IGNORECASE)
    if start_match:
        json_start = without_closed_blocks.find("{", start_match.end())
        if json_start >= 0:
            without_closed_blocks = without_closed_blocks[: start_match.start()] + without_closed_blocks[json_start:]
        else:
            without_closed_blocks = without_closed_blocks[: start_match.start()]
    return without_closed_blocks.replace("</think>", "").strip()


def extract_json(text: str) -> str:
    cleaned = strip_thinking(text)
    decoder = json.JSONDecoder()
    for index, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            _, end = decoder.raw_decode(cleaned[index:])
            return cleaned[index : index + end]
        except json.JSONDecodeError:
            continue
    raise ValueError("No JSON object found in model output.")


def _validate_json(text: str, schema_model: type[SchemaT]) -> SchemaT:
    data = json.loads(extract_json(text))
    return schema_model.model_validate(data)
