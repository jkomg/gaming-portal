#!/usr/bin/env python3
"""Import/sync the Athens Chronicles campaign wiki from the ground-truth
export at scripts/fixtures/athens_wiki_export.json (dumped directly from the
production Turso DB of the real athens-chronicles app).

This replaces the original one-time import (same filename, kept for
history in git blame) — that version hand-transcribed 14 pages from the
Notion campaign guide with different slugs than the real site and never
set any cover images. This version mirrors the real site exactly: same
35 pages, same slugs (so a slug-based redirect from athens.jkomg.us/wiki
works), same draft/active status split (draft = Book Two spoiler content,
kept staff-only here too), and real cover image URLs (reusing the GCS
bucket the real site already serves them from — no re-upload needed).

Safe to re-run: upserts by (campaign_id, slug).

Usage:
    export DATABASE_URL=$(gcloud secrets versions access latest --secret=DATABASE_URL --project=jkomg-gaming)
    export TURSO_AUTH_TOKEN=$(gcloud secrets versions access latest --secret=TURSO_AUTH_TOKEN --project=jkomg-gaming)
    python scripts/import_athens_chronicles.py             # dry run (default)
    python scripts/import_athens_chronicles.py --apply      # actually write changes

To refresh the export after future changes to the real site, re-run (from
the athens-chronicles apps/web/ directory, against its own DATABASE_URL):
    python3 -c "
import json
from app import create_app
from app.db import WikiPage
app = create_app()
with app.app_context():
    pages = WikiPage.query.order_by(WikiPage.category, WikiPage.slug).all()
    out = [{'slug': p.slug, 'title': p.title, 'summary': p.summary or '',
            'body_markdown': p.body_markdown or '', 'category': p.category or '',
            'cover_image_url': p.cover_image_url or '', 'status': p.status} for p in pages]
    json.dump(out, open('athens_wiki_export.json', 'w'), indent=2)
"
then copy the resulting file over scripts/fixtures/athens_wiki_export.json here.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

CAMPAIGN_SLUG = 'athens-chronicles'
CAMPAIGN_NAME = 'Athens Chronicles'
CAMPAIGN_SYSTEM = 'Vampire: The Masquerade 5th Edition'
CAMPAIGN_DESCRIPTION = (
    "A multi-book Chronicle following a coterie of Athenian Cainites from 1242 CE, "
    "beginning with Book One: Titanomachy (1242-1458 CE). "
    "Player Campaign Guide (Notion): "
    "https://app.notion.com/p/3a33a3e5cab181809536d87e4a9ee2f1"
)
CAMPAIGN_STATUS = 'active'  # full migration -- gaming-portal is now the canonical wiki

WIKI_CATEGORIES = [
    {'slug': 'locations',   'name': 'Locations',   'icon': 'bi-geo-alt-fill'},
    {'slug': 'characters',  'name': 'Characters',  'icon': 'bi-person-fill'},
    {'slug': 'backgrounds', 'name': 'Backgrounds', 'icon': 'bi-journal-text'},
    {'slug': 'spcs',        'name': 'SPCs',        'icon': 'bi-person-badge-fill'},
    {'slug': 'plotlines',   'name': 'Plotlines',   'icon': 'bi-diagram-3-fill'},
    {'slug': 'coteries',    'name': 'Coteries',    'icon': 'bi-people-fill'},
    {'slug': 'factions',    'name': 'Factions',    'icon': 'bi-shield-fill'},
    {'slug': 'lore',        'name': 'Lore',        'icon': 'bi-book-fill'},
]

EXPORT_PATH = Path(__file__).parent / 'fixtures' / 'athens_wiki_export.json'


def _load_pages() -> list[dict]:
    with open(EXPORT_PATH, encoding='utf-8') as f:
        return json.load(f)


def main() -> None:
    apply_changes = '--apply' in sys.argv
    pages = _load_pages()
    print(f'Loaded {len(pages)} pages from {EXPORT_PATH.name}')

    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('libsql://') or db_url.startswith('https://'):
        _run_turso(db_url, pages, apply_changes)
    else:
        _run_sqlite(pages, apply_changes)


def _get_or_create_campaign_sqlite(conn, apply_changes: bool):
    row = conn.execute('SELECT id FROM campaigns WHERE slug = ?', (CAMPAIGN_SLUG,)).fetchone()
    if row:
        print(f'campaign "{CAMPAIGN_SLUG}" exists (id={row["id"]})')
        if apply_changes:
            conn.execute(
                """UPDATE campaigns SET status=?, description=?, wiki_categories=?,
                       updated_at=datetime('now') WHERE id=?""",
                (CAMPAIGN_STATUS, CAMPAIGN_DESCRIPTION, json.dumps(WIKI_CATEGORIES), row['id']),
            )
        return row['id']
    print(f'create campaign "{CAMPAIGN_SLUG}"')
    if not apply_changes:
        return None
    cur = conn.execute(
        """INSERT INTO campaigns (slug, name, system, status, description, wiki_categories,
                                   wiki_enabled, sort_order, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 1, 0, datetime('now'), datetime('now'))""",
        (CAMPAIGN_SLUG, CAMPAIGN_NAME, CAMPAIGN_SYSTEM, CAMPAIGN_STATUS, CAMPAIGN_DESCRIPTION,
         json.dumps(WIKI_CATEGORIES)),
    )
    return cur.lastrowid


def _run_sqlite(pages, apply_changes: bool) -> None:
    import sqlite3

    db_path = Path(__file__).parent.parent / 'data' / 'db.sqlite'
    if not db_path.exists():
        print(f'DB not found at {db_path}')
        sys.exit(1)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        campaign_id = _get_or_create_campaign_sqlite(conn, apply_changes)
        if apply_changes:
            _upsert_pages_sqlite(conn, campaign_id, pages)
            conn.commit()
    print('\nDone (sqlite).' if apply_changes else '\nDry run only. Re-run with --apply to write changes.')


def _upsert_pages_sqlite(conn, campaign_id, pages) -> None:
    for p in pages:
        row = conn.execute(
            'SELECT id FROM wiki_pages WHERE campaign_id = ? AND slug = ?',
            (campaign_id, p['slug']),
        ).fetchone()
        if row:
            conn.execute(
                """UPDATE wiki_pages SET title=?, summary=?, category=?, body_markdown=?,
                       cover_image_url=?, status=?, source='manual', updated_at=datetime('now')
                   WHERE id=?""",
                (p['title'], p['summary'], p['category'], p['body_markdown'],
                 p['cover_image_url'], p['status'], row['id']),
            )
            print(f'  updated: {p["slug"]}')
        else:
            conn.execute(
                """INSERT INTO wiki_pages (campaign_id, slug, title, summary, body_markdown,
                       category, cover_image_url, status, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual', datetime('now'), datetime('now'))""",
                (campaign_id, p['slug'], p['title'], p['summary'], p['body_markdown'],
                 p['category'], p['cover_image_url'], p['status']),
            )
            print(f'  created: {p["slug"]}')


