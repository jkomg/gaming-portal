"""Database abstraction — Turso (production) or SQLite (local fallback).

Both the bot and the management UI share the same Turso database as the
Cloud Run portal, so session pages appear on the public wiki automatically.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

DATABASE_URL = os.environ.get('DATABASE_URL', '')
TURSO_TOKEN = os.environ.get('TURSO_AUTH_TOKEN', '')

# ── Routing ───────────────────────────────────────────────────────────────────

def execute(sql: str, params: list | None = None) -> list[dict]:
    """Run a SELECT and return rows as dicts."""
    if _is_turso():
        return _turso_execute(sql, params)
    return _sqlite_execute(sql, params)


def execute_write(sql: str, params: list | None = None) -> int:
    """Run an INSERT/UPDATE/DELETE; return last_insert_rowid for inserts."""
    if _is_turso():
        return _turso_write(sql, params)
    return _sqlite_write(sql, params)


def _is_turso() -> bool:
    return DATABASE_URL.startswith('libsql://')


def _turso_http_url() -> str:
    return 'https://' + DATABASE_URL[len('libsql://'):]


# ── Turso (Hrana over HTTP) ───────────────────────────────────────────────────

def _hrana_request(sql: str, params: list | None) -> dict:
    import httpx

    args = [_hrana_arg(p) for p in (params or [])]
    payload = {
        'requests': [
            {'type': 'execute', 'stmt': {'sql': sql, 'args': args}},
            {'type': 'close'},
        ]
    }
    resp = httpx.post(
        f'{_turso_http_url()}/v2/pipeline',
        json=payload,
        headers={'Authorization': f'Bearer {TURSO_TOKEN}'},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()['results'][0]['response']['result']


def _hrana_arg(value: Any) -> dict:
    if value is None:
        return {'type': 'null'}
    if isinstance(value, int):
        return {'type': 'integer', 'value': str(value)}
    if isinstance(value, float):
        return {'type': 'float', 'value': value}
    return {'type': 'text', 'value': str(value)}


def _hrana_rows(result: dict) -> list[dict]:
    cols = [c['name'] for c in result['cols']]
    rows = []
    for row in result['rows']:
        rows.append(dict(zip(cols, [v.get('value') for v in row])))
    return rows


def _turso_execute(sql: str, params: list | None) -> list[dict]:
    return _hrana_rows(_hrana_request(sql, params))


def _turso_write(sql: str, params: list | None) -> int:
    result = _hrana_request(sql, params)
    return int(result.get('last_insert_rowid') or 0)


# ── SQLite fallback ───────────────────────────────────────────────────────────

def _sqlite_path() -> str:
    return os.environ.get(
        'PORTAL_DB_PATH',
        str(Path(__file__).parent.parent / 'data' / 'db.sqlite'),
    )


def _sqlite_execute(sql: str, params: list | None) -> list[dict]:
    with sqlite3.connect(_sqlite_path()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql, params or [])
        return [dict(r) for r in cur.fetchall()]


def _sqlite_write(sql: str, params: list | None) -> int:
    with sqlite3.connect(_sqlite_path()) as conn:
        cur = conn.execute(sql, params or [])
        return cur.lastrowid or 0
