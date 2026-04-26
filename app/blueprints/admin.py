"""Admin panel — campaign management, wiki oversight, Notion sync."""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
)
from app.auth import require_staff, get_staff_user
from app.db import db, Campaign, WikiPage, SyncLog, CAMPAIGN_STATUSES, CAMPAIGN_STATUS_LABELS

bp = Blueprint('admin', __name__)


@bp.before_request
@require_staff
def _require_staff():
    pass


# ── One-time fix: correct Keys/Vecna category mappings ─────────────────────────

@bp.route('/fix-category-mappings', methods=['POST'])
def fix_category_mappings():
    """Apply correct Notion DB → category mappings for Keys and Vecna."""
    fixes = {
        'keys': {
            'notion_databases': {
                'characters': '3483a3e5-cab1-817a-a15a-ffc8223aa1bf',
                'npcs':       '3483a3e5-cab1-81ac-b84f-e62686a85b51',
                'chapters':   '3483a3e5-cab1-81e8-a61d-c540cbe7cd26',
            },
            'wiki_categories': [
                {'slug': 'characters', 'name': 'Characters', 'icon': 'bi-person-fill'},
                {'slug': 'npcs',       'name': 'NPCs',       'icon': 'bi-person-lines-fill'},
                {'slug': 'chapters',   'name': 'Chapters',   'icon': 'bi-book-fill'},
            ],
        },
        'vecna': {
            'notion_databases': {
                'characters': '3483a3e5-cab1-81a2-a4bf-c05bdb1f35b6',
                'npcs':       '3483a3e5-cab1-8157-aa2d-e0f26e067598',
                'chapters':   '3483a3e5-cab1-8102-b08c-db68df72deab',
            },
            'wiki_categories': [
                {'slug': 'characters', 'name': 'Characters', 'icon': 'bi-person-fill'},
                {'slug': 'npcs',       'name': 'NPCs',       'icon': 'bi-person-lines-fill'},
                {'slug': 'chapters',   'name': 'Chapters',   'icon': 'bi-book-fill'},
            ],
        },
        'gotw': {
            'notion_databases': {
                'characters': 'c2d7cdd8-5938-4ee2-9986-02580d84f2ac',
                'locations':  '9007ee36-f931-4298-9986-b82c7b6e2a53',
                'factions':   '63c814ca-8ad1-437b-99f0-f10a44819820',
                'jobs':       '2b44db63-34bb-4800-b7fa-7c7c5352d9af',
            },
            'wiki_categories': [
                {'slug': 'characters', 'name': 'Characters', 'icon': 'bi-person-fill'},
                {'slug': 'locations',  'name': 'Locations',  'icon': 'bi-geo-alt-fill'},
                {'slug': 'factions',   'name': 'Factions',   'icon': 'bi-shield-fill'},
                {'slug': 'jobs',       'name': 'Jobs',       'icon': 'bi-briefcase-fill'},
                {'slug': 'lore',       'name': 'Lore',       'icon': 'bi-book-fill'},
            ],
        },
    }
    updated = []
    for slug, data in fixes.items():
        c = Campaign.query.filter_by(slug=slug).first()
        if c:
            c._notion_databases = json.dumps(data['notion_databases'])
            c._wiki_categories  = json.dumps(data['wiki_categories'])
            c.updated_at        = datetime.now(timezone.utc)
            updated.append(c.name)
    db.session.commit()
    flash(f'Updated category mappings for: {", ".join(updated)}. Run Notion sync for each to reclassify pages.', 'success')
    return redirect(url_for('admin.index'))


@bp.route('/')
def index():
    campaigns = Campaign.query.order_by(Campaign.sort_order, Campaign.name).all()
    stats = {c.slug: WikiPage.query.filter_by(campaign_id=c.id).count() for c in campaigns}
    return render_template('admin/index.html', campaigns=campaigns,
                           stats=stats, status_labels=CAMPAIGN_STATUS_LABELS)


# ── Campaign CRUD ──────────────────────────────────────────────────────────────

@bp.route('/campaigns/new', methods=['GET', 'POST'])
def campaign_new():
    if request.method == 'POST':
        slug = request.form.get('slug', '').strip().lower()
        name = request.form.get('name', '').strip()
        if not slug or not name:
            flash('Slug and name are required.', 'danger')
            return redirect(url_for('admin.campaign_new'))
        if Campaign.query.filter_by(slug=slug).first():
            flash(f'A campaign with slug "{slug}" already exists.', 'danger')
            return redirect(url_for('admin.campaign_new'))
        c = Campaign(
            slug=slug,
            name=name,
            system=request.form.get('system', '').strip(),
            status=request.form.get('status', 'upcoming'),
            description=request.form.get('description', '').strip(),
            cover_image_url=request.form.get('cover_image_url', '').strip(),
            wiki_url=request.form.get('wiki_url', '').strip(),
            wiki_enabled=request.form.get('wiki_enabled') == '1',
            sort_order=int(request.form.get('sort_order', 0) or 0),
        )
        db.session.add(c)
        db.session.commit()
        flash(f'Campaign "{name}" created.', 'success')
        return redirect(url_for('admin.campaign_edit', slug=slug))
    return render_template('admin/campaign_form.html', campaign=None,
                           statuses=CAMPAIGN_STATUSES, status_labels=CAMPAIGN_STATUS_LABELS,
                           sync_logs=[])


