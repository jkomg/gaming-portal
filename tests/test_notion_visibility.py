import unittest
from datetime import datetime
from unittest.mock import patch

from flask import Flask

from app.db import Campaign, WikiPage, db
from app.blueprints.admin import _notion_page_status, _upsert_notion_page
from app.blueprints.wiki import bp


class NotionVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY='test', TESTING=True,
                               SQLALCHEMY_DATABASE_URI='sqlite://')
        db.init_app(self.app)
        self.app.register_blueprint(bp, url_prefix='/<campaign_slug>/wiki')
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.campaign = Campaign(slug='dcbn', name='DC')
        db.session.add(self.campaign)
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        self.context.pop()

    def page(self, visibility=None, **extra):
        props = {'Name': {'type': 'title', 'title': [{'plain_text': 'Secret hive'}]}}
        if visibility is not None:
            props['Visibility'] = {'type': 'select', 'select': {'name': visibility}}
        return dict(id='notion-id', properties=props,
                    last_edited_time='2026-10-01T00:00:00Z', **extra)

    def existing(self, status='active', newer=False):
        row = WikiPage(campaign_id=self.campaign.id, notion_page_id='notion-id',
                       slug='secret-hive', title='Secret hive', category='factions',
                       status=status, body_markdown='Locally edited secret',
                       updated_at=datetime(2026, 10, 2 if newer else 1))
        db.session.add(row)
        db.session.commit()
        return row

    def sync(self, page):
        with patch('app.blueprints.admin._blocks_to_markdown', return_value='Notion secret'):
            return _upsert_notion_page(None, page, self.campaign.id, 'factions', 'test')

    def test_visibility_requires_explicit_public_choice(self):
        for choice, expected in [('Hidden', 'draft'), ('ST Only', 'draft'),
                                 ('', 'draft'), ('Players', 'active'), ('Public', 'active')]:
            with self.subTest(choice=choice):
                self.assertEqual(_notion_page_status(self.page(choice)), expected)
        page = self.page()
        self.assertEqual(_notion_page_status(page, require_visibility=True), 'draft')
        self.assertEqual(_notion_page_status(page), 'active')
        page['properties']['Visibility'] = {'type': 'rich_text', 'rich_text': []}
        self.assertEqual(_notion_page_status(page), 'draft')
        page['properties']['Visible'] = {'type': 'checkbox', 'checkbox': True}
        self.assertEqual(_notion_page_status(page), 'draft')

    def test_legacy_checkbox_and_archive_controls(self):
        page = self.page()
        for checked, expected in [(False, 'draft'), (True, 'active'), ('true', 'draft')]:
            page['properties']['Visible'] = {'type': 'checkbox', 'checkbox': checked}
            self.assertEqual(_notion_page_status(page), expected)
        for flag in ('archived', 'in_trash'):
            self.assertEqual(_notion_page_status(self.page('Players', **{flag: True})), 'archived')

    def test_dc_import_is_hidden_until_explicitly_released(self):
        self.sync(self.page())
        row = WikiPage.query.one()
        self.assertEqual((row.status, row.body_markdown), ('draft', 'Notion secret'))
        self.sync(self.page('Players'))
        self.assertEqual(row.status, 'active')

    def test_hide_newer_wiki_without_overwriting_content_or_timestamp(self):
        row = self.existing(newer=True)
        stamp = row.updated_at
        self.assertEqual(self.sync(self.page('Hidden')), row.slug)
        self.assertEqual(row.status, 'draft')
        self.assertEqual(row.body_markdown, 'Locally edited secret')
        self.assertEqual(row.updated_at, stamp)
        self.sync(self.page('Players'))
        self.assertEqual(row.status, 'draft')

    def test_untitled_page_still_withdraws_publication(self):
        row = self.existing()
        page = self.page('Hidden')
        page['properties']['Name']['title'] = []
        self.sync(page)
        self.assertEqual(row.status, 'draft')

    def test_failed_content_fetch_still_withdraws_publication(self):
        row = self.existing()
        with patch('app.blueprints.admin._blocks_to_markdown', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):
                _upsert_notion_page(None, self.page('Hidden'), self.campaign.id, 'factions', 'test')
        db.session.expire_all()
        self.assertEqual(row.status, 'draft')

    def test_public_routes_exclude_hidden_content_but_staff_can_read(self):
        self.existing(status='draft')
        public = WikiPage(campaign_id=self.campaign.id, slug='public', title='Public hive',
                          category='factions', status='active', body_markdown='Public information')
        db.session.add(public)
        db.session.commit()
        with patch('app.blueprints.wiki.render_template', return_value='rendered') as render:
            self.assertEqual(self.client.get('/dcbn/wiki/secret-hive').status_code, 404)
            self.client.get('/dcbn/wiki/category/factions')
            self.assertEqual([p.slug for p in render.call_args.kwargs['pages']], ['public'])
            response = self.client.get('/dcbn/wiki/search?q=hive',
                                       headers={'X-Requested-With': 'XMLHttpRequest'})
            self.assertEqual([r['title'] for r in response.json['results']], ['Public hive'])
            with self.client.session_transaction() as session:
                session['authenticated'] = True
            self.assertEqual(self.client.get('/dcbn/wiki/secret-hive').status_code, 200)


if __name__ == '__main__':
    unittest.main()
