"""Token-authenticated endpoints for unattended callers (e.g. Cloud Scheduler).

Not part of the staff-session-gated admin blueprint -- these routes check a
shared bearer token (INTERNAL_SYNC_TOKEN) instead, since a scheduled job has
no browser session to authenticate with.
"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, request

from app.db import Campaign
from app.blueprints.admin import run_campaign_notion_sync

bp = Blueprint('internal', __name__)


def init_app(csrf) -> None:
    csrf.exempt(bp)


def _check_token() -> bool:
    expected = os.environ.get('INTERNAL_SYNC_TOKEN', '')
    if not expected:
        return False
    auth = request.headers.get('Authorization', '')
    return auth == f'Bearer {expected}'


@bp.route('/notion-sync-all', methods=['POST'])
def notion_sync_all():
    if not _check_token():
        return jsonify({'error': 'unauthorized'}), 401

    results = []
    for c in Campaign.query.filter(Campaign.status != 'archived').all():
        if not c.notion_databases:
            continue
        status, detail, synced = run_campaign_notion_sync(c, 'scheduled-sync')
        results.append({'campaign': c.slug, 'status': status, 'pages_synced': synced, 'detail': detail})

    return jsonify({'campaigns_synced': len(results), 'results': results})
