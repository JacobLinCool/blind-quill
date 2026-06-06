from __future__ import annotations

import json
from typing import Any

from schemas import GraftPlan, Story


SYSTEM_PROMPT = """You are Blind Quill, an invisible story editor.
You can see the full hidden manuscript, but the player cannot.
Your job is to preserve continuity while making each player's fragment feel like it always belonged in the story.

Rules:
- Think carefully, then final-answer with valid JSON only.
- Do not include Markdown in the final answer.
- Do not reveal hidden editorial notes to the player-facing fields.
- Preserve existing character names, rules, and unresolved threads unless the user fragment intentionally changes them.
- Never rewrite the entire manuscript unless explicitly asked by the schema. For grafts, output only the local patch.
- Keep the story PG-13. Refuse or soften explicit sexual content, sexual content involving minors, detailed real-world harm instructions, hateful content, or private personal data.
"""


def build_create_story_messages(seed: str) -> list[dict[str, Any]]:
    prompt = f"""Create the initial hidden manuscript for Blind Quill.

Seed, 500 characters maximum:
{seed}

Return ONLY this JSON object:
{{
  "public_capsule": {{
    "title": "string",
    "genre": "string",
    "tone": "string",
    "short_summary": "string <= 600 chars",
    "visible_characters": [
      {{"name": "string", "one_line_description": "string"}}
    ],
    "open_questions": ["string"]
  }},
  "world_bible": {{
    "premise": "string",
    "rules": ["string"],
    "characters": [
      {{"name": "string", "facts": ["string"]}}
    ],
    "locations": ["string"],
    "motifs": ["string"],
    "open_threads": ["string"]
  }},
  "chapters": [
    {{
      "title": "string",
      "summary": "string",
      "paragraphs": ["paragraph text", "paragraph text"]
    }}
  ]
}}

Requirements:
- Generate 3 to 5 chapters.
- Each chapter should have 4 to 8 paragraphs.
- Leave meaningful open threads for later players.
- Do not mention Blind Quill, the hackathon, Qwen, or implementation details inside the story.
"""
    return [_text_message("system", SYSTEM_PROMPT), _text_message("user", prompt)]


def build_plan_graft_messages(story: Story, fragment: str) -> list[dict[str, Any]]:
    prompt = f"""Plan where the player's fragment belongs in the hidden manuscript.

Hidden manuscript JSON:
{_json(story_for_prompt(story))}

Player fragment, 500 characters maximum:
{fragment}

Return ONLY this JSON object:
{{
  "target_chapter_id": "ch02",
  "target_paragraph_ids": ["ch02_p0003"],
  "insertion_mode": "replace | insert_before | insert_after | append_to_chapter",
  "player_safe_rationale": "A short explanation suitable for the reveal UI.",
  "continuity_risks": ["string"],
  "required_preservations": ["string"],
  "fragment_interpretation": {{
    "kind": "character_trait | event | object | location | secret | theme | dialogue | other",
    "summary": "string"
  }}
}}

Planning rules:
- Choose one target chapter.
- Prefer 1 or 2 target paragraphs.
- Use append_to_chapter only when no existing paragraph can naturally absorb the fragment.
- Choose the location that creates the most satisfying later reveal while preserving continuity.
- The player-facing rationale should be charming but concise.
"""
    return [_text_message("system", SYSTEM_PROMPT), _text_message("user", prompt)]


def build_write_patch_messages(story: Story, plan: GraftPlan, fragment: str) -> list[dict[str, Any]]:
    prompt = f"""Write the local patch for the selected graft. Output only patch JSON, not the full manuscript.

Hidden manuscript JSON:
{_json(story_for_prompt(story))}

Selected graft plan JSON:
{_json(plan.model_dump(mode="json"))}

Player fragment, 500 characters maximum:
{fragment}

Return ONLY this JSON object:
{{
  "target_chapter_id": "{plan.target_chapter_id}",
  "target_paragraph_ids": {json.dumps(plan.target_paragraph_ids)},
  "insertion_mode": "{plan.insertion_mode}",
  "replacement_paragraphs": [
    "new paragraph text",
    "optional second new paragraph text"
  ],
  "public_reveal": "Your fragment was stitched into Chapter 2, just before ...",
  "editor_rationale_for_player": "Why this placement makes story sense, without exposing hidden notes.",
  "updated_chapter_summary": "string",
  "public_capsule_patch": {{
    "short_summary": "updated story-facing public summary <= 600 chars",
    "visible_characters": [
      {{"name": "string", "one_line_description": "string"}}
    ],
    "open_questions": ["string"]
  }},
  "world_bible_patch": {{
    "rules_to_add": ["string"],
    "character_facts_to_add": [
      {{"name": "string", "facts": ["string"]}}
    ],
    "locations_to_add": ["string"],
    "motifs_to_add": ["string"],
    "open_threads_to_add": ["string"],
    "open_threads_to_resolve": ["string"]
  }}
}}

Patch-writing rules:
- Preserve the target chapter ID, target paragraph IDs, and insertion mode exactly as selected in the plan.
- Make the user's fragment visible in spirit, not necessarily verbatim.
- Blend style with the existing chapter.
- Do not contradict world bible facts unless the fragment is intentionally a revelation, and even then make it coherent.
- Keep replacement_paragraphs to 1 to 3 paragraphs.
- Use empty arrays when the world bible has no additions or resolutions.
- public_capsule_patch.short_summary must be a public story summary only. Do not mention the player, fragment, graft, placement, target paragraph, editing opportunity, rationale, continuity risks, or why this was a good place to insert the contribution.
- Put placement explanations only in editor_rationale_for_player.
"""
    return [_text_message("system", SYSTEM_PROMPT), _text_message("user", prompt)]


def build_repair_json_messages(
    raw: str,
    schema_name: str,
    schema_contract: str,
    validation_error: str,
) -> list[dict[str, Any]]:
    prompt = f"""The previous response was not valid JSON for schema {schema_name}.

Schema contract:
{schema_contract}

Validation or parsing error:
{validation_error}

Previous response after thinking text was removed:
{raw}

Return ONLY corrected valid JSON. Do not add Markdown or explanation.
"""
    return [_text_message("system", SYSTEM_PROMPT), _text_message("user", prompt)]


def story_for_prompt(story: Story) -> dict[str, Any]:
    return {
        "story_id": story.story_id,
        "status": story.status,
        "graft_count": story.graft_count,
        "max_grafts": story.max_grafts,
        "public_capsule": story.public_capsule.model_dump(mode="json"),
        "world_bible": story.world_bible.model_dump(mode="json"),
        "canon": story.canon.model_dump(mode="json"),
        "graft_log": [record.model_dump(mode="json") for record in story.graft_log],
    }


def _text_message(role: str, text: str) -> dict[str, Any]:
    return {"role": role, "content": [{"type": "text", "text": text}]}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
