"""Tiny aiohttp status API served alongside the Discord bot.

Endpoints (all JSON):
  GET /health          — bot online status + current recording state
  GET /logs            — rolling buffer of recent log lines
  GET /sessions        — last N sessions from the DB
  GET /saved-sessions  — session dirs on disk with unprocessed audio
  POST /reprocess      — trigger reprocessing of a saved session
"""
from __future__ import annotations

import asyncio
import collections
import json
import logging
import os
from pathlib import Path
from typing import Callable, Awaitable

from aiohttp import web

# Rolling log buffer — populated by LogBufferHandler below
_log_buffer: collections.deque[str] = collections.deque(maxlen=300)

# Set by start() to references of bot.py's live dicts
_active: dict = {}
_processing: dict = {}
_reprocess_fn: Callable[[str], Awaitable[bool]] | None = None
_sync_fn: Callable[[], Awaitable[None]] | None = None
_sessions_dir: Path | None = None


# ── Log capture ───────────────────────────────────────────────────────────────

class LogBufferHandler(logging.Handler):
    """Captures log records into the in-memory buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        _log_buffer.append(self.format(record))


# ── HTTP handlers ─────────────────────────────────────────────────────────────

async def _handle_health(request: web.Request) -> web.Response:
    recording = bool(_active)
    processing = dict(_processing)  # snapshot
    payload: dict = {'online': True, 'recording': recording, 'processing': processing}

    if recording:
        state = next(iter(_active.values()))
        sink = state['sink']
        elapsed_ms = sink.session_duration_ms()
        h, rem = divmod(elapsed_ms // 1000, 3600)
        m, s = divmod(rem, 60)
        payload.update({
            'campaign': state['campaign'],
            'elapsed': f'{h:02d}:{m:02d}:{s:02d}',
            'speakers': list(sink.user_names.values()),
        })

    return web.json_response(payload)


async def _handle_logs(request: web.Request) -> web.Response:
    return web.json_response({'lines': list(_log_buffer)})


async def _handle_saved_sessions(request: web.Request) -> web.Response:
    if _sessions_dir is None or not _sessions_dir.exists():
        return web.json_response({'sessions': []})
    sessions = []
    for d in sorted(_sessions_dir.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        lsm_files = list(d.glob('*.lsm'))
        if not lsm_files:
            continue
        meta_path = d / 'meta.json'
        meta: dict = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
        sessions.append({
            'session_id': d.name,
            'campaign': meta.get('campaign', '?'),
            'started_at': meta.get('started_at'),
            'speaker_count': len(lsm_files),
        })
    return web.json_response({'sessions': sessions})


async def _handle_reprocess(request: web.Request) -> web.Response:
    if _reprocess_fn is None:
        return web.json_response({'ok': False, 'error': 'Not available'}, status=503)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({'ok': False, 'error': 'Invalid JSON'}, status=400)
    session_id = data.get('session_id', '').strip()
    if not session_id:
        return web.json_response({'ok': False, 'error': 'session_id required'}, status=400)
    ok = await _reprocess_fn(session_id)
    return web.json_response({'ok': ok})


async def _handle_diagnose(request: web.Request) -> web.Response:
    session_id = request.rel_url.query.get('session_id', '').strip()
    if not session_id or _sessions_dir is None:
        return web.json_response({'error': 'session_id required'}, status=400)
    session_dir = _sessions_dir / session_id
    if not session_dir.exists():
        return web.json_response({'error': 'Session not found'}, status=404)
    from diagnose_session import analyse_session
    stats = analyse_session(session_dir)
    return web.json_response(stats)


async def _handle_restart(request: web.Request) -> web.Response:
    async def _do_exit() -> None:
        await asyncio.sleep(0.5)
        os._exit(0)
    asyncio.create_task(_do_exit())
    return web.json_response({'ok': True})


async def _handle_sync(request: web.Request) -> web.Response:
    if _sync_fn is None:
        return web.json_response({'ok': False, 'error': 'Not available'}, status=503)
    try:
        await _sync_fn()
        return web.json_response({'ok': True})
    except Exception as exc:
        return web.json_response({'ok': False, 'error': str(exc)})


async def _handle_sessions(request: web.Request) -> web.Response:
    from db import execute
    limit = int(request.rel_url.query.get('limit', 10))
    rows = execute(
        """SELECT wp.title, wp.slug, wp.created_at, c.slug AS campaign_slug, c.name AS campaign_name
           FROM wiki_pages wp
           JOIN campaigns c ON c.id = wp.campaign_id
           WHERE wp.category = 'sessions'
           ORDER BY wp.created_at DESC
           LIMIT ?""",
        [limit],
    )
    return web.json_response({'sessions': rows})


# ── Server lifecycle ──────────────────────────────────────────────────────────

async def start(
    active_sessions: dict,
    processing_state: dict,
    port: int = 8765,
    reprocess_fn: Callable[[str], Awaitable[bool]] | None = None,
    sync_fn: Callable[[], Awaitable[None]] | None = None,
    sessions_dir: Path | None = None,
) -> None:
    """Start the HTTP server. Pass bot.py's _active and _processing dicts directly."""
    global _active, _processing, _reprocess_fn, _sync_fn, _sessions_dir
    _active = active_sessions
    _processing = processing_state  # same object — mutations in bot.py are visible here
    _reprocess_fn = reprocess_fn
    _sync_fn = sync_fn
    _sessions_dir = sessions_dir

    app = web.Application()
    app.router.add_get('/health', _handle_health)
    app.router.add_get('/logs', _handle_logs)
    app.router.add_get('/sessions', _handle_sessions)
    app.router.add_get('/saved-sessions', _handle_saved_sessions)
    app.router.add_post('/reprocess', _handle_reprocess)
    app.router.add_get('/diagnose', _handle_diagnose)
    app.router.add_post('/restart', _handle_restart)
    app.router.add_post('/sync', _handle_sync)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.getLogger('orpheus').info('Status API listening on :%d', port)
