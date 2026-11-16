"""Seed the Scum and Villainy campaign on startup, preserving authored wiki edits.

The fixture ships with the image so a Cloud Run deployment creates the campaign
and draft GM pages on its normal database without a separate manual import.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'scripts/fixtures/sav_campaign.json'

SOURCE = 'sav-seed'


def load_payload():
    payload = json.loads(FIXTURE.read_text())
    slugs = [p['slug'] for p in payload['pages']]
    if len(slugs) != len(set(slugs)):
        raise ValueError('Duplicate page slug')
    for page in payload['pages']:
        if page['category'] == 'gm' and page['status'] != 'draft':
            raise ValueError('GM preparation must stay draft')
    return payload


def seed(payload=None, refresh=False):
    """Run in an app context; one transaction, no deletion or unrelated updates."""
    from app.db import Campaign, WikiPage, db
    if payload is None:
        payload = load_payload()
    data = payload['campaign']
    try:
        campaign = Campaign.query.filter_by(slug=data['slug']).first()
        if campaign is None:
            campaign = Campaign(**{k: v for k, v in data.items() if k != 'wiki_categories'},
                                wiki_enabled=True, sort_order=11)
            campaign.wiki_categories = data['wiki_categories']
            db.session.add(campaign)
            db.session.flush()
        else:
            # Add newly introduced categories without replacing staff-customized ones.
            current = campaign.wiki_categories
            existing = {category['slug'] for category in current}
            campaign.wiki_categories = current + [
                category for category in data['wiki_categories'] if category['slug'] not in existing
            ]
        if not campaign.cover_image_url:
            campaign.cover_image_url = data.get('cover_image_url', '')
        for page in payload['pages']:
            row = WikiPage.query.filter_by(campaign_id=campaign.id, slug=page['slug']).first()
            if row is not None:
                if not refresh:
                    if row.source == SOURCE and not row.cover_image_url:
                        row.cover_image_url = page.get('cover_image_url', '')
                    continue
                if row.source != SOURCE:
                    raise ValueError(f'Refusing to replace non-imported page: {row.slug}')
                for key, value in page.items():
                    setattr(row, key, value)
                from datetime import datetime
                row.updated_at = datetime.utcnow()
            else:
                db.session.add(WikiPage(campaign_id=campaign.id, source=SOURCE, **page))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
