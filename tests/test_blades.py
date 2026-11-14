import hashlib
import json
import os
import re
import unittest
from unittest.mock import patch

from app import create_app
from app.db import Campaign, WikiPage, db
from scripts.import_blades import ROOT, load_payload, seed


class BladesCampaignTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'DATABASE_URL': 'sqlite://', 'SECRET_KEY': 'test'})
        self.environment.start()
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        self.payload = load_payload()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        self.context.pop()
        self.environment.stop()

    def test_startup_seeds_campaign_pages_and_covers(self):
        campaign = Campaign.query.filter_by(slug='blades').one()
        self.assertEqual(campaign.wiki_pages.count(), len(self.payload['pages']))
        self.assertTrue(campaign.cover_image_url)
        for page in campaign.wiki_pages:
            self.assertTrue(page.cover_image_url, page.slug)
            if page.category == 'gm':
                self.assertEqual(page.status, 'draft')

    def test_cover_backfill_preserves_custom_art_and_authored_content(self):
        campaign = Campaign.query.filter_by(slug='blades').one()
        first = campaign.wiki_pages.filter_by(slug='start-here').one()
        first.body_markdown = 'Authored edit'
        first.status = 'archived'
        first.cover_image_url = ''
        second = campaign.wiki_pages.filter_by(slug='the-borrowed-spark').one()
        second.cover_image_url = '/custom-cover.jpg'
        campaign.cover_image_url = '/custom-campaign.jpg'
        db.session.commit()
        seed()
        self.assertTrue(first.cover_image_url)
        self.assertEqual(first.body_markdown, 'Authored edit')
        self.assertEqual(first.status, 'archived')
        self.assertEqual(second.cover_image_url, '/custom-cover.jpg')
        self.assertEqual(campaign.cover_image_url, '/custom-campaign.jpg')

    def test_repeat_import_preserves_campaign_and_authored_edits(self):
        campaign = Campaign.query.filter_by(slug='blades').one()
        campaign.name = 'Our crew name'
        page = WikiPage.query.filter_by(campaign_id=campaign.id, slug='start-here').one()
        page.body_markdown = 'Our own opening'
        db.session.commit()
        seed(self.payload)
        self.assertEqual(campaign.name, 'Our crew name')
        self.assertEqual(page.body_markdown, 'Our own opening')
        self.assertEqual(campaign.wiki_pages.count(), len(self.payload["pages"]))
        self.assertEqual(Campaign.query.count(), 5)

    def test_refresh_adds_new_category_without_replacing_custom_categories(self):
        campaign = Campaign.query.filter_by(slug='blades').one()
        campaign.wiki_categories = [{'slug': 'lore', 'name': 'Our Lore', 'icon': 'custom'}]
        db.session.commit()
        seed(self.payload, refresh=True)
        categories = {c['slug']: c for c in campaign.wiki_categories}
        self.assertIn('characters', categories)
        self.assertEqual(categories['lore']['name'], 'Our Lore')
        self.assertEqual(categories['lore']['icon'], 'custom')

    def test_refresh_rejects_collision_and_rolls_back(self):
        campaign = Campaign.query.filter_by(slug='blades').one()
        first = campaign.wiki_pages.filter_by(slug='start-here').one()
        first.body_markdown = 'Preserve after rollback'
        collision = campaign.wiki_pages.filter_by(slug='crows-foot').one()
        collision.source = 'manual'
        db.session.commit()
        with self.assertRaises(ValueError):
            seed(self.payload, refresh=True)
        self.assertEqual(first.body_markdown, 'Preserve after rollback')
        self.assertEqual(collision.source, 'manual')

    def test_public_routes_and_gm_visibility(self):
        for path in ['/', '/blades', '/blades/wiki/', '/blades/wiki/start-here', '/blades/atlas/']:
            self.assertEqual(self.client.get(path, follow_redirects=True).status_code, 200, path)
        for slug in [p['slug'] for p in self.payload['pages'] if p['category'] == 'gm']:
            self.assertEqual(self.client.get('/blades/wiki/' + slug).status_code, 404)
        result = self.client.get('/blades/wiki/search?q=Proprietor').get_data(as_text=True)
        self.assertNotIn('GM: After the first spark', result)
        with self.client.session_transaction() as session:
            session['authenticated'] = True
        self.assertEqual(self.client.get('/blades/wiki/gm-the-borrowed-spark').status_code, 200)
        self.assertEqual(self.client.get('/blades/wiki/gm-deeper-cuts').status_code, 200)

    def test_draft_campaign_hides_atlas(self):
        campaign = Campaign.query.filter_by(slug='blades').one()
        campaign.status = 'draft'
        db.session.commit()
        self.assertEqual(self.client.get('/blades/atlas/').status_code, 404)

    def test_public_links_and_static_assets_resolve(self):
        public = {p['slug'] for p in self.payload['pages'] if p['status'] == 'active'}
        for page in self.payload['pages']:
            for target in re.findall(r'\]\(/blades/wiki/([a-z-]+)\)', page['body_markdown']):
                if page['status'] == 'active':
                    self.assertIn(target, public)
                self.assertIn(target, {p['slug'] for p in self.payload['pages']})
                expected = 200 if target in public else 404
                self.assertEqual(self.client.get('/blades/wiki/' + target).status_code, expected, target)
        manifest = json.loads((ROOT / 'app/static/blades/art/manifest.json').read_text())
        for image in manifest['assets']:
            path = ROOT / 'app/static/blades/art' / image['file']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), image['sha256'])
            self.assertTrue(image['source'].startswith('https://'))
            self.assertTrue(image['license'])
        for page in self.payload['pages']:
            paths = [page['cover_image_url']]
            paths += re.findall(r'(?:src="|\]\()(/static/blades/[^" )]+)', page['body_markdown'])
            for path in paths:
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)
                response.close()
        sites = json.loads((ROOT / 'app/static/blades/sites.json').read_text())
        self.assertEqual(len(sites), 7)
        for site in sites:
            self.assertIn(site['wiki'], public)
            self.assertTrue(0 <= site['x'] <= 1 and 0 <= site['y'] <= 1)
        for path in ['blades/crows-foot.jpg', 'blades/sites.json', 'blades/atlas.js',
                     'blades/atlas.css', 'vendor/leaflet/leaflet.js', 'vendor/leaflet/leaflet.css']:
            response = self.client.get('/static/' + path)
            self.assertEqual(response.status_code, 200)
            response.close()
