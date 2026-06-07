# Blind Quill Design

Blind Quill is a hidden-canon story grafting game. A reader sees a public
capsule for a manuscript, adds a short fragment, and the model privately decides
where that fragment belongs in the full canon. The reveal is the important
moment: the reader learns where their contribution was stitched and can then read
the updated manuscript.

## Product Rules

- Each manuscript has a hidden full canon and a public capsule.
- A public capsule contains title, genre, tone, summary, visible characters,
  open questions, status, and graft count.
- A manuscript accepts at most 30 grafts. At 30 grafts it becomes sealed and
  read-only.
- Readers are encouraged to add a fragment before reading the full manuscript.
- Readers may still use the escape door, `Read without changing`, after a
  warning modal. This prevents low-quality forced contributions from people who
  only want to read.
- A stitch may replace or append a small local passage. It must not regenerate
  the whole manuscript.

## User Flows

### Start a Manuscript

1. The user writes a seed, up to 500 characters.
2. The binding page explains that the model is creating hidden canon, a public
   capsule, and persistent storage.
3. The creator lands on the capsule for the new manuscript.
4. The creator can contribute another fragment, read the manuscript, or share the
   link.

### Continue a Manuscript

1. The user opens the gallery or a `?story=` share link.
2. The user sees only the public capsule.
3. The primary path is `Contribute a fragment`.
4. The escape path is `Read without changing`, which opens a warning modal before
   revealing the full manuscript.
5. After a stitch, the reveal stage shows the public reveal, rationale, target
   chapter, and links to read or return to the bindery.

### Read a Manuscript

The reader view shows the full canon, chapter navigation, highlighted grafted
paragraphs when present, and a graft ledger.

## Architecture

The app is a custom frontend served by a Gradio Server backend.

- `app.py` exposes queued API endpoints and serves `web/`.
- `core.py` owns create, browse, stitch, and read orchestration.
- `story_store.py` owns JSON persistence and file locking.
- `model_client.py` loads `Qwen/Qwen3.5-2B`, resolves the execution device,
  runs generation, strips thinking blocks, and validates JSON.
- `patcher.py` applies model patches deterministically.
- `presenter.py` maps backend story objects into frontend view models.
- `observability.py` configures logging and a lightweight per-run profiler.
- `web/` contains the production React frontend loaded through Babel in the
  Space page.

## Execution and Progress

`BQ_DEVICE` (`auto` | `zerogpu` | `cuda` | `mps` | `cpu`) selects the base
backend; `auto` prefers ZeroGPU on a Space, then CUDA, MPS, and CPU.

ZeroGPU quota is per visitor and only known at request time, so device selection
cannot be purely static. The flow is:

- `app.py` attempts each ZeroGPU stitch synchronously on the request thread —
  ZeroGPU bills against the Gradio request context, which a worker thread would
  not carry. ZeroGPU runs the function in a forked subprocess, so its arguments
  are pickled and it cannot stream token callbacks back.
- If ZeroGPU raises a per-user quota error (`spaces` raises `gradio.Error` with a
  "quota exceeded" / "credits exceeded" message), `app.py` retries the stitch
  with `force_cpu=True`. `model_client.generate_text` then runs in-process on the
  CPU-resident model instead of the GPU worker.
- In-process runs (local CUDA/MPS/CPU, or the CPU fallback) execute through
  `_stream_stitch`, which runs `core.stitch` on a worker thread and drains its
  `on_progress` callback through a queue into the endpoint's yields. A worker
  thread is safe here only because no `@spaces.GPU` call is involved.
- `core.stitch` accepts an optional `on_progress` callback and a `force_cpu`
  flag, reports stage and token progress, and still returns an
  `AppliedPatchResult` synchronously so tests and callers are unaffected.
- The frontend consumes the stream with the Gradio JS client's `submit` and
  shows stage, percentage, ETA, and a fallback note, dropping back to the staged
  animation for fast GPU runs that emit no token progress.

## Observability

Logging and profiling write to stderr only, never the UI. `observability.py`
configures the `blind_quill` logger (level via `BQ_LOG_LEVEL`, default `INFO`).
Each stitch logs messages processed, total and per-stage timings, and a
best-effort resource snapshot (process memory, CPU, and GPU/MPS memory when
available); a missing metric is omitted rather than raising.

## Model Policy

- Model: `Qwen/Qwen3.5-2B`.
- One model only.
- No embeddings, RAG, ASR, image generation, or secondary LLM.
- Qwen thinking mode stays enabled.
- `<think>...</think>` content is stripped before parsing, storage, prompts, or
  UI display.
- Generation does not manually tune sampling controls.
- ZeroGPU runs use `spaces.GPU(duration=300)`; CUDA, MPS, and CPU runs call the
  model directly. The backend is chosen by `BQ_DEVICE`.

## Environment

The Space targets Python 3.12 and Gradio 6.16. Local development should use uv
with the same Python version:

```bash
uv sync --python 3.12
uv export --format requirements-txt --no-dev --no-hashes --no-emit-project -o requirements.txt
```

Hugging Face Spaces still installs from `requirements.txt`; that file is
generated from `uv.lock`.

## Verification

Required checks before deployment:

```bash
uv run python -m compileall app.py core.py model_client.py observability.py patcher.py presenter.py prompts.py schemas.py story_store.py utils.py tests
uv run python -m unittest discover -s tests -v
```

For frontend changes, also verify the relevant deployed or local UI state with a
browser: mobile width, no horizontal overflow, and expected button/modal flows.
