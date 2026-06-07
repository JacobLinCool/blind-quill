from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError

from observability import get_logger, resource_snapshot
from prompts import build_repair_json_messages


MODEL_ID = "Qwen/Qwen3.5-2B"

SchemaT = TypeVar("SchemaT", bound=BaseModel)

# A callback reporting generation progress: (tokens_done, tokens_total).
StepCallback = Callable[[int, int], None]

_processor = None
_model = None
_execution_cache: str | None = None

try:
    import spaces
except ImportError:
    spaces = None


def _is_zerogpu() -> bool:
    """Whether generation should be wrapped in `spaces.GPU` (no torch import).

    Decided cheaply so the `@_gpu` decorator can run at import time without
    pulling in torch. ZeroGPU applies when explicitly requested, or under `auto`
    on a Hugging Face Space that has the `spaces` runtime.
    """
    mode = os.environ.get("BQ_DEVICE", "auto").strip().lower()
    if mode == "zerogpu":
        return True
    if mode == "auto":
        return spaces is not None and bool(os.environ.get("SPACE_ID"))
    return False


def resolve_execution() -> str:
    """Resolve BQ_DEVICE to a concrete mode: zerogpu | cuda | mps | cpu."""
    mode = os.environ.get("BQ_DEVICE", "auto").strip().lower()
    if mode not in {"auto", "zerogpu", "cuda", "mps", "cpu"}:
        get_logger("model").warning("Unknown BQ_DEVICE=%r; falling back to auto.", mode)
        mode = "auto"
    if _is_zerogpu():
        return "zerogpu"
    if mode in {"cuda", "mps", "cpu"}:
        return mode
    # auto, not a Space: pick the best local accelerator, else CPU.
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        backend = getattr(torch.backends, "mps", None)
        if backend is not None and backend.is_available():
            return "mps"
    except Exception:  # noqa: BLE001 - torch may be unavailable; CPU is the safe floor
        pass
    return "cpu"


def execution_mode() -> str:
    """Cached `resolve_execution()`; safe to call from anywhere, including app.py."""
    global _execution_cache
    if _execution_cache is None:
        _execution_cache = resolve_execution()
    return _execution_cache


def _gpu(duration: int):
    if _is_zerogpu() and spaces is not None:
        return spaces.GPU(duration=duration)
    return lambda function: function


class ModelClientError(RuntimeError):
    pass


def generate_json(
    messages: list[dict[str, Any]],
    schema_model: type[SchemaT],
    schema_name: str,
    max_new_tokens: int = 8192,
    on_step: StepCallback | None = None,
    force_cpu: bool = False,
) -> SchemaT:
    # ZeroGPU runs generation in a forked subprocess that a live callback cannot
    # reach, so token progress only applies in-process (local, or a CPU fallback).
    on_gpu = execution_mode() == "zerogpu" and not force_cpu
    effective_step = None if on_gpu else on_step
    raw = generate_text(
        messages,
        max_new_tokens=max_new_tokens,
        on_step=effective_step,
        force_cpu=force_cpu,
        json_mode=True,
    )
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
        repaired = strip_thinking(
            generate_text(
                repair_messages,
                max_new_tokens=4096,
                force_cpu=force_cpu,
                json_mode=True,
            )
        )
        try:
            return _validate_json(repaired, schema_model)
        except (json.JSONDecodeError, ValueError, ValidationError) as repair_error:
            raise ModelClientError(f"Model did not return valid {schema_name} JSON.") from repair_error


def generate_text(
    messages: list[dict[str, Any]],
    max_new_tokens: int = 8192,
    on_step: StepCallback | None = None,
    force_cpu: bool = False,
    json_mode: bool = False,
) -> str:
    """Run one generation.

    On a ZeroGPU Space this dispatches to the GPU worker, which raises a
    `gradio.Error` when the calling user is out of quota — the app layer catches
    that and retries with `force_cpu=True`. Every other case (local CUDA/MPS/CPU,
    or the CPU retry) runs in-process and can stream live token progress.
    """
    if execution_mode() == "zerogpu" and not force_cpu:
        return _generate_on_gpu(messages, max_new_tokens, json_mode)
    return _generate_in_process(messages, max_new_tokens, on_step, json_mode)