def _run_turso(db_url: str, pages, apply_changes: bool) -> None:
    token = os.environ.get('TURSO_AUTH_TOKEN', '')
    connect_url = 'https://' + db_url[len('libsql://'):] if db_url.startswith('libsql://') else db_url

    sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))
    from turso_http import connect

    conn = connect(connect_url, auth_token=token)
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM campaigns WHERE slug = ?', (CAMPAIGN_SLUG,))
    row = cursor.fetchone()
    if row:
        campaign_id = row[0]
        print(f'campaign "{CAMPAIGN_SLUG}" exists (id={campaign_id})')
        if apply_changes:
            cursor.execute(
                """UPDATE campaigns SET status=?, description=?, wiki_categories=?,
                       updated_at=datetime('now') WHERE id=?""",
                (CAMPAIGN_STATUS, CAMPAIGN_DESCRIPTION, json.dumps(WIKI_CATEGORIES), campaign_id),
            )
    else:
        print(f'create campaign "{CAMPAIGN_SLUG}"')
        if not apply_changes:
            campaign_id = None
        else:
            cursor.execute(
                """INSERT INTO campaigns (slug, name, system, status, description, wiki_categories,
                                           wiki_enabled, sort_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, 0, datetime('now'), datetime('now'))""",
                (CAMPAIGN_SLUG, CAMPAIGN_NAME, CAMPAIGN_SYSTEM, CAMPAIGN_STATUS, CAMPAIGN_DESCRIPTION,
                 json.dumps(WIKI_CATEGORIES)),
            )
            cursor.execute('SELECT id FROM campaigns WHERE slug = ?', (CAMPAIGN_SLUG,))
            campaign_id = cursor.fetchone()[0]
            print(f'  created campaign (id={campaign_id})')

    for p in pages:
        if apply_changes:
            cursor.execute(
                'SELECT id FROM wiki_pages WHERE campaign_id = ? AND slug = ?',
                (campaign_id, p['slug']),
            )
            existing = cursor.fetchone()
        else:
            existing = None
        action = 'update' if (apply_changes and existing) else ('create' if apply_changes else 'upsert')
        print(f'  {action:8} {p["slug"]}')
        if not apply_changes:
            continue
        if existing:
            cursor.execute(
                """UPDATE wiki_pages SET title=?, summary=?, category=?, body_markdown=?,
                       cover_image_url=?, status=?, source='manual', updated_at=datetime('now')
                   WHERE id=?""",
                (p['title'], p['summary'], p['category'], p['body_markdown'],
                 p['cover_image_url'], p['status'], existing[0]),
            )
        else:
            cursor.execute(
                """INSERT INTO wiki_pages (campaign_id, slug, title, summary, body_markdown,
                       category, cover_image_url, status, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual', datetime('now'), datetime('now'))""",
                (campaign_id, p['slug'], p['title'], p['summary'], p['body_markdown'],
                 p['category'], p['cover_image_url'], p['status']),
            )

    if apply_changes:
        conn.commit()
        print(f'\nDone. {len(pages)} page(s) processed for campaign "{CAMPAIGN_SLUG}".')
    else:
        print('\nDry run only. Re-run with --apply to write changes.')


if __name__ == '__main__':
    main()
