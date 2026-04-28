"""Claude-powered session summarization."""
from __future__ import annotations

import os

import anthropic

# System prompts tailored per game system
_SYSTEM_TTRPG = """\
You are a dedicated scribe for a tabletop RPG group. You receive a raw voice \
transcript of a game session and produce polished session notes in Markdown.

Guidelines:
- Write in past tense, present-tense for player action beats is fine.
- Use the players' actual in-character names if they refer to their characters; \
  otherwise use the speaker name from the transcript.
- Ignore out-of-character chatter about rules lookups, dice rolls, snacks, etc. \
  unless it's amusing and relevant.
- Do not invent details not supported by the transcript.
- Keep the Summary section readable by someone who missed the session.
"""

_PROMPT_TEMPLATE = """\
Campaign: {campaign}
Session date: {session_date}

=== TRANSCRIPT ===
{transcript}
=== END TRANSCRIPT ===

Please produce session notes with exactly this Markdown structure \
(no extra top-level headings):

## Summary
2–4 paragraph narrative summary of what happened.

## Key Events
- Bullet list of major plot beats and action moments.

## NPCs Encountered
- Name — brief note (attitude, what happened).
(Omit section if none.)

## Locations Visited
- Location — brief note.
(Omit section if none.)

## Decisions & Revelations
- Bullet list of important choices made or lore revealed.
(Omit section if none.)

## Next Session Setup
1–2 sentences on where things stand / what's coming.
"""


def summarize_transcript(
    lines: list[tuple[float, str, str]],
    campaign_slug: str,
    session_date: str,
) -> str:
    """Call Claude and return the summary as a Markdown string."""
    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

    # Keep the transcript to a reasonable token count — truncate the middle
    # if it's extremely long (Whisper verbosity can be high).
    transcript_text = _build_transcript_text(lines)

    prompt = _PROMPT_TEMPLATE.format(
        campaign=campaign_slug,
        session_date=session_date,
        transcript=transcript_text,
    )

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=4096,
        system=_SYSTEM_TTRPG,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text.strip()


def _build_transcript_text(lines: list[tuple[float, str, str]]) -> str:
    """Plain text version for the prompt (no Markdown bold)."""
    parts = []
    for t, name, text in lines:
        h = int(t) // 3600
        m = (int(t) % 3600) // 60
        s = int(t) % 60
        ts = f'{h:02d}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'
        parts.append(f'[{ts}] {name}: {text}')
    return '\n'.join(parts)
