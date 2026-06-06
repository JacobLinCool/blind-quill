from __future__ import annotations

import traceback
from html import escape
from typing import Any

import gradio as gr

from model_client import generate_json
from patcher import apply_patch
from prompts import build_plan_graft_messages, build_write_patch_messages
from render import render_capsule, render_full_story, render_gallery, render_reveal, share_link
from schemas import GraftPatch, GraftPlan
from story_store import StoryStoreError, create_story, get_story, list_story_summaries, save_story
from utils import InputValidationError, validate_fragment, validate_story_id


APP_CSS = """
.gradio-container {
  background:
    linear-gradient(90deg, rgba(90, 61, 31, 0.05) 1px, transparent 1px),
    linear-gradient(180deg, rgba(90, 61, 31, 0.04) 1px, transparent 1px),
    #f5eddc;
  background-size: 28px 28px;
  color: #221b14;
}
.app-shell { max-width: 1120px; margin: 0 auto; }
.app-title h1 { margin-bottom: 0.2rem; font-size: 2rem; }
.app-title p { margin-top: 0; color: #5e5145; }
.capsule, .reveal, .full-story, .gallery-card {
  border: 1px solid #d3bea0;
  border-radius: 8px;
  background: rgba(255, 250, 239, 0.88);
  box-shadow: 0 1px 0 rgba(60, 41, 20, 0.06);
}
.capsule, .reveal, .full-story { padding: 18px; }
.capsule h2, .chapter h3, .gallery-card h3 { margin-bottom: 0.2rem; }
.capsule h3 { margin: 1rem 0 0.2rem; font-size: 1rem; }
.meta, .progress, .story-code, .chapter-summary { color: #6f5f4c; }
.story-code code { background: #efe1c8; border-radius: 4px; padding: 2px 5px; }
.status-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.badge {
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0;
}
.badge.open { background: #d9ead3; color: #214b26; }
.badge.sealed { background: #ead7d3; color: #6c2b22; }
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}
.gallery-card { padding: 14px; }
.chapter { border-top: 1px solid #ddc8aa; padding-top: 16px; margin-top: 16px; }
.chapter:first-child { border-top: 0; margin-top: 0; padding-top: 0; }
.paragraph {
  line-height: 1.62;
  margin: 0.85rem 0;
}
.graft-highlight {
  background: #fff0a8;
  border-left: 4px solid #a97817;
  padding: 10px 12px;
  border-radius: 6px;
}
.reveal {
  background: #2f261d;
  color: #fff8e8;
  border-color: #2f261d;
}
.reveal .meta { color: #dfc9a9; }
.reveal-line { font-size: 1.15rem; font-weight: 700; }
.empty-state { color: #6f5f4c; }
textarea { font-family: inherit; }
"""


def refresh_gallery() -> tuple[dict[str, Any], str]:
    summaries = list_story_summaries()
    choices = [(f"{item.title} ({item.graft_count}/{item.max_grafts}) - {item.story_id}", item.story_id) for item in summaries]
    return gr.update(choices=choices, value=choices[0][1] if choices else None), render_gallery(summaries)


def create_manuscript(seed: str, request: gr.Request) -> tuple[str, str, str, str, dict[str, Any], str]:
    try:
        story = create_story(seed)
        base_url = _request_base_url(request)
        share_markdown = _share_markdown(base_url, story.story_id)
        gallery_update, gallery_html = refresh_gallery()
        return (
            render_capsule(story),
            render_full_story(story),
            share_markdown,
            story.story_id,
            gallery_update,
            gallery_html,
        )
    except Exception as exc:
        return _error_html(exc), "", "", "", gr.update(), render_gallery(list_story_summaries())


def load_selected_story(story_id: str, request: gr.Request) -> tuple[str, str, str, str]:
    try:
        clean_id = validate_story_id(story_id)
        story = get_story(clean_id)
        share_markdown = _share_markdown(_request_base_url(request), story.story_id)
        sealed_note = ""
        if story.status == "sealed":
            sealed_note = "<p class='meta'>This manuscript is sealed. You can read it, but it cannot accept new grafts.</p>"
        return render_capsule(story) + sealed_note, share_markdown, "", ""
    except Exception as exc:
        return _error_html(exc), "", "", ""


def load_gallery_story(story_id: str, request: gr.Request) -> tuple[str, str, str, str, str, str, str]:
    story_id_value = story_id or ""
    capsule, link, reveal, full_story = load_selected_story(story_id_value, request)
    return story_id_value, capsule, link, capsule, link, reveal, full_story


def stitch_fragment(story_id: str, fragment: str, request: gr.Request) -> tuple[str, str, str, str, str, dict[str, Any], str]:
    try:
        clean_id = validate_story_id(story_id)
        clean_fragment = validate_fragment(fragment)
        story = get_story(clean_id)
        plan = generate_json(
            build_plan_graft_messages(story, clean_fragment),
            GraftPlan,
            "GraftPlan",
            max_new_tokens=4096,
        )
        patch = generate_json(
            build_write_patch_messages(story, plan, clean_fragment),
            GraftPatch,
            "GraftPatch",
            max_new_tokens=8192,
        )
        result = apply_patch(story, plan, patch, clean_fragment)
        save_story(result.story, expected_updated_at=story.updated_at)
        share_markdown = _share_markdown(_request_base_url(request), result.story.story_id)
        gallery_update, gallery_html = refresh_gallery()
        return (
            render_reveal(result),
            render_capsule(result.story),
            render_full_story(result.story, result.highlight_paragraph_ids),
            share_markdown,
            "",
            gallery_update,
            gallery_html,
        )
    except Exception as exc:
        return _error_html(exc), "", "", "", fragment, gr.update(), render_gallery(list_story_summaries())


