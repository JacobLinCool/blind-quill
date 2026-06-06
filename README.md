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

Blind Quill is a blinded collaborative story-grafting game.

You do not get to read the whole manuscript before you play. You only see a tiny public capsule: genre, a few characters, and a short summary. Then you contribute one fragment: a secret, an object, a scene, a personality trait, a place.

`Qwen/Qwen3.5-2B` reads the hidden manuscript, chooses where your fragment belongs, rewrites only that local passage, and reveals where it stitched your idea into the story.

It is a hidden-canon editor: every player changes the manuscript without knowing where their contribution will land.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Set `DATA_DIR=/data` on Hugging Face Spaces when persistent storage is available. If `DATA_DIR` is unset and `/data` does not exist, Blind Quill writes to `./data/stories.json`.

## Test

```bash
python -m unittest discover -s tests -v
```

The tests cover JSON/thinking cleanup, deterministic patch application, graft sealing, and stale-write rejection. They do not download model weights.

## Model policy

- Uses one model: `Qwen/Qwen3.5-2B`.
- Uses the Transformers `AutoProcessor` and `AutoModelForImageTextToText` path.
- Wraps model generation in `@spaces.GPU(duration=300)` when running on ZeroGPU.
- Does not set `temperature`, `top_p`, `top_k`, or other sampling controls.
- Keeps Qwen thinking mode enabled by default.
- Strips `<think>...</think>` before JSON parsing, storage, or UI rendering.
- Does not use embeddings, RAG, ASR, image models, or a second language model.

## Demo seed

```text
A lighthouse keeper discovers that every storm washes a different childhood memory onto the shore.
```

Demo contribution:

```text
The keeper has always avoided blue glass because it shows reflections that are one day late.
```
