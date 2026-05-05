"""Write session notes to the portal database (Turso or SQLite)."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

from db import execute, execute_write

PORTAL_URL = os.environ.get('PORTAL_URL', 'http://localhost:8080')

SESSIONS_CATEGORY = {
    'slug': 'sessions',
    'name': 'Sessions',
    'icon': 'bi-calendar-event-fill',
}

DEFAULT_CATEGORIES = [
    {'slug': 'locations',  'name': 'Locations',  'icon': 'bi-geo-alt-fill'},
    {'slug': 'characters', 'name': 'Characters', 'icon': 'bi-person-fill'},
    {'slug': 'factions',   'name': 'Factions',   'icon': 'bi-shield-fill'},
    {'slug': 'lore',       'name': 'Lore',       'icon': 'bi-book-fill'},
]


def get_campaigns() -> list[dict]:
    return execute('SELECT id, slug, name FROM campaigns ORDER BY sort_order')


def get_campaign_id(slug: str) -> int | None:
    rows = execute('SELECT id FROM campaigns WHERE slug = ?', [slug])
    return int(rows[0]['id']) if rows else None


def _ensure_sessions_category(campaign_id: int) -> None:
    rows = execute('SELECT wiki_categories FROM campaigns WHERE id = ?', [campaign_id])
    if not rows:
        return
    raw = rows[0]['wiki_categories'] or ''
    try:
        cats: list[dict] = json.loads(raw) if raw else list(DEFAULT_CATEGORIES)
    except Exception:
        cats = list(DEFAULT_CATEGORIES)
    if any(c.get('slug') == 'sessions' for c in cats):
        return
    cats.append(SESSIONS_CATEGORY)
    execute_write(
        'UPDATE campaigns SET wiki_categories = ? WHERE id = ?',
        [json.dumps(cats), campaign_id],
    )


def _next_session_number(campaign_id: int) -> int:
    rows = execute(
        "SELECT COUNT(*) AS n FROM wiki_pages WHERE campaign_id = ? AND category = 'sessions'",
        [campaign_id],
    )
    return int(rows[0]['n'] or 0) + 1


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return re.sub(r'-+', '-', text).strip('-')


def _unique_slug(campaign_id: int, base: str) -> str:
    slug, i = base, 1
    while execute(
        'SELECT 1 FROM wiki_pages WHERE campaign_id = ? AND slug = ?',
        [campaign_id, slug],
    ):
        i += 1
        slug = f'{base}-{i}'
    return slug


def post_session(
    campaign_id: int,
    campaign_slug: str,
    started_at: datetime,
    summary_md: str,
    transcript_lines: list[tuple[float, str, str]],
) -> str:
    """Insert a new session WikiPage; return its public URL."""
    _ensure_sessions_category(campaign_id)
    session_num = _next_session_number(campaign_id)

    date_str = started_at.strftime('%B %-d, %Y')
    title = f'Session {session_num:02d} \u2014 {date_str}'
    base_slug = _slugify(f'session-{session_num:02d}-{started_at.strftime("%Y-%m-%d")}')
    slug = _unique_slug(campaign_id, base_slug)
    body = _build_body(summary_md, transcript_lines, started_at)
    now = datetime.utcnow().isoformat()

    execute_write(
        '''INSERT INTO wiki_pages
           (campaign_id, slug, title, summary, body_markdown, category,
            status, source, updated_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'sessions', 'active', 'bot', 'Orpheus', ?, ?)''',
        [
            campaign_id, slug, title,
            f'Auto-generated notes for session {session_num}.',
            body, now, now,
        ],
    )
    return f'{PORTAL_URL}/{campaign_slug}/wiki/{slug}'


def _build_body(
    summary_md: str,
    transcript_lines: list[tuple[float, str, str]],
    started_at: datetime,
) -> str:
    speakers = sorted({name for _, name, _ in transcript_lines})
    speaker_list = ', '.join(speakers) if speakers else 'Unknown'
    transcript_md = '\n\n'.join(
        f'[{_fmt_ts(t)}] **{name}**: {text}'
        for t, name, text in transcript_lines
    )
    return f"""\
*Auto-generated session notes — recorded {started_at.strftime("%B %-d, %Y")}.*
*Speakers: {speaker_list}*

---

{summary_md}

---

## Full Transcript

{transcript_md}
""".strip()


def _fmt_ts(t: float) -> str:
    h = int(t) // 3600
    m = (int(t) % 3600) // 60
    s = int(t) % 60
    return f'{h:02d}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'