def load_from_query(request: gr.Request) -> tuple[str, str, str, str, str, dict[str, Any], str]:
    gallery_update, gallery_html = refresh_gallery()
    story_id = ""
    capsule = ""
    link = ""
    try:
        params = getattr(request, "query_params", None) or {}
        candidate = params.get("story", "") if hasattr(params, "get") else ""
        if candidate:
            story_id = validate_story_id(str(candidate))
            story = get_story(story_id)
            capsule = render_capsule(story)
            link = _share_markdown(_request_base_url(request), story.story_id)
    except Exception as exc:
        capsule = _error_html(exc)
    return story_id, capsule, link, capsule, link, gallery_update, gallery_html


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Blind Quill") as demo:
        with gr.Column(elem_classes=["app-shell"]):
            gr.HTML(
                """
                <header class="app-title">
                  <h1>Blind Quill</h1>
                  <p>A hidden-canon story grafting game.</p>
                </header>
                """
            )
            selected_story_id = gr.State("")

            with gr.Tab("Browse Hidden Manuscripts"):
                gallery_dropdown = gr.Dropdown(label="Choose a manuscript", choices=[], interactive=True)
                refresh_button = gr.Button("Refresh")
                gallery_html = gr.HTML()
                gallery_load_button = gr.Button("Load selected manuscript")
                browse_capsule = gr.HTML()
                browse_share = gr.Markdown()

            with gr.Tab("Start a Hidden Manuscript"):
                seed_input = gr.Textbox(label="Seed", max_lines=5, max_length=500, placeholder="A lighthouse keeper discovers...")
                create_button = gr.Button("Begin manuscript", variant="primary")
                created_capsule = gr.HTML()
                created_story = gr.HTML()
                created_share = gr.Markdown()

            with gr.Tab("Continue a Hidden Manuscript"):
                story_id_input = gr.Textbox(label="Story code", placeholder="Paste a story code or open a share link")
                load_button = gr.Button("Load public capsule")
                continue_capsule = gr.HTML()
                continue_share = gr.Markdown()
                fragment_input = gr.Textbox(
                    label="Your fragment",
                    max_lines=5,
                    max_length=500,
                    placeholder="Add a secret, object, scene, place, line of dialogue, or strange rule.",
                )
                stitch_button = gr.Button("Stitch my fragment", variant="primary")
                reveal_output = gr.HTML()
                updated_capsule = gr.HTML()
                full_story_output = gr.HTML()

            refresh_button.click(refresh_gallery, outputs=[gallery_dropdown, gallery_html])
            gallery_load_button.click(
                load_gallery_story,
                inputs=[gallery_dropdown],
                outputs=[
                    story_id_input,
                    browse_capsule,
                    browse_share,
                    continue_capsule,
                    continue_share,
                    reveal_output,
                    full_story_output,
                ],
            )
            create_button.click(
                create_manuscript,
                inputs=[seed_input],
                outputs=[created_capsule, created_story, created_share, selected_story_id, gallery_dropdown, gallery_html],
            ).then(lambda story_id: story_id, inputs=[selected_story_id], outputs=[story_id_input])
            load_button.click(
                load_selected_story,
                inputs=[story_id_input],
                outputs=[continue_capsule, continue_share, reveal_output, full_story_output],
            )
            stitch_button.click(
                stitch_fragment,
                inputs=[story_id_input, fragment_input],
                outputs=[
                    reveal_output,
                    updated_capsule,
                    full_story_output,
                    continue_share,
                    fragment_input,
                    gallery_dropdown,
                    gallery_html,
                ],
            )
            demo.load(
                load_from_query,
                outputs=[
                    story_id_input,
                    continue_capsule,
                    continue_share,
                    browse_capsule,
                    browse_share,
                    gallery_dropdown,
                    gallery_html,
                ],
            )
    return demo


def _request_base_url(request: gr.Request) -> str:
    raw = getattr(request, "request", None)
    if raw is not None and hasattr(raw, "base_url"):
        return str(raw.base_url).rstrip("/")
    headers = getattr(request, "headers", {}) or {}
    host = headers.get("host") if hasattr(headers, "get") else ""
    if host:
        proto = headers.get("x-forwarded-proto", "https") if hasattr(headers, "get") else "https"
        return f"{proto}://{host}"
    return ""


def _share_markdown(base_url: str, story_id: str) -> str:
    link = share_link(base_url, story_id)
    if link == story_id:
        return f"Story code: `{story_id}`"
    return f"[Share link]({link})"


def _error_html(exc: Exception) -> str:
    if isinstance(exc, (InputValidationError, StoryStoreError, ValueError)):
        message = str(exc)
    else:
        message = "The app hit an internal error. Check the Space logs for details."
        traceback.print_exc()
    return f'<section class="capsule"><p><strong>Error:</strong> {escape(message)}</p></section>'


if __name__ == "__main__":
    build_app().launch(css=APP_CSS)