@bp.route('/campaigns/<slug>/edit', methods=['GET', 'POST'])
def campaign_edit(slug):
    c = Campaign.query.filter_by(slug=slug).first_or_404()
    if request.method == 'POST':
        c.name            = request.form.get('name', c.name).strip() or c.name
        c.system          = request.form.get('system', '').strip()
        c.status          = request.form.get('status', c.status)
        c.description     = request.form.get('description', '').strip()
        c.cover_image_url = request.form.get('cover_image_url', '').strip()
        c.wiki_url        = request.form.get('wiki_url', '').strip()
        c.wiki_enabled    = request.form.get('wiki_enabled') == '1'
        c.sort_order      = int(request.form.get('sort_order', c.sort_order) or 0)
        c.updated_at      = datetime.now(timezone.utc)
        # Wiki categories — stored as JSON
        cats_raw = request.form.get('wiki_categories_json', '').strip()
        if cats_raw:
            try:
                c.wiki_categories = json.loads(cats_raw)
            except ValueError:
                flash('Invalid wiki categories JSON — not saved.', 'warning')
        # Notion databases mapping
        notion_raw = request.form.get('notion_databases_json', '').strip()
        if notion_raw:
            try:
                c.notion_databases = json.loads(notion_raw)
            except ValueError:
                flash('Invalid Notion databases JSON — not saved.', 'warning')
        c.notion_token_secret = request.form.get('notion_token_secret', '').strip()
        db.session.commit()
        flash(f'Campaign "{c.name}" saved.', 'success')
        return redirect(url_for('admin.campaign_edit', slug=slug))
    sync_logs = (SyncLog.query.filter_by(campaign_id=c.id)
                 .order_by(SyncLog.triggered_at.desc()).limit(15).all())
    return render_template('admin/campaign_form.html', campaign=c,
                           statuses=CAMPAIGN_STATUSES, status_labels=CAMPAIGN_STATUS_LABELS,
                           sync_logs=sync_logs)


@bp.route('/campaigns/<slug>/status', methods=['POST'])
def campaign_set_status(slug):
    c = Campaign.query.filter_by(slug=slug).first_or_404()
    new_status = request.form.get('status', '').strip()
    if new_status not in CAMPAIGN_STATUSES:
        flash('Invalid status.', 'danger')
    else:
        c.status     = new_status
        c.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash(f'"{c.name}" set to {CAMPAIGN_STATUS_LABELS[new_status]}.', 'success')
    return redirect(url_for('admin.index'))


@bp.route('/campaigns/<slug>/delete', methods=['POST'])
def campaign_delete(slug):
    c = Campaign.query.filter_by(slug=slug).first_or_404()
    name = c.name
    db.session.delete(c)
    db.session.commit()
    flash(f'Campaign "{name}" deleted along with all its wiki pages.', 'success')
    return redirect(url_for('admin.index'))


# ── Notion Sync ────────────────────────────────────────────────────────────────

@bp.route('/campaigns/<slug>/notion-sync', methods=['POST'])
def notion_sync(slug):
    c = Campaign.query.filter_by(slug=slug).first_or_404()
    notion_dbs = c.notion_databases
    if not notion_dbs:
        flash('No Notion databases configured for this campaign.', 'warning')
        return redirect(url_for('admin.campaign_edit', slug=slug))

    # Resolve token: campaign can specify an env var name or use NOTION_TOKEN
    token_var = c.notion_token_secret or 'NOTION_TOKEN'
    notion_token = os.environ.get(token_var, '')
    if not notion_token:
        flash(f'Notion token not found (env var: {token_var}).', 'danger')
        return redirect(url_for('admin.campaign_edit', slug=slug))

    synced, errors = 0, []
    for category_slug, database_id in notion_dbs.items():
        try:
            count = _sync_notion_database(notion_token, database_id, c.id, category_slug, get_staff_user())
            synced += count
        except Exception as exc:
            errors.append(f'{category_slug}: {exc}')

    if errors:
        status = 'partial' if synced else 'error'
        detail = '; '.join(errors)
        flash(f'Sync completed with errors: {detail}', 'warning')
    else:
        status = 'success'
        detail = f'Synced {synced} pages across {len(notion_dbs)} databases.'
        flash(f'Synced {synced} pages from Notion.', 'success')

    db.session.add(SyncLog(
        campaign_id=c.id,
        status=status,
        pages_synced=synced,
        detail=detail,
        triggered_by=get_staff_user(),
    ))
    db.session.commit()
    return redirect(url_for('admin.campaign_edit', slug=slug))


