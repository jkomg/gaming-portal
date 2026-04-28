"""Tiny aiohttp status API served alongside the Discord bot.

Endpoints (all JSON):
  GET /health   — bot online status + current recording state
  GET /logs     — rolling buffer of recent log lines
  GET /sessions — last N sessions from the DB
"""
from __future__ import annotations

import collections
import logging
import time

from aiohttp import web

# Rolling log buffer — populated by LogBufferHandler below
_log_buffer: collections.deque[str] = collections.deque(maxlen=300)

# Set by start() to references of bot.py's live dicts
_active: dict = {}
_processing: dict = {}


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

async def start(active_sessions: dict, processing_state: dict, port: int = 8765) -> None:
    """Start the HTTP server. Pass bot.py's _active and _processing dicts directly."""
    global _active, _processing
    _active = active_sessions
    _processing = processing_state  # same object — mutations in bot.py are visible here

    app = web.Application()
    app.router.add_get('/health', _handle_health)
    app.router.add_get('/logs', _handle_logs)
    app.router.add_get('/sessions', _handle_sessions)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.getLogger('lasombra').info('Status API listening on :%d', port)
