"""Install the supplied DC covers on empty chronicle pages.

Runs during normal portal initialization, using the portal's own database
configuration. It only affects the dcbn campaign and preserves authored pages,
existing covers, statuses, categories, and unrelated campaigns.
"""
from __future__ import annotations

import json
from pathlib import Path

from .db import Campaign, WikiPage, db


def seed_dcbn_artwork() -> int:
    campaign = Campaign.query.filter_by(slug='dcbn').first()
    if campaign is None:
        return 0
    manifest = json.loads((Path(__file__).parent / 'static/img/dcbn/manifest.json').read_text())
    pages = WikiPage.query.filter_by(campaign_id=campaign.id).all()
    known_categories = {category['slug'] for category in campaign.wiki_categories}
    created = 0
    if not campaign.cover_image_url:
        campaign.cover_image_url = '/static/img/dcbn/chronicle-home.jpg'
    for cover in manifest['covers']:
        category = cover.get('wiki_category')
        if not category or category not in known_categories:
            continue
        cover_url = f"/static/img/dcbn/{cover['slug']}.jpg"
        page = next((page for page in pages if
                     page.slug == cover['slug'] or
                     page.title.casefold() == cover['title'].casefold()), None)
        if page is not None:
            if not page.cover_image_url:
                page.cover_image_url = cover_url
            continue
        page = WikiPage(
            campaign_id=campaign.id, slug=cover['slug'], title=cover['title'],
            summary='', body_markdown='', category=category, status='upcoming',
            cover_image_url=cover_url, source='manual',
            updated_by='dcbn-artwork-setup',
        )
        db.session.add(page)
        pages.append(page)
        created += 1
    db.session.commit()
    return created
