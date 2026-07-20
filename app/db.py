from __future__ import annotations
import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Campaign status values
CAMPAIGN_STATUSES = ('draft', 'active', 'hiatus', 'complete', 'upcoming')
CAMPAIGN_STATUS_LABELS = {
    'draft':    'Draft (staff only)',
    'active':   'Active',
    'hiatus':   'On Hiatus',
    'complete': 'Complete',
    'upcoming': 'Upcoming',
}

# Wiki page status values
WIKI_STATUSES = ('draft', 'active', 'upcoming', 'completed', 'archived')
WIKI_STATUS_LABELS = {
    'draft':     'Draft',
    'active':    'Active',
    'upcoming':  'Upcoming',
    'completed': 'Completed',
    'archived':  'Archived',
}
WIKI_PUBLIC_STATUSES = ('active', 'upcoming', 'completed')

# Default wiki categories — campaigns can override
DEFAULT_WIKI_CATEGORIES = [
    {'slug': 'locations',   'name': 'Locations',   'icon': 'bi-geo-alt-fill'},
    {'slug': 'characters',  'name': 'Characters',  'icon': 'bi-person-fill'},
    {'slug': 'factions',    'name': 'Factions',    'icon': 'bi-shield-fill'},
    {'slug': 'lore',        'name': 'Lore',        'icon': 'bi-book-fill'},
]


class Campaign(db.Model):
    __tablename__ = 'campaigns'
    id            = db.Column(db.Integer, primary_key=True)
    slug          = db.Column(db.String(50), nullable=False, unique=True, index=True)
    name          = db.Column(db.String(200), nullable=False)
    system        = db.Column(db.String(200), default='')
    status        = db.Column(db.String(20), default='active', nullable=False, index=True)
    description   = db.Column(db.Text, default='')
    cover_image_url = db.Column(db.Text, default='')
    # If set, "Visit Wiki" links here instead of the built-in /slug/wiki
    wiki_url      = db.Column(db.Text, default='')
    wiki_enabled  = db.Column(db.Boolean, default=True, nullable=False)
    # JSON list of {slug, name, icon} — if empty, DEFAULT_WIKI_CATEGORIES is used
    _wiki_categories = db.Column('wiki_categories', db.Text, default='')
    # JSON dict of {category_slug: notion_database_id}
    _notion_databases = db.Column('notion_databases', db.Text, default='')
    notion_token_secret = db.Column(db.String(200), default='')  # env var name holding the token
    sort_order    = db.Column(db.Integer, default=0)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow)

    wiki_pages = db.relationship('WikiPage', backref='campaign', lazy='dynamic',
                                  cascade='all, delete-orphan')

    @property
    def wiki_categories(self) -> list:
        if self._wiki_categories:
            try:
                return json.loads(self._wiki_categories)
            except Exception:
                pass
        return DEFAULT_WIKI_CATEGORIES

    @wiki_categories.setter
    def wiki_categories(self, value):
        self._wiki_categories = json.dumps(value) if value else ''

    @property
    def notion_databases(self) -> dict:
        if self._notion_databases:
            try:
                return json.loads(self._notion_databases)
            except Exception:
                pass
        return {}

    @notion_databases.setter
    def notion_databases(self, value):
        self._notion_databases = json.dumps(value) if value else ''

    @property
    def effective_wiki_url(self) -> str:
        """The URL to link to for this campaign's wiki."""
        if self.wiki_url:
            return self.wiki_url
        if self.wiki_enabled:
            from flask import url_for
            return url_for('wiki.index', campaign_slug=self.slug)
        return ''


class SyncLog(db.Model):
    __tablename__ = 'sync_logs'
    id           = db.Column(db.Integer, primary_key=True)
    campaign_id  = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False, index=True)
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow)
    status       = db.Column(db.String(20), default='success')  # success / error / partial
    pages_synced = db.Column(db.Integer, default=0)
    detail       = db.Column(db.Text, default='')
    triggered_by = db.Column(db.String(100), default='')


class WikiPage(db.Model):
    __tablename__ = 'wiki_pages'
    __table_args__ = (
        db.UniqueConstraint('campaign_id', 'slug', name='uq_campaign_wiki_slug'),
        db.Index('ix_wiki_pages_campaign_slug', 'campaign_id', 'slug'),
    )
    id              = db.Column(db.Integer, primary_key=True)
    campaign_id     = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False, index=True)
    slug            = db.Column(db.String(200), nullable=False)
    title           = db.Column(db.String(300), nullable=False)
    summary         = db.Column(db.String(500), default='')
    body_markdown   = db.Column(db.Text, default='')
    category        = db.Column(db.String(100), default='', index=True)
    cover_image_url = db.Column(db.Text, default='')
    status          = db.Column(db.String(20), default='active', nullable=False, index=True)
    source          = db.Column(db.String(50), default='manual')
    notion_page_id  = db.Column(db.String(100), default='', index=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by      = db.Column(db.String(100), default='')
