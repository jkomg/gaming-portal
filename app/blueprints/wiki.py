"""Per-campaign wiki — public read, staff write."""
from __future__ import annotations
import re
import html as _html_mod
from datetime import datetime, timezone
from html.parser import HTMLParser
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort, g,
)
import markdown as md_lib
from markupsafe import Markup
from app.auth import require_staff, get_staff_user, is_staff as _is_staff
from app.db import db, Campaign, WikiPage, WIKI_STATUSES, WIKI_STATUS_LABELS, WIKI_PUBLIC_STATUSES

bp = Blueprint('wiki', __name__)


# ── Campaign resolution ────────────────────────────────────────────────────────

@bp.url_value_preprocessor
def _pull_campaign(endpoint, values):
    slug = values.pop('campaign_slug', None)
    if slug:
        g.campaign = Campaign.query.filter_by(slug=slug).first_or_404()
    else:
        g.campaign = None


@bp.url_defaults
def _add_campaign(endpoint, values):
    if 'campaign_slug' not in values and g.get('campaign'):
        values['campaign_slug'] = g.campaign.slug


@bp.context_processor
def _wiki_context():
    c = g.get('campaign')
    return {
        'campaign': c,
        'wiki_categories': c.wiki_categories if c else [],
        'wiki_statuses': WIKI_STATUSES,
        'wiki_status_labels': WIKI_STATUS_LABELS,
    }


# ── Markdown rendering ─────────────────────────────────────────────────────────

_ALLOWED_TAGS = frozenset({
    'h1','h2','h3','h4','h5','h6','p','br','hr',
    'ul','ol','li','strong','em','del','s',
    'a','img','blockquote','pre','code',
    'table','thead','tbody','tr','th','td',
    'div','span',
})
_ALLOWED_ATTRS = {
    'a':   ['href', 'title', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    '*':   ['class', 'id'],
}
_VOID_TAGS = frozenset({'br', 'hr', 'img'})
_JS_RE = re.compile(r'^\s*javascript:', re.I)


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self._out: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in _ALLOWED_TAGS:
            self._skip += 1
            return
        if self._skip:
            return
        allowed = _ALLOWED_ATTRS.get(tag, []) + _ALLOWED_ATTRS['*']
        safe = ''
        for name, value in attrs:
            name = name.lower()
            if name not in allowed:
                continue
            value = value or ''
            if name == 'href' and _JS_RE.match(value):
                continue
            safe += f' {name}="{_html_mod.escape(value)}"'
        self._out.append(f'<{tag}{safe}>')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag not in _ALLOWED_TAGS:
            if self._skip:
                self._skip -= 1
            return
        if self._skip:
            return
        if tag not in _VOID_TAGS:
            self._out.append(f'</{tag}>')

    def handle_data(self, data):
        if not self._skip:
            self._out.append(_html_mod.escape(data))

    def handle_entityref(self, name):
        if not self._skip:
            self._out.append(f'&{name};')

    def handle_charref(self, name):
        if not self._skip:
            self._out.append(f'&#{name};')

    def get_output(self):
        return ''.join(self._out)


def _render_md(text: str) -> Markup:
    text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text or '')
    raw = md_lib.markdown(text, extensions=['extra', 'toc'], output_format='html')
    s = _Sanitizer()
    s.feed(raw)
    return Markup(s.get_output())


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return re.sub(r'-+', '-', text).strip('-')


def _unique_slug(campaign_id: int, base: str) -> str:
    slug, i = base, 1
    while WikiPage.query.filter_by(campaign_id=campaign_id, slug=slug).first():
        i += 1
        slug = f'{base}-{i}'
    return slug


