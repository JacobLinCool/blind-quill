---
title: Blind Quill
sdk: gradio
sdk_version: 6.16.0
app_file: app.py
python_version: "3.12"
suggested_hardware: zero-a10g
license: mit
---

# Blind Quill

Blind Quill is a hidden-canon story grafting game.

Each manuscript has a public capsule and a hidden full canon. You can play the
intended way by reading only the capsule, adding one fragment, and letting
`Qwen/Qwen3.5-2B` decide where that fragment belongs. The model rewrites only the
local passage it targets, then reveals where your idea was stitched into the
story.

Readers who only want to read can use the escape door: `Read without changing`.
The app warns that the best experience is to contribute first, then allows the
reader to reveal the full manuscript anyway.

## Interface

The UI is a bespoke literary frontend called "The Invisible Bindery". It lives in
`web/` and is served by a `gradio.Server` backend.

`app.py` exposes queued API endpoints:

- `list_stories`
- `get_capsule`
- `create_story`
- `stitch`
- `read_manuscript`

The frontend calls those endpoints through the Gradio JS client. This keeps
Gradio queueing, concurrency control, and ZeroGPU support while presenting a
single custom surface: gallery -> capsule -> compose -> reveal -> reader.

The Python layers are:

- `core.py`: create, browse, stitch, and read orchestration.
- `story_store.py`: JSON persistence and file locking.
- `model_client.py`: model loading, generation, thinking-block stripping, and
  JSON validation.
- `patcher.py`: deterministic local patch application.
- `presenter.py`: view models for the custom frontend.
- `app.py`: static frontend serving and Gradio Server API endpoints.

## Local Development

Use uv with Python 3.12, matching the Hugging Face Space as closely as possible.

```bash
uv sync --python 3.12
uv run python app.py
```

Then open <http://localhost:7860>.

Persistent story data is stored at:

- `DATA_DIR`, when set
- `/data`, when it exists on Hugging Face Spaces
- `./data/stories.json`, otherwise

### Execution backend

`BQ_DEVICE` selects where generation runs.

| `BQ_DEVICE` | Behaviour |
| --- | --- |
| `auto` (default) | ZeroGPU on a Space with the `spaces` runtime, else CUDA, else Apple MPS, else CPU. |
| `zerogpu` | Hugging Face ZeroGPU (`@spaces.GPU`), with automatic CPU fallback (below). |
| `cuda` | Local NVIDIA GPU via `device_map="auto"`. |
| `mps` | Apple Silicon GPU (Metal); falls back to float32 if float16 fails. |
| `cpu` | CPU only — slow but needs no accelerator or quota. |

**Per-user ZeroGPU fallback.** ZeroGPU quota is per visitor, not per Space owner,
and is only known at request time. So on a ZeroGPU Space each stitch is attempted
on the GPU; if the visitor's quota is spent, the request is transparently re-run
on CPU instead of failing. No configuration or sign-in is required to keep using
the app — it just gets slower.

**Progress.** Because CPU/MPS runs are slow, the `stitch` endpoint streams real
progress (stage, percentage, ETA — and a note when a fallback happens) to the
reveal screen. Fast GPU runs keep the original staged animation, since ZeroGPU's
forked generation cannot stream token callbacks back across the process boundary.

### Logging

Set `BQ_LOG_LEVEL` (default `INFO`; use `DEBUG` for per-stage detail). Logs go to
stderr only — never the UI — and record messages processed, total and per-stage
timings, and a best-effort resource snapshot (process memory, CPU, and GPU/MPS
memory when available).

## Requirements

`requirements.txt` is generated from `uv.lock` for Hugging Face Spaces:

```bash
uv export --format requirements-txt --no-dev --no-hashes --no-emit-project -o requirements.txt
```

Do not hand-edit `requirements.txt`; edit `pyproject.toml`, run `uv lock`, and
export again.

## Test

```bash
uv run python -m compileall app.py core.py model_client.py observability.py patcher.py presenter.py prompts.py schemas.py story_store.py utils.py tests
uv run python -m unittest discover -s tests -v
```

The tests cover JSON/thinking cleanup, deterministic patch application, graft
sealing, stale-write rejection, the blinded capsule flow, the warned read escape
door, the create-then-stitch flow, device resolution, the resource snapshot, and
the streamed stitch progress events. They do not download model weights.

## Model Policy

- Uses one model: `Qwen/Qwen3.5-2B`.
- Uses the Transformers `AutoProcessor` and `AutoModelForImageTextToText` path.
- Wraps model generation in `@spaces.GPU(duration=300)` on ZeroGPU; runs directly
  on CUDA, MPS, or CPU otherwise (selected by `BQ_DEVICE`).
- Does not set `temperature`, `top_p`, `top_k`, or other sampling controls.
- Disables Qwen thinking for schema-constrained JSON calls so the token budget is
  spent on parseable JSON; other text generation keeps the model template default.
- Strips `<think>...</think>` before JSON parsing, storage, prompting, or UI
  rendering.
- Does not use embeddings, RAG, ASR, image models, or a second language model.

## Example Seeds

```text
A city where every doorway remembers the last person who lied inside it.
```

```text
On a generation ship whose crew believes Earth was a myth invented to calm children, a janitor discovers a sealed garden where rain falls upward and an old radio is still receiving ocean weather reports.
```

Example fragment:

```text
A brass key in the protagonist's pocket becomes warm whenever someone nearby tells the truth.
```
