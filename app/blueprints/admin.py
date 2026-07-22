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

    synced, errors, conflicts = 0, [], []
    for category_slug, database_id in notion_dbs.items():
        try:
            count, skipped = _sync_notion_database(notion_token, database_id, c.id, category_slug, get_staff_user())
            synced += count
            conflicts.extend(skipped)
        except Exception as exc:
            errors.append(f'{category_slug}: {exc}')

    if errors:
        status = 'partial' if synced else 'error'
        detail = '; '.join(errors)
        flash(f'Sync completed with errors: {detail}', 'warning')
    else:
        status = 'partial' if conflicts else 'success'
        detail = f'Synced {synced} pages across {len(notion_dbs)} databases.'
        flash(f'Synced {synced} pages from Notion.', 'success')

    if conflicts:
        detail += f' Skipped {len(conflicts)} page(s) edited in the wiki since their last Notion edit: ' \
                  + ', '.join(conflicts) + '. Pull those into Notion before syncing again, or they’ll keep being skipped.'
        flash(f'{len(conflicts)} page(s) were newer in the wiki than in Notion and were NOT overwritten: '
              + ', '.join(conflicts), 'warning')

    db.session.add(SyncLog(
        campaign_id=c.id,
        status=status,
        pages_synced=synced,
        detail=detail,
        triggered_by=get_staff_user(),
    ))
    db.session.commit()
    return redirect(url_for('admin.campaign_edit', slug=slug))


@bp.route('/campaigns/<slug>/notion-pull', methods=['POST'])
def notion_pull(slug):
    """Push wiki pages that are newer than their Notion source back into Notion.

    The inverse of notion-sync: for any WikiPage linked to a Notion page where
    the wiki copy was edited more recently, overwrite Notion's title/content/
    cover with the wiki's version instead of the other way around.
    """
    c = Campaign.query.filter_by(slug=slug).first_or_404()
    token_var = c.notion_token_secret or 'NOTION_TOKEN'
    notion_token = os.environ.get(token_var, '')
    if not notion_token:
        flash(f'Notion token not found (env var: {token_var}).', 'danger')
        return redirect(url_for('admin.campaign_edit', slug=slug))

    from notion_client import Client
    notion = Client(auth=notion_token)

    pages = WikiPage.query.filter(
        WikiPage.campaign_id == c.id,
        WikiPage.notion_page_id.isnot(None),
        WikiPage.notion_page_id != '',
    ).all()

    pushed, up_to_date, errors = [], [], []
    for p in pages:
        try:
            notion_page = notion.pages.retrieve(page_id=p.notion_page_id)
        except Exception as exc:
            errors.append(f'{p.slug}: could not read from Notion ({exc})')
            continue

        notion_edited_at = _parse_notion_datetime(notion_page.get('last_edited_time'))
        wiki_edited_at = p.updated_at
        if wiki_edited_at and wiki_edited_at.tzinfo is None:
            wiki_edited_at = wiki_edited_at.replace(tzinfo=timezone.utc)

        if notion_edited_at and wiki_edited_at and notion_edited_at >= wiki_edited_at:
            up_to_date.append(p.slug)
            continue

        try:
            _push_wikipage_to_notion(notion, notion_page, p)
            pushed.append(p.slug)
        except Exception as exc:
            errors.append(f'{p.slug}: push failed ({exc})')

    if pushed:
        flash(f'Pushed {len(pushed)} page(s) to Notion: ' + ', '.join(pushed), 'success')
    if errors:
        flash(f'{len(errors)} page(s) failed to push: ' + '; '.join(errors), 'danger')
    if not pushed and not errors:
        flash('Nothing to pull — every linked page already matches or predates its Notion copy.', 'success')

    detail = f'Pushed {len(pushed)} page(s) to Notion, {len(up_to_date)} already up to date.'
    if errors:
        detail += ' Errors: ' + '; '.join(errors)
    db.session.add(SyncLog(
        campaign_id=c.id,
        status='error' if errors and not pushed else ('partial' if errors else 'success'),
        pages_synced=len(pushed),
        detail=detail,
        triggered_by=get_staff_user(),
    ))
    db.session.commit()
    return redirect(url_for('admin.campaign_edit', slug=slug))


