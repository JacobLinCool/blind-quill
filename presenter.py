"""Map backend Story objects to the shapes the Blind Quill frontend expects.

The web client (web/*.jsx) speaks in capsules, chapters with Roman numerals,
illuminated lead paragraphs, a graft ledger, and a reveal payload. This module
is the single translation layer between the Pydantic canon and that view model.
"""

from __future__ import annotations

from schemas import AppliedPatchResult, PublicCapsule, Story


def roman(number: int) -> str:
    if number <= 0:
        return str(number)
    numerals = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    result = []
    remaining = number
    for value, symbol in numerals:
        while remaining >= value:
            result.append(symbol)
            remaining -= value
    return "".join(result)


def capsule_dict(capsule: PublicCapsule) -> dict:
    return {
        "title": capsule.title,
        "genre": capsule.genre,
        "tone": capsule.tone,
        "summary": capsule.short_summary,
        "characters": [
            {"name": character.name, "desc": character.one_line_description}
            for character in capsule.visible_characters
        ],
        "questions": list(capsule.open_questions),
    }


def card_dict(story: Story) -> dict:
    """Blinded view: full public capsule, but never the hidden chapters."""
    return {
        "id": story.story_id,
        "status": story.status,
        "graftCount": story.graft_count,
        "maxGrafts": story.max_grafts,
        "capsule": capsule_dict(story.public_capsule),
    }


def _chapter_index_title(story: Story) -> dict[str, tuple[int, str]]:
    return {
        chapter.chapter_id: (index, chapter.title)
        for index, chapter in enumerate(story.canon.chapters, start=1)
    }


def _chapter_dict(index: int, chapter) -> dict:
    return {
        "no": roman(index),
        "title": chapter.title,
        "summary": chapter.summary,
        "paragraphs": [
            {"id": paragraph.paragraph_id, "text": paragraph.text, **({"lead": True} if position == 0 else {})}
            for position, paragraph in enumerate(chapter.paragraphs)
        ],
    }


def _ledger(story: Story) -> list[dict]:
    chapters = _chapter_index_title(story)
    rows = []
    for order, record in enumerate(story.graft_log, start=1):
        index, title = chapters.get(record.target_chapter_id, (0, "the canon"))
        where = f"Ch. {roman(index)} · {title}" if index else f"In {title}"
        fragment = record.user_fragment.strip()
        if len(fragment) > 90:
            fragment = fragment[:87] + "…"
        rows.append({"no": order, "frag": fragment, "where": where})
    rows.reverse()  # newest graft first
    return rows


def full_story_dict(story: Story) -> dict:
    """Unblinded view: the capsule plus every chapter and the graft ledger."""
    data = card_dict(story)
    data["chapters"] = [
        _chapter_dict(index, chapter)
        for index, chapter in enumerate(story.canon.chapters, start=1)
    ]
    data["log"] = _ledger(story)
    return data


def reveal_dict(result: AppliedPatchResult) -> dict:
    chapters = _chapter_index_title(result.story)
    index, title = chapters.get(result.graft_record.target_chapter_id, (0, result.target_chapter_title))
    target_label = f"Chapter {roman(index)} · {title}" if index else title
    return {
        "revealLine": result.graft_record.public_reveal,
        "rationale": result.graft_record.editor_rationale_for_player,
        "targetLabel": target_label,
        "highlightIds": list(result.highlight_paragraph_ids),
    }
