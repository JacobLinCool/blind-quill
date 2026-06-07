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
- `model_client.py` loads `Qwen/Qwen3.5-2B`, runs generation, strips thinking
  blocks, and validates JSON.
- `patcher.py` applies model patches deterministically.
- `presenter.py` maps backend story objects into frontend view models.
- `web/` contains the production React frontend loaded through Babel in the
  Space page.

## Model Policy

- Model: `Qwen/Qwen3.5-2B`.
- One model only.
- No embeddings, RAG, ASR, image generation, or secondary LLM.
- Qwen thinking mode stays enabled.
- `<think>...</think>` content is stripped before parsing, storage, prompts, or
  UI display.
- Generation does not manually tune sampling controls.
- ZeroGPU runs use `spaces.GPU(duration=300)`.

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
uv run python -m compileall app.py core.py model_client.py patcher.py presenter.py prompts.py schemas.py story_store.py utils.py tests
uv run python -m unittest discover -s tests -v
```

For frontend changes, also verify the relevant deployed or local UI state with a
browser: mobile width, no horizontal overflow, and expected button/modal flows.
