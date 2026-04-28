"""One-time migration: add 'Sessions' wiki category to all campaigns.

Run from the project root:
    python scripts/add_sessions_category.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow running from project root or scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

SESSIONS_CATEGORY = {
    'slug': 'sessions',
    'name': 'Sessions',
    'icon': 'bi-calendar-event-fill',
}

DEFAULT_CATEGORIES = [
    {'slug': 'locations',  'name': 'Locations',  'icon': 'bi-geo-alt-fill'},
    {'slug': 'characters', 'name': 'Characters', 'icon': 'bi-person-fill'},
    {'slug': 'factions',   'name': 'Factions',   'icon': 'bi-shield-fill'},
    {'slug': 'lore',       'name': 'Lore',        'icon': 'bi-book-fill'},
]


def main() -> None:
    db_url = os.environ.get('DATABASE_URL', '')

    if db_url.startswith('libsql://'):
        _run_turso(db_url)
    else:
        _run_sqlite()


def _run_sqlite() -> None:
    import sqlite3

    db_path = Path(__file__).parent.parent / 'data' / 'db.sqlite'
    if not db_path.exists():
        print(f'DB not found at {db_path}')
        sys.exit(1)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        campaigns = conn.execute('SELECT id, slug, name, wiki_categories FROM campaigns').fetchall()
        updated = 0
        for row in campaigns:
            raw = row['wiki_categories'] or ''
            try:
                cats = json.loads(raw) if raw else list(DEFAULT_CATEGORIES)
            except Exception:
                cats = list(DEFAULT_CATEGORIES)

            if any(c.get('slug') == 'sessions' for c in cats):
                print(f'  {row["slug"]}: already has sessions category, skipping')
                continue

            cats.append(SESSIONS_CATEGORY)
            conn.execute(
                'UPDATE campaigns SET wiki_categories = ? WHERE id = ?',
                (json.dumps(cats), row['id']),
            )
            print(f'  {row["slug"]} ({row["name"]}): added sessions category')
            updated += 1

    print(f'\nDone. Updated {updated} campaign(s).')


def _run_turso(db_url: str) -> None:
    """For production Turso DB — import the portal's own HTTP client."""
    token = os.environ.get('TURSO_AUTH_TOKEN', '')
    connect_url = 'https://' + db_url[len('libsql://'):]

    sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))
    from turso_http import connect

    conn = connect(connect_url, auth_token=token)
    cursor = conn.cursor()
    cursor.execute('SELECT id, slug, name, wiki_categories FROM campaigns')
    campaigns = cursor.fetchall()
    # turso_http returns tuples
    updated = 0
    for row in campaigns:
        cid, slug, name, raw = row
        try:
            cats = json.loads(raw) if raw else list(DEFAULT_CATEGORIES)
        except Exception:
            cats = list(DEFAULT_CATEGORIES)

        if any(c.get('slug') == 'sessions' for c in cats):
            print(f'  {slug}: already has sessions category, skipping')
            continue

        cats.append(SESSIONS_CATEGORY)
        cursor.execute(
            'UPDATE campaigns SET wiki_categories = ? WHERE id = ?',
            (json.dumps(cats), cid),
        )
        print(f'  {slug} ({name}): added sessions category')
        updated += 1

    conn.commit()
    print(f'\nDone. Updated {updated} campaign(s).')


if __name__ == '__main__':
    main()
