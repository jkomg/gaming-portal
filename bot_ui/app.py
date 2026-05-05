"""Orpheus management UI."""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request

load_dotenv()

ORPHEUS_API = os.environ.get('ORPHEUS_API', 'http://orpheus:8765')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
TURSO_TOKEN = os.environ.get('TURSO_AUTH_TOKEN', '')
PORTAL_URL = os.environ.get('PORTAL_URL', 'https://gaming.jkomg.us')

app = Flask(__name__)


# ── DB helper (read-only, mirrors discord_bot/db.py) ─────────────────────────

def _turso_url() -> str:
    return 'https://' + DATABASE_URL[len('libsql://'):]


def _query(sql: str, params: list | None = None) -> list[dict]:
    args = [{'type': 'text', 'value': str(p)} for p in (params or [])]
    payload = {
        'requests': [
            {'type': 'execute', 'stmt': {'sql': sql, 'args': args}},
            {'type': 'close'},
        ]
    }
    resp = httpx.post(
        f'{_turso_url()}/v2/pipeline',
        json=payload,
        headers={'Authorization': f'Bearer {TURSO_TOKEN}'},
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()['results'][0]['response']['result']
    cols = [c['name'] for c in result['cols']]
    return [dict(zip(cols, [v.get('value') for v in row])) for row in result['rows']]


# ── Bot API helpers ───────────────────────────────────────────────────────────

def _bot_get(path: str, timeout: float = 3.0) -> dict | None:
    try:
        resp = httpx.get(f'{ORPHEUS_API}{path}', timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _bot_post(path: str, body: dict, timeout: float = 5.0) -> dict | None:
    try:
        resp = httpx.post(f'{ORPHEUS_API}{path}', json=body, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html', portal_url=PORTAL_URL)


@app.route('/api/status')
def api_status():
    data = _bot_get('/health')
    if data is None:
        return jsonify({'online': False})
    return jsonify(data)


@app.route('/api/sessions')
def api_sessions():
    try:
        sessions = _query(
            """SELECT wp.title, wp.slug, wp.created_at,
                      c.slug AS campaign_slug, c.name AS campaign_name
               FROM wiki_pages wp
               JOIN campaigns c ON c.id = wp.campaign_id
               WHERE wp.category = 'sessions'
               ORDER BY wp.created_at DESC
               LIMIT 20"""
        )
        for s in sessions:
            s['url'] = f'{PORTAL_URL}/{s["campaign_slug"]}/wiki/{s["slug"]}'
        return jsonify({'sessions': sessions})
    except Exception as e:
        return jsonify({'sessions': [], 'error': str(e)})


@app.route('/api/saved-sessions')
def api_saved_sessions():
    data = _bot_get('/saved-sessions')
    if data is None:
        return jsonify({'sessions': []})
    return jsonify(data)


@app.route('/api/reprocess', methods=['POST'])
def api_reprocess():
    body = request.get_json(force=True) or {}
    session_id = body.get('session_id', '').strip()
    if not session_id:
        return jsonify({'ok': False, 'error': 'session_id required'}), 400
    result = _bot_post('/reprocess', {'session_id': session_id})
    if result is None:
        return jsonify({'ok': False, 'error': 'Bot offline or unreachable'})
    return jsonify(result)


@app.route('/api/diagnose/<session_id>')
def api_diagnose(session_id):
    data = _bot_get(f'/diagnose?session_id={session_id}', timeout=10.0)
    if data is None:
        return jsonify({'error': 'Bot offline or unreachable'})
    return jsonify(data)


@app.route('/api/restart', methods=['POST'])
def api_restart():
    result = _bot_post('/restart', {})
    if result is None:
        return jsonify({'ok': False, 'error': 'Bot offline or unreachable'})
    return jsonify(result)


@app.route('/api/sync', methods=['POST'])
def api_sync():
    result = _bot_post('/sync', {}, timeout=15.0)
    if result is None:
        return jsonify({'ok': False, 'error': 'Bot offline or unreachable'})
    return jsonify(result)


@app.route('/api/logs')
def api_logs():
    data = _bot_get('/logs')
    if data is None:
        return jsonify({'lines': ['Bot offline or unreachable.']})
    return jsonify(data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=False)
