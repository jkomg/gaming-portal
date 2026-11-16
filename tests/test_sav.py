"""S&V publishing boundaries, importer safety, and starter record consistency."""
import hashlib
import html
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import event

from app import create_app
from app.db import Campaign, WikiPage, db
from app.sav_campaign import load_payload, seed

ROOT = Path(__file__).resolve().parents[1]


class SavCampaignTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'DATABASE_URL': 'sqlite://', 'SECRET_KEY': 'test'})
        self.environment.start()
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        self.client = self.app.test_client()
        self.payload = load_payload()
        self.campaign = Campaign.query.filter_by(slug='sav').one()

    def tearDown(self):
        db.session.remove()
        self.context.pop()
        self.environment.stop()

    def test_startup_separate_entry_and_idempotent_seed_preserves_edits(self):
        gotw = Campaign.query.filter_by(slug='gotw').one()
        gotw.name = 'Existing Wayline campaign'
        gotw.description = 'Keep this continuity'
        page = self.campaign.wiki_pages.filter_by(slug='start-here').one()
        page.body_markdown = 'Our actual crew history'
        page.cover_image_url = '/custom.jpg'
        page.status = 'archived'
        self.campaign.name = 'Our ship'
        db.session.commit()
        seed()
        self.assertEqual(self.campaign.wiki_pages.count(), 17)
        self.assertEqual(self.campaign.name, 'Our ship')
        self.assertEqual(page.body_markdown, 'Our actual crew history')
        self.assertEqual(page.status, 'archived')
        self.assertEqual(page.cover_image_url, '/custom.jpg')
        self.assertEqual(gotw.name, 'Existing Wayline campaign')
        self.assertEqual(gotw.description, 'Keep this continuity')
        self.assertEqual(Campaign.query.count(), 6)

    def test_routes_spoiler_boundary_and_staff_access(self):
        for path in ['/', '/sav', '/sav/wiki/', '/sav/atlas/']:
            response = self.client.get(path, follow_redirects=True)
            self.assertEqual(response.status_code, 200, path)
        for page in self.payload['pages']:
            expected = 404 if page['category'] == 'gm' else 200
            response = self.client.get('/sav/wiki/' + page['slug'])
            self.assertEqual(response.status_code, expected, page['slug'])
            if expected == 200:
                self.assertNotIn('Morrow', response.get_data(as_text=True))
        result = self.client.get('/sav/wiki/search?q=Morrow').get_data(as_text=True)
        self.assertNotIn('GM: A Breathing Cargo', result)
        self.assertNotIn('bioelectric organism recovered', result)
        with self.client.session_transaction() as session:
            session['authenticated'] = True
        for page in self.payload['pages']:
            self.assertEqual(self.client.get('/sav/wiki/' + page['slug']).status_code, 200)
        self.campaign.status = 'draft'
        db.session.commit()
        self.client.get('/auth/logout', follow_redirects=True)
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.get('/sav/atlas/').status_code, 404)

    def test_learning_run_refresh_removes_only_retired_seed_pages(self):
        retired = ['deep-cuts-compatibility', 'deep-cuts-playtest', 'threat-roll-prototype']
        self.campaign.description = (
            'A patched freighter takes a living cargo through Rin customs. '
            'A ready-to-play teaching job opens into faction choices and optional Deep Cuts experiments.'
        )
        self.campaign.wiki_categories = [{'slug': 'rules', 'name': 'Rules and Experiments'}]
        for slug in retired[:2]:
            db.session.add(WikiPage(campaign_id=self.campaign.id, slug=slug,
                                    title='Old experiment', source='sav-seed', status='active'))
        manual = WikiPage(campaign_id=self.campaign.id, slug=retired[2],
                          title='Staff notes', source='manual', status='draft')
        db.session.add(manual)
        db.session.commit()
        seed()
        self.assertEqual(self.campaign.wiki_pages.filter(WikiPage.slug.in_(retired)).count(), 3)
        seed(refresh=True)
        self.assertEqual(self.campaign.wiki_pages.filter(WikiPage.slug.in_(retired)).all(), [manual])
        self.assertEqual(self.campaign.description, self.payload['campaign']['description'])
        self.assertEqual(self.campaign.wiki_categories[0]['name'], 'Rules')
        for slug in retired[:2]:
            self.assertEqual(self.client.get('/sav/wiki/' + slug).status_code, 404)
        self.assertNotRegex(json.dumps(self.payload).lower(), r'deep.cuts|threat-roll-prototype')

    def test_refresh_collision_is_rejected_before_any_database_write(self):
        page = self.campaign.wiki_pages.filter_by(slug='a-breathing-cargo').one()
        page.source = 'manual'
        self.campaign.cover_image_url = ''
        self.campaign.wiki_categories = [{'slug': 'rules', 'name': 'Rules and Experiments'}]
        db.session.add(WikiPage(campaign_id=self.campaign.id, slug='deep-cuts-playtest',
                                title='Retired packet', source='sav-seed', status='active'))
        db.session.commit()
        writes = []

        def record_writes(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().split()[0].upper() in ('INSERT', 'UPDATE', 'DELETE'):
                writes.append(statement)

        event.listen(db.engine, 'before_cursor_execute', record_writes)
        try:
            with self.assertRaisesRegex(ValueError, 'Refusing to replace non-imported page: a-breathing-cargo'):
                seed(refresh=True)
        finally:
            event.remove(db.engine, 'before_cursor_execute', record_writes)
        self.assertEqual(writes, [])
        self.assertEqual(self.campaign.cover_image_url, '')
        self.assertEqual(self.campaign.wiki_categories, [{'slug': 'rules', 'name': 'Rules and Experiments'}])
        self.assertIsNotNone(self.campaign.wiki_pages.filter_by(slug='deep-cuts-playtest').first())

    def test_fixture_sources_links_images_and_player_safe_atlas(self):
        all_slugs = {p['slug'] for p in self.payload['pages']}
        public = {p['slug'] for p in self.payload['pages'] if p['status'] == 'active'}
        for page in self.payload['pages']:
            source = ROOT / 'content/sav/campaign' / (page['slug'] + '.md')
            self.assertEqual(source.read_text(), page['body_markdown'])
            for link in re.findall(r'\]\(/sav/wiki/([a-z-]+)\)', page['body_markdown']):
                self.assertIn(link, all_slugs)
                if page['status'] == 'active':
                    self.assertIn(link, public, (page['slug'], link))
            paths = [page['cover_image_url']]
            paths += re.findall(r'(?:src="|\]\()(/static/sav/[^" )]+)', page['body_markdown'])
            for path in paths:
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)
                response.close()
        for image in json.loads((ROOT / 'app/static/sav/manifest.json').read_text())['assets']:
            path = ROOT / 'app/static/sav' / image['file']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), image['sha256'])
            self.assertTrue(image['source'].startswith('https://'))
            self.assertTrue(image['license'])
        sites = json.loads((ROOT / 'app/static/sav/sites.json').read_text())
        self.assertEqual(len({s['id'] for s in sites}), 5)
        for site in sites:
            self.assertIn(site['wiki'], public)
            self.assertTrue(0 < site['x'] < 1060 and 0 < site['y'] < 560)
        atlas = self.client.get('/sav/atlas/').get_data(as_text=True)
        self.assertNotIn('Morrow', atlas)
        for site in sites:
            self.assertIn(f'id="detail-{site["id"]}"', atlas)
            self.assertIn(site['access'], html.unescape(atlas))
        self.assertIn('J. DePasquale (STScI)', atlas)
        for path in ['/', '/sav', '/sav/wiki/start-here']:
            response = self.client.get(path, follow_redirects=True)
            self.assertIn('J. DePasquale (STScI)', response.get_data(as_text=True), path)

    def test_pregen_starting_dots_and_derived_ratings(self):
        people = json.loads((ROOT / 'content/sav/pregens.json').read_text())
        self.assertEqual(len(people), 6)
        groups = {'Insight': ['Doctor', 'Hack', 'Rig', 'Study'],
                  'Prowess': ['Helm', 'Scramble', 'Scrap', 'Skulk'],
                  'Resolve': ['Attune', 'Command', 'Consort', 'Sway']}
        canonical_base = {'Pilot': {'Helm': 2, 'Rig': 1}, 'Mechanic': {'Rig': 2, 'Study': 1},
                          'Speaker': {'Consort': 2, 'Command': 1}, 'Muscle': {'Scrap': 2, 'Command': 1},
                          'Mystic': {'Attune': 2, 'Scramble': 1}, 'Stitch': {'Doctor': 2, 'Study': 1}}
        for person in people:
            self.assertEqual(person['base'], canonical_base[person['book']])
            self.assertEqual(sum(person['actions'].values()), 7)
            self.assertLessEqual(max(person['actions'].values()), 2)
            for action, rating in person['base'].items():
                self.assertGreaterEqual(person['actions'][action], rating)
            ratings = {g: sum(person['actions'].get(a, 0) > 0 for a in actions)
                       for g, actions in groups.items()}
            self.assertEqual(person['resistance'], ratings)
            self.assertEqual(person['vice_dice'], min(ratings.values()))
            self.assertTrue(person['starting'])
            self.assertTrue(person['special'])

    def test_cli_preview_is_offline_and_refresh_collision_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'campaign.sqlite'
            env = dict(os.environ, DATABASE_URL=f'sqlite:///{path}')
            preview = subprocess.run([sys.executable, 'scripts/import_sav.py'], cwd=ROOT,
                                     env=env, capture_output=True, text=True)
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertFalse(path.exists())
            with patch.dict(os.environ, env):
                app = create_app(seed_campaigns=False)
            with app.app_context():
                campaign = Campaign(slug='sav', name='Our authored ship', status='hiatus')
                campaign.wiki_categories = [{'slug': 'lore', 'name': 'Our category', 'icon': 'custom'}]
                db.session.add(campaign)
                db.session.flush()
                db.session.add_all([
                    WikiPage(campaign_id=campaign.id, slug='start-here', title='Our opening',
                             source='sav-seed', body_markdown='Keep this edit'),
                    WikiPage(campaign_id=campaign.id, slug='a-breathing-cargo', title='Manual page',
                             source='manual', status='draft', body_markdown='Keep this too'),
                ])
                db.session.commit()
                db.session.remove()
                db.engine.dispose()
            with sqlite3.connect(path) as connection:
                before = tuple(connection.iterdump())
            result = subprocess.run([sys.executable, 'scripts/import_sav.py', '--apply', '--refresh'],
                                    cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Refusing to replace non-imported page: a-breathing-cargo', result.stderr)
            with sqlite3.connect(path) as connection:
                self.assertEqual(tuple(connection.iterdump()), before)