def _excerpt(body: str, query: str, context: int = 160) -> str:
    plain = re.sub(r'[#*_`\[\]!]', '', body).replace('\n', ' ')
    lower = plain.lower()
    idx = lower.find(query.lower())
    if idx == -1:
        return plain[:context].strip() + ('…' if len(plain) > context else '')
    start = max(0, idx - context // 2)
    end = min(len(plain), idx + len(query) + context // 2)
    snippet = plain[start:end].strip()
    if start > 0:
        snippet = '…' + snippet
    if end < len(plain):
        snippet += '…'
    return snippet


# ── Public routes ──────────────────────────────────────────────────────────────

@bp.route('/')
def index():
    c = g.campaign
    recent = (WikiPage.query
              .filter_by(campaign_id=c.id)
              .filter(WikiPage.status.in_(WIKI_PUBLIC_STATUSES))
              .order_by(WikiPage.updated_at.desc())
              .limit(6).all())
    counts = {}
    for cat in c.wiki_categories:
        counts[cat['slug']] = (WikiPage.query
                               .filter_by(campaign_id=c.id, category=cat['slug'])
                               .filter(WikiPage.status.in_(WIKI_PUBLIC_STATUSES))
                               .count())
    return render_template('wiki/index.html', recent=recent, counts=counts)


@bp.route('/search')
def search():
    q = request.args.get('q', '').strip()
    results = []
    if q:
        c = g.campaign
        visible = [] if _is_staff() else [WikiPage.status.in_(WIKI_PUBLIC_STATUSES)]
        pattern = f'%{q}%'
        pages = (WikiPage.query
                 .filter_by(campaign_id=c.id)
                 .filter(*visible)
                 .filter(db.or_(WikiPage.title.ilike(pattern),
                                WikiPage.body_markdown.ilike(pattern)))
                 .order_by(WikiPage.title)
                 .limit(50).all())
        for p in pages:
            results.append({
                'page': p,
                'excerpt': _excerpt(p.body_markdown or '', q),
                'title_match': q.lower() in p.title.lower(),
            })
        results.sort(key=lambda r: (not r['title_match'], r['page'].title.lower()))
    return render_template('wiki/search.html', q=q, results=results)


@bp.route('/category/<category>')
def category(category):
    c = g.campaign
    cats = {cat['slug']: cat for cat in c.wiki_categories}
    if category not in cats:
        abort(404)
    query = WikiPage.query.filter_by(campaign_id=c.id, category=category)
    if not _is_staff():
        query = query.filter(WikiPage.status.in_(WIKI_PUBLIC_STATUSES))
    pages = query.order_by(WikiPage.title).all()
    return render_template('wiki/category.html', pages=pages,
                           active_category=category,
                           category_name=cats[category]['name'])


@bp.route('/<page_slug>')
def page(page_slug):
    c = g.campaign
    p = WikiPage.query.filter_by(campaign_id=c.id, slug=page_slug).first_or_404()
    if p.status not in WIKI_PUBLIC_STATUSES and not _is_staff():
        abort(404)
    body_html = _render_md(p.body_markdown)
    return render_template('wiki/page.html', page=p, body_html=body_html)


# ── Staff routes ───────────────────────────────────────────────────────────────

@bp.route('/new', methods=['GET', 'POST'])
@require_staff
def new_page():
    c = g.campaign
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Title is required.', 'danger')
            return redirect(url_for('wiki.new_page'))
        base_slug = _slugify(request.form.get('slug', '').strip() or title)
        slug = _unique_slug(c.id, base_slug)
        new_status = request.form.get('status', 'active')
        if new_status not in WIKI_STATUSES:
            new_status = 'active'
        p = WikiPage(
            campaign_id=c.id,
            slug=slug,
            title=title,
            summary=request.form.get('summary', '').strip(),
            body_markdown=request.form.get('body_markdown', ''),
            category=request.form.get('category', '').strip(),
            cover_image_url=request.form.get('cover_image_url', '').strip(),
            status=new_status,
            source='manual',
            updated_by=get_staff_user(),
        )
        db.session.add(p)
        db.session.commit()
        flash(f'Page "{title}" created.', 'success')
        return redirect(url_for('wiki.page', page_slug=slug))
    return render_template('wiki/edit.html', page=None)


@bp.route('/edit/<page_slug>', methods=['GET', 'POST'])
@require_staff
def edit_page(page_slug):
    c = g.campaign
    p = WikiPage.query.filter_by(campaign_id=c.id, slug=page_slug).first_or_404()
    if request.method == 'POST':
        p.title           = request.form.get('title', p.title).strip() or p.title
        p.summary         = request.form.get('summary', '').strip()
        p.category        = request.form.get('category', p.category).strip()
        p.body_markdown   = request.form.get('body_markdown', '')
        p.cover_image_url = request.form.get('cover_image_url', '').strip()
        new_status        = request.form.get('status', p.status).strip()
        if new_status in WIKI_STATUSES:
            p.status = new_status
        p.updated_by = get_staff_user()
        p.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash(f'Page "{p.title}" saved.', 'success')
        return redirect(url_for('wiki.page', page_slug=page_slug))
    return render_template('wiki/edit.html', page=p)


@bp.route('/set-status/<page_slug>', methods=['POST'])
@require_staff
def set_status(page_slug):
    c = g.campaign
    p = WikiPage.query.filter_by(campaign_id=c.id, slug=page_slug).first_or_404()
    new_status = request.form.get('status', '').strip()
    if new_status not in WIKI_STATUSES:
        flash('Invalid status.', 'danger')
    else:
        p.status     = new_status
        p.updated_by = get_staff_user()
        p.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash(f'"{p.title}" set to {WIKI_STATUS_LABELS[new_status]}.', 'success')
    return redirect(url_for('wiki.page', page_slug=page_slug))


@bp.route('/delete/<page_slug>', methods=['POST'])
@require_staff
def delete_page(page_slug):
    c = g.campaign
    p = WikiPage.query.filter_by(campaign_id=c.id, slug=page_slug).first_or_404()
    title = p.title
    db.session.delete(p)
    db.session.commit()
    flash(f'Page "{title}" deleted.', 'success')
    return redirect(url_for('wiki.index'))
