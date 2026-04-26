from __future__ import annotations
from functools import wraps
from urllib.parse import urlparse
from flask import session, redirect, url_for, flash, current_app


def is_staff() -> bool:
    if session.get('authenticated'):
        return True
    discord_id = session.get('discord_id', '')
    return bool(discord_id) and discord_id in current_app.config.get('ALLOWED_DISCORD_IDS', set())


def is_logged_in() -> bool:
    return bool(session.get('discord_id') or session.get('authenticated'))


def get_staff_user() -> str:
    return session.get('staff_user') or session.get('discord_name', 'unknown')


def require_staff(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_staff():
            flash('Please sign in as staff to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def _safe_local_path(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return None
    if not parsed.path.startswith('/') or parsed.path.startswith('//'):
        return None
    path = parsed.path or '/'
    if parsed.query:
        path = f'{path}?{parsed.query}'
    return path


def pop_login_next(default: str) -> str:
    candidate = _safe_local_path(session.pop('login_next', ''))
    return candidate or default
