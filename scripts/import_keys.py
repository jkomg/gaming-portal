#!/usr/bin/env python3
"""One-time import: parse Keys from the Golden Vault .md into wiki pages in Turso.

Usage:
    export DATABASE_URL=$(gcloud secrets versions access latest --secret=DATABASE_URL --project=jkomg-gaming)
    export TURSO_AUTH_TOKEN=$(gcloud secrets versions access latest --secret=TURSO_AUTH_TOKEN --project=jkomg-gaming)
    python3 scripts/import_keys.py
"""
from __future__ import annotations
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

MD_PATH = os.path.expanduser('~/Downloads/Keys from the Golden Vault.md')

_ssl_ctx = ssl._create_unverified_context()

# ── Turso connection ───────────────────────────────────────────────────────────

_db_url = os.environ.get('DATABASE_URL', '')
_token  = os.environ.get('TURSO_AUTH_TOKEN', '')

if _db_url.startswith('libsql://'):
    _turso_url = 'https://' + _db_url[len('libsql://'):]
elif _db_url.startswith('https://'):
    _turso_url = _db_url
else:
    print('ERROR: DATABASE_URL must start with libsql:// or https://')
    sys.exit(1)

_endpoint = f'{_turso_url}/v2/pipeline'
_headers  = {'Authorization': f'Bearer {_token}', 'Content-Type': 'application/json'}


def _arg(v):
    if v is None:           return {'type': 'null',    'value': None}
    if isinstance(v, bool): return {'type': 'integer', 'value': str(int(v))}
    if isinstance(v, int):  return {'type': 'integer', 'value': str(v)}
    return                         {'type': 'text',    'value': str(v)}


def sql(query, params=None):
    stmt = {'sql': query}
    if params:
        stmt['args'] = [_arg(p) for p in params]
    body = json.dumps({'requests': [{'type': 'execute', 'stmt': stmt}, {'type': 'close'}]})
    req  = urllib.request.Request(_endpoint, data=body.encode(), headers=_headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Turso HTTP {exc.code}: {exc.read().decode()}') from exc
    result = data['results'][0]
    if result['type'] == 'error':
        raise RuntimeError(f'SQL error: {result["error"]["message"]}')
    return result['response']['result']


def fetchone(query, params=None):
    rows = sql(query, params).get('rows', [])
    if not rows:
        return None
    return tuple(c.get('value') for c in rows[0])


# ── Helpers ────────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    s = re.sub(r'[^\w\s-]', '', text.lower())
    s = re.sub(r'[\s_]+', '-', s).strip('-')
    return s


def unique_slug(campaign_id: int, base: str) -> str:
    slug, i = base, 1
    while fetchone('SELECT id FROM wiki_pages WHERE campaign_id=? AND slug=?', [campaign_id, slug]):
        i += 1
        slug = f'{base}-{i}'
    return slug


def first_paragraph(text: str) -> str:
    for line in text.split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('!') and not line.startswith('>'):
            return line[:300]
    return ''


# ── MD parser ─────────────────────────────────────────────────────────────────

SKIP_TITLES = {'Credits'}


def parse_sections(path: str) -> list[dict]:
    with open(path, encoding='utf-8') as f:
        raw = f.read()

    parts = re.split(r'(?m)^(?=# )', raw)
    sections = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines   = part.split('\n')
        heading = lines[0].strip()
        if not heading.startswith('# '):
            continue
        title = heading[2:].strip()
        body  = '\n'.join(lines[1:]).strip()

        if title in SKIP_TITLES:
            print(f'  SKIP: {title}')
            continue

        summary = first_paragraph(body)
        body = (
            '## Session Notes\n'
            '_Not yet played — notes will appear here after the session._\n\n'
            '---\n\n'
            + body
        )
        sections.append({
            'title':    title,
            'slug':     slugify(title),
            'summary':  summary,
            'body':     body,
            'category': 'chapters',
            'status':   'draft',
        })
    return sections


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not _token:
        print('ERROR: TURSO_AUTH_TOKEN not set')
        sys.exit(1)

    print('Connecting to Turso…')
    row = fetchone("SELECT id FROM campaigns WHERE slug='keys'")
    if not row:
        print('ERROR: keys campaign not found in DB')
        sys.exit(1)
    campaign_id = int(row[0])
    print(f'Keys campaign_id = {campaign_id}')

    print(f'Parsing {MD_PATH}…')
    sections = parse_sections(MD_PATH)
    print(f'Found {len(sections)} sections to import\n')

    created = updated = 0
    for s in sections:
        existing = fetchone(
            'SELECT id, source FROM wiki_pages WHERE campaign_id=? AND slug=?',
            [campaign_id, s['slug']]
        )
        if existing:
            page_id, source = existing
            sql(
                '''UPDATE wiki_pages
                   SET title=?, summary=?, body_markdown=?, category=?, updated_by='import'
                   WHERE id=?''',
                [s['title'], s['summary'], s['body'], s['category'], int(page_id)],
            )
            print(f'  UPDATED (was {source}): {s["title"]}')
            updated += 1
        else:
            slug = unique_slug(campaign_id, s['slug'])
            sql(
                '''INSERT INTO wiki_pages
                   (campaign_id, slug, title, summary, body_markdown,
                    category, status, source, notion_page_id, updated_by)
                   VALUES (?,?,?,?,?,?,?,'manual','','import')''',
                [campaign_id, slug, s['title'], s['summary'], s['body'],
                 s['category'], s['status']],
            )
            print(f'  CREATED [chapters/draft]: {s["title"]}')
            created += 1

    print(f'\nDone. Created: {created}  |  Updated: {updated}')
    print()
    print('Next steps:')
    print('  • All heists are DRAFT (hidden from players).')
    print('  • After each session, edit the heist page, fill in Session Notes,')
    print('    and change status → Active to reveal it to players.')


if __name__ == '__main__':
    main()