def _sync_notion_database(token: str, database_id: str, campaign_id: int,
                           category: str, updated_by: str) -> int:
    """Fetch all pages from a Notion database and upsert into WikiPage table."""
    from notion_client import Client
    notion = Client(auth=token)

    pages = []
    cursor = None
    while True:
        kwargs = {'database_id': database_id, 'page_size': 100}
        if cursor:
            kwargs['start_cursor'] = cursor
        resp = notion.databases.query(**kwargs)
        pages.extend(resp.get('results', []))
        if not resp.get('has_more'):
            break
        cursor = resp.get('next_cursor')

    count = 0
    for page in pages:
        _upsert_notion_page(notion, page, campaign_id, category, updated_by)
        count += 1
    return count


def _upsert_notion_page(notion, page: dict, campaign_id: int,
                         category: str, updated_by: str) -> None:
    """Convert a Notion page to a WikiPage row."""
    from app.db import WikiPage
    import re

    notion_id   = page['id']
    props       = page.get('properties', {})
    archived    = page.get('archived', False)

    # Extract title from any title-type property
    title = ''
    for prop in props.values():
        if prop.get('type') == 'title':
            title = ''.join(t.get('plain_text', '') for t in prop.get('title', []))
            break
    if not title:
        return  # skip untitled pages

    # Slug from title
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[\s_]+', '-', slug).strip('-')
    if not slug:
        return

    # Fetch page content (blocks → markdown)
    body_md = _blocks_to_markdown(notion, page['id'])

    # Cover image
    cover_url = ''
    cover = page.get('cover')
    if cover:
        cover_url = (cover.get('external') or cover.get('file') or {}).get('url', '')

    # Summary: first non-empty paragraph, truncated
    summary = ''
    for line in body_md.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            summary = line[:200]
            break

    page_status = 'archived' if archived else 'active'

    existing = WikiPage.query.filter_by(campaign_id=campaign_id, notion_page_id=notion_id).first()
    if existing:
        existing.title           = title
        existing.summary         = summary
        existing.body_markdown   = body_md
        existing.cover_image_url = cover_url
        existing.category        = category
        existing.status          = page_status
        existing.updated_at      = datetime.now(timezone.utc)
        existing.updated_by      = updated_by
        existing.source          = 'notion'
    else:
        # Ensure slug is unique within campaign
        base_slug, i = slug, 1
        while WikiPage.query.filter_by(campaign_id=campaign_id, slug=slug).first():
            i += 1
            slug = f'{base_slug}-{i}'
        db.session.add(WikiPage(
            campaign_id=campaign_id,
            slug=slug,
            title=title,
            summary=summary,
            body_markdown=body_md,
            cover_image_url=cover_url,
            category=category,
            status=page_status,
            source='notion',
            notion_page_id=notion_id,
            updated_by=updated_by,
        ))
    db.session.commit()


def _blocks_to_markdown(notion, page_id: str) -> str:
    """Fetch Notion blocks and convert to markdown (best-effort)."""
    try:
        blocks = notion.blocks.children.list(block_id=page_id, page_size=100).get('results', [])
    except Exception:
        return ''
    lines = []
    for block in blocks:
        bt = block.get('type', '')
        data = block.get(bt, {})
        rich = data.get('rich_text', [])
        text = ''.join(t.get('plain_text', '') for t in rich)
        if bt == 'heading_1':
            lines.append(f'# {text}')
        elif bt == 'heading_2':
            lines.append(f'## {text}')
        elif bt == 'heading_3':
            lines.append(f'### {text}')
        elif bt in ('paragraph',):
            lines.append(text)
        elif bt == 'bulleted_list_item':
            lines.append(f'- {text}')
        elif bt == 'numbered_list_item':
            lines.append(f'1. {text}')
        elif bt == 'quote':
            lines.append(f'> {text}')
        elif bt == 'divider':
            lines.append('---')
        elif bt == 'code':
            lang = data.get('language', '')
            lines.append(f'```{lang}\n{text}\n```')
        elif bt == 'image':
            img = data.get('external') or data.get('file') or {}
            url = img.get('url', '')
            caption = ''.join(t.get('plain_text', '') for t in data.get('caption', []))
            lines.append(f'![{caption}]({url})')
        else:
            if text:
                lines.append(text)
        lines.append('')  # blank line between blocks
    return '\n'.join(lines).strip()
