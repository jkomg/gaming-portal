import os
import unittest
from unittest.mock import patch

from app import create_app
from app.db import Campaign, WikiPage, db
from app.dcbn_artwork import seed_dcbn_artwork


class DCArtworkTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'DATABASE_URL': 'sqlite://', 'SECRET_KEY': 'test'})
        self.environment.start()
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        self.context.pop()
        self.environment.stop()

    def campaign(self, slug='dcbn', categories=None):
        campaign = Campaign(slug=slug, name=slug)
        campaign.wiki_categories = [{'slug': c, 'name': c} for c in
                                    (categories or ['characters', 'coteries', 'locations', 'factions', 'lore', 'sessions'])]
        db.session.add(campaign)
        db.session.commit()
        return campaign

    def test_missing_campaign_does_not_create_one(self):
        self.assertEqual(seed_dcbn_artwork(), 0)
        self.assertEqual(Campaign.query.count(), 0)

    def test_rerun_preserves_authored_pages_covers_and_other_campaigns(self):
        campaign = self.campaign()
        campaign.cover_image_url = '/custom-home.jpg'
        authored = WikiPage(campaign_id=campaign.id, slug='custom-mage-slug', title='Mage',
                            body_markdown='Existing lore', category='lore', status='draft')
        covered = WikiPage(campaign_id=campaign.id, slug='technocracy', title='Technocracy',
                          body_markdown='Private lore', category='factions', status='draft',
                          cover_image_url='/custom-technocracy.jpg')
        other = self.campaign('other')
        other_page = WikiPage(campaign_id=other.id, slug='garou', title='Garou', body_markdown='Other lore')
        db.session.add_all([authored, covered, other_page])
        db.session.commit()
        self.assertEqual(seed_dcbn_artwork(), 12)
        self.assertEqual(seed_dcbn_artwork(), 0)
        self.assertEqual(WikiPage.query.filter_by(campaign_id=campaign.id).count(), 14)
        self.assertEqual(authored.body_markdown, 'Existing lore')
        self.assertEqual(authored.category, 'lore')
        self.assertEqual(authored.status, 'draft')
        self.assertEqual(authored.slug, 'custom-mage-slug')
        self.assertEqual(authored.cover_image_url, '/static/img/dcbn/mage.jpg')
        self.assertEqual(covered.cover_image_url, '/custom-technocracy.jpg')
        self.assertEqual(campaign.cover_image_url, '/custom-home.jpg')
        self.assertEqual(other_page.body_markdown, 'Other lore')
        self.assertFalse(other_page.cover_image_url)
        self.assertFalse(other.cover_image_url)

    def test_factions_remain_in_existing_category_with_empty_content(self):
        campaign = self.campaign(categories=['factions'])
        self.assertEqual(seed_dcbn_artwork(), 6)
        self.assertEqual(campaign.cover_image_url, '/static/img/dcbn/chronicle-home.jpg')
        pages = WikiPage.query.filter_by(campaign_id=campaign.id).all()
        self.assertEqual({p.slug for p in pages}, {'firstlight', 'technocracy', 'garou', 'wraith', 'mage', 'hunter'})
        self.assertTrue(all(p.category == 'factions' and p.status == 'upcoming' for p in pages))
        self.assertTrue(all(p.body_markdown == '' and p.summary == '' for p in pages))


if __name__ == '__main__':
    unittest.main()