def _push_wikipage_to_notion(notion, notion_page: dict, wiki_page) -> None:
    """Overwrite a Notion page's title, cover, and content with the wiki page's."""
    title_prop_name = None
    for name, prop in notion_page.get('properties', {}).items():
        if prop.get('type') == 'title':
            title_prop_name = name
            break

    update_payload = {}
    if title_prop_name:
        update_payload['properties'] = {
            title_prop_name: {'title': [{'type': 'text', 'text': {'content': wiki_page.title}}]}
        }
    if wiki_page.cover_image_url:
        update_payload['cover'] = {'type': 'external', 'external': {'url': wiki_page.cover_image_url}}
    if update_payload:
        notion.pages.update(page_id=wiki_page.notion_page_id, **update_payload)

    _clear_notion_page_content(notion, wiki_page.notion_page_id)
    blocks = _markdown_to_blocks(wiki_page.body_markdown or '')
    _append_notion_blocks(notion, wiki_page.notion_page_id, blocks)


def _clear_notion_page_content(notion, page_id: str) -> None:
    """Archive every existing child block of a Notion page."""
    cursor = None
    while True:
        kwargs = {'block_id': page_id, 'page_size': 100}
        if cursor:
            kwargs['start_cursor'] = cursor
        resp = notion.blocks.children.list(**kwargs)
        for block in resp.get('results', []):
            try:
                notion.blocks.delete(block_id=block['id'])
            except Exception:
                pass
        if not resp.get('has_more'):
            break
        cursor = resp.get('next_cursor')


def _append_notion_blocks(notion, page_id: str, blocks: list) -> None:
    """Append blocks to a Notion page, respecting the 100-block-per-call limit."""
    for i in range(0, len(blocks), 100):
        chunk = blocks[i:i + 100]
        if chunk:
            notion.blocks.children.append(block_id=page_id, children=chunk)


_MD_INLINE_RE = None


def _markdown_to_rich_text(text: str) -> list:
    """Parse **bold** / *italic* markdown in a single line into Notion rich_text spans."""
    import re
    global _MD_INLINE_RE
    if _MD_INLINE_RE is None:
        _MD_INLINE_RE = re.compile(r'(\*\*.+?\*\*|\*.+?\*)')
    if not text:
        return []

    spans = []
    for part in _MD_INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith('**') and part.endswith('**') and len(part) >= 4:
            content, annotations = part[2:-2], {'bold': True}
        elif part.startswith('*') and part.endswith('*') and len(part) >= 2:
            content, annotations = part[1:-1], {'italic': True}
        else:
            content, annotations = part, None
        # Notion rich_text content is capped at 2000 chars per span.
        for i in range(0, max(len(content), 1), 2000):
            chunk = content[i:i + 2000]
            span = {'type': 'text', 'text': {'content': chunk}}
            if annotations:
                span['annotations'] = annotations
            spans.append(span)
    return spans


_NOTION_CODE_LANGUAGES = {
    'plain text', 'python', 'javascript', 'typescript', 'json', 'markdown',
    'bash', 'shell', 'html', 'css', 'sql', 'yaml',
}


