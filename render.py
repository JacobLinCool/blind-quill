from __future__ import annotations

from html import escape

from schemas import AppliedPatchResult, Story, StorySummary


def render_capsule(story: Story) -> str:
    capsule = story.public_capsule
    characters = "".join(
        f"<li><strong>{escape(character.name)}</strong>: {escape(character.one_line_description)}</li>"
        for character in capsule.visible_characters
    )
    questions = "".join(f"<li>{escape(question)}</li>" for question in capsule.open_questions)
    status_label = "Sealed" if story.status == "sealed" else "Open"
    return f"""
    <section class="capsule">
      <div class="status-row">
        <span class="badge {escape(story.status)}">{status_label}</span>
        <span class="progress">Grafts: {story.graft_count} / {story.max_grafts}</span>
      </div>
      <h2>{escape(capsule.title)}</h2>
      <p class="meta">{escape(capsule.genre)} / {escape(capsule.tone)}</p>
      <p>{escape(capsule.short_summary)}</p>
      <h3>Visible characters</h3>
      <ul>{characters or "<li>None revealed yet.</li>"}</ul>
      <h3>Open questions</h3>
      <ul>{questions or "<li>No public questions yet.</li>"}</ul>
      <p class="story-code">Story code: <code>{escape(story.story_id)}</code></p>
    </section>
    """


def render_full_story(story: Story, highlight_ids: list[str] | None = None) -> str:
    highlighted = set(highlight_ids or [])
    chapters = []
    for chapter in story.canon.chapters:
        paragraphs = []
        for paragraph in chapter.paragraphs:
            css_class = "paragraph graft-highlight" if paragraph.paragraph_id in highlighted else "paragraph"
            paragraphs.append(
                f'<p class="{css_class}" data-paragraph-id="{escape(paragraph.paragraph_id)}">'
                f"{escape(paragraph.text)}</p>"
            )
        chapters.append(
            f"""
            <article class="chapter">
              <h3>{escape(chapter.title)}</h3>
              <p class="chapter-summary">{escape(chapter.summary)}</p>
              {''.join(paragraphs)}
            </article>
            """
        )
    return f'<section class="full-story">{"".join(chapters)}</section>'


def render_reveal(result: AppliedPatchResult) -> str:
    record = result.graft_record
    return f"""
    <section class="reveal">
      <p class="reveal-line">{escape(record.public_reveal)}</p>
      <p>{escape(record.editor_rationale_for_player)}</p>
      <p class="meta">Target: {escape(result.target_chapter_title)} / {escape(record.insertion_mode)}</p>
    </section>
    """


def render_gallery(summaries: list[StorySummary]) -> str:
    if not summaries:
        return '<p class="empty-state">No manuscripts yet.</p>'
    cards = []
    for summary in summaries:
        status_label = "Sealed" if summary.status == "sealed" else "Open"
        cards.append(
            f"""
            <article class="gallery-card">
              <div class="status-row">
                <span class="badge {escape(summary.status)}">{status_label}</span>
                <span class="progress">{summary.graft_count} / {summary.max_grafts}</span>
              </div>
              <h3>{escape(summary.title)}</h3>
              <p class="meta">{escape(summary.genre)} / {escape(summary.tone)}</p>
              <p>{escape(summary.short_summary)}</p>
              <p class="story-code"><code>{escape(summary.story_id)}</code></p>
            </article>
            """
        )
    return f'<section class="gallery-grid">{"".join(cards)}</section>'


def share_link(base_url: str, story_id: str) -> str:
    base = base_url.rstrip("/") if base_url else ""
    if not base:
        return story_id
    return f"{base}/?story={story_id}"