def _generate_in_process(
    messages: list[dict[str, Any]],
    max_new_tokens: int,
    on_step: StepCallback | None = None,
    json_mode: bool = False,
) -> str:
    processor, model = load_model()
    logger = get_logger("generate")
    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
        enable_thinking=not json_mode,
    ).to(model.device)
    input_len = int(inputs["input_ids"].shape[-1])

    import torch

    streamer = _make_progress_streamer(max_new_tokens, on_step) if on_step is not None else None

    start = time.perf_counter()
    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            streamer=streamer,
            # Sampling controls are intentionally left to the model defaults.
        )
    elapsed = time.perf_counter() - start

    generated = outputs[0][input_len:]
    output_len = int(generated.shape[-1])
    rate = output_len / elapsed if elapsed > 0 else 0.0
    logger.info(
        "generate device=%s in=%d out=%d in %.2fs (%.1f tok/s) | %s",
        str(model.device),
        input_len,
        output_len,
        elapsed,
        rate,
        resource_snapshot(),
    )
    return processor.decode(generated, skip_special_tokens=False)


@_gpu(duration=300)
def _generate_on_gpu(messages: list[dict[str, Any]], max_new_tokens: int, json_mode: bool) -> str:
    # Runs inside the ZeroGPU fork: arguments are pickled, so no callbacks here.
    return _generate_in_process(messages, max_new_tokens, on_step=None, json_mode=json_mode)


def _make_progress_streamer(max_new_tokens: int, on_step: StepCallback):
    """Build a token-counting streamer that reports progress as generation runs.

    Defined lazily so importing this module never requires transformers. The
    streamer's `put` is called synchronously by `model.generate` for the prompt
    (skipped) and then once per generated token; reports are throttled by time.
    """
    from transformers.generation.streamers import BaseStreamer

    class _ProgressStreamer(BaseStreamer):
        def __init__(self) -> None:
            self.total = max(1, max_new_tokens)
            self.count = 0
            self._prompt_seen = False
            self._last_report = 0.0
            self._min_interval = 0.3

        def put(self, value) -> None:
            if not self._prompt_seen:
                self._prompt_seen = True  # first call is the prompt; not generated output
                return
            try:
                self.count += int(value.numel())
            except AttributeError:
                self.count += 1
            now = time.perf_counter()
            if now - self._last_report >= self._min_interval:
                self._last_report = now
                self._report()

        def end(self) -> None:
            self._report()

        def _report(self) -> None:
            try:
                on_step(min(self.count, self.total), self.total)
            except Exception:  # noqa: BLE001 - progress is best-effort, never fatal
                pass

    return _ProgressStreamer()


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

    import torch

    logger = get_logger("model")
    mode = execution_mode()
    logger.info("Loading %s for execution=%s", MODEL_ID, mode)

    _processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)

    if mode in ("zerogpu", "cuda"):
        # ZeroGPU/CUDA: let accelerate place the model (CUDA-first, as before).
        _model = AutoModelForImageTextToText.from_pretrained(
            MODEL_ID,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=True,
        )
    else:
        # Local MPS/CPU: load on CPU then move to the chosen device explicitly.
        dtype = torch.float16 if mode == "mps" else torch.float32
        try:
            _model = AutoModelForImageTextToText.from_pretrained(
                MODEL_ID, torch_dtype=dtype, trust_remote_code=True
            ).to(mode)
        except Exception as exc:  # noqa: BLE001 - MPS half precision can be flaky
            if mode == "mps":
                logger.warning("MPS load with float16 failed (%s); retrying with float32.", exc)
                _model = AutoModelForImageTextToText.from_pretrained(
                    MODEL_ID, torch_dtype=torch.float32, trust_remote_code=True
                ).to("mps")
            else:
                raise

    logger.info("Model ready execution=%s device=%s", mode, str(_model.device))
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