def _markdown_to_blocks(body_markdown: str) -> list:
    """Convert markdown (as produced by _blocks_to_markdown) back into Notion blocks."""
    import re

    def heading(level, text):
        return {'object': 'block', 'type': level, level: {'rich_text': _markdown_to_rich_text(text)}}

    blocks = []
    lines = body_markdown.split('\n')
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        if stripped.startswith('```'):
            lang = stripped[3:].strip().lower() or 'plain text'
            if lang not in _NOTION_CODE_LANGUAGES:
                lang = 'plain text'
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            blocks.append({
                'object': 'block', 'type': 'code',
                'code': {'rich_text': _markdown_to_rich_text('\n'.join(code_lines)), 'language': lang},
            })
            i += 1
            continue

        if stripped == '---':
            blocks.append({'object': 'block', 'type': 'divider', 'divider': {}})
        elif stripped.startswith('### '):
            blocks.append(heading('heading_3', stripped[4:]))
        elif stripped.startswith('## '):
            blocks.append(heading('heading_2', stripped[3:]))
        elif stripped.startswith('# '):
            blocks.append(heading('heading_1', stripped[2:]))
        elif stripped.startswith('> '):
            blocks.append({'object': 'block', 'type': 'quote',
                            'quote': {'rich_text': _markdown_to_rich_text(stripped[2:])}})
        elif re.match(r'^[-*]\s+', stripped):
            text = re.sub(r'^[-*]\s+', '', stripped)
            blocks.append({'object': 'block', 'type': 'bulleted_list_item',
                            'bulleted_list_item': {'rich_text': _markdown_to_rich_text(text)}})
        elif re.match(r'^\d+\.\s+', stripped):
            text = re.sub(r'^\d+\.\s+', '', stripped)
            blocks.append({'object': 'block', 'type': 'numbered_list_item',
                            'numbered_list_item': {'rich_text': _markdown_to_rich_text(text)}})
        elif stripped.startswith('!['):
            m = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', stripped)
            if m:
                caption, url = m.group(1), m.group(2)
                blocks.append({
                    'object': 'block', 'type': 'image',
                    'image': {
                        'type': 'external', 'external': {'url': url},
                        'caption': _markdown_to_rich_text(caption) if caption else [],
                    },
                })
        elif stripped:
            blocks.append({'object': 'block', 'type': 'paragraph',
                            'paragraph': {'rich_text': _markdown_to_rich_text(stripped)}})
        i += 1
    return blocks


def _sync_notion_database(token: str, database_id: str, campaign_id: int,
                           category: str, updated_by: str) -> tuple[int, list[str]]:
    """Fetch all pages from a Notion database and upsert into WikiPage table.

    Returns (pages_synced, [slugs skipped because the wiki copy is newer]).
    """
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
    skipped = []
    for page in pages:
        conflict_slug = _upsert_notion_page(notion, page, campaign_id, category, updated_by)
        if conflict_slug:
            skipped.append(conflict_slug)
        else:
            count += 1
    return count, skipped


def _upsert_notion_page(notion, page: dict, campaign_id: int,
                         category: str, updated_by: str) -> str | None:
    """Convert a Notion page to a WikiPage row.

    Returns the page's slug if it was SKIPPED due to a conflict (wiki edited
    after Notion), otherwise None (created or updated normally).
    """
    from app.db import WikiPage
    import re

    notion_id   = page['id']
    props       = page.get('properties', {})
    archived    = page.get('archived', False)
    notion_edited_at = _parse_notion_datetime(page.get('last_edited_time'))

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

    existing = WikiPage.query.filter_by(campaign_id=campaign_id, notion_page_id=notion_id).first()

    # Conflict guard: if someone edited this page in the wiki UI more recently
    # than it was last edited in Notion, don't clobber it — Notion isn't the
    # newer copy here, so leave the wiki content alone until it's pulled back.
    if existing and notion_edited_at and existing.updated_at:
        wiki_edited_at = existing.updated_at
        if wiki_edited_at.tzinfo is None:
            wiki_edited_at = wiki_edited_at.replace(tzinfo=timezone.utc)
        if wiki_edited_at > notion_edited_at:
            return existing.slug

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
    return None


def _parse_notion_datetime(value: str | None):
    """Parse a Notion ISO8601 timestamp (e.g. last_edited_time) into an aware UTC datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


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
