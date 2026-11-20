"""Public snapshot validation, permission boundaries, and optimistic revisions."""
import copy
import json
import os
import re
import unittest
from unittest.mock import patch
from app import create_app
from app.db import Campaign, db
from app.sector_state import geography


class SectorAtlasTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'DATABASE_URL': 'sqlite://', 'SECRET_KEY': 'sector-test'})
        self.env.start()
        self.app = create_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        self.state = copy.deepcopy(geography()['defaultState'])
        self.path = '/sav/atlas/sector/state'

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        self.env.stop()

    def token(self, staff=True):
        with self.client.session_transaction() as session:
            session['authenticated'] = staff
        html = self.client.get('/sav/atlas/sector/').get_data(as_text=True)
        config = json.loads(re.search(r'id="sector-config">(.*?)</script>', html, re.S).group(1))
        return config['csrfToken']

    def put(self, state, revision=0, token=None):
        return self.client.put(self.path, json=dict(revision=revision, state=state),
                               headers={'X-CSRFToken': token or self.token()})

    def test_public_atlas_read_only_and_player_safe(self):
        html = self.client.get('/sav/atlas/sector/').get_data(as_text=True)
        self.assertIn('"canEdit": false', html)
        data = self.client.get(self.path).get_json()
        self.assertEqual(data['revision'], 0)
        self.assertNotIn('Morrow', json.dumps(data))
        self.assertNotIn('secret', json.dumps(data).lower())
        token = self.token(staff=False)
        self.assertEqual(self.put(self.state, token=token).status_code, 403)

    def test_staff_save_persistence_conflict_and_csrf(self):
        self.assertEqual(self.client.put(self.path, json={}).status_code, 400)
        token = self.token()
        self.state['systems']['rin']['heat'] = 5
        first = self.put(self.state, token=token)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()['revision'], 1)
        self.assertEqual(self.client.get(self.path).get_json()['state']['systems']['rin']['heat'], 5)
        self.assertEqual(self.put(self.state, revision=0, token=token).status_code, 409)
        self.assertEqual(self.put(self.state, revision=1, token=token).get_json()['revision'], 2)

    def test_invalid_state_and_private_extra_fields_rejected(self):
        token = self.token()
        bad = copy.deepcopy(self.state)
        bad['gmNotes'] = 'Do not publish'
        self.assertEqual(self.put(bad, token=token).status_code, 400)
        for field, value in [('heat', 9), ('wanted', -1), ('heat', True)]:
            bad = copy.deepcopy(self.state)
            bad['systems']['rin'][field] = value
            self.assertEqual(self.put(bad, token=token).status_code, 400)
        bad = copy.deepcopy(self.state)
        bad['ship']['location'] = 'missing'
        self.assertEqual(self.put(bad, token=token).status_code, 400)
        self.assertEqual(self.client.get(self.path).get_json()['revision'], 0)

    def test_draft_campaign_not_exposed_by_map_or_api(self):
        campaign = Campaign.query.filter_by(slug='sav').one()
        campaign.status = 'draft'
        db.session.commit()
        self.assertEqual(self.client.get(self.path).status_code, 404)
        self.assertEqual(self.client.get('/sav/atlas/sector/').status_code, 404)
