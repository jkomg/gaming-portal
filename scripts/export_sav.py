#!/usr/bin/env python3
"""Export authorable content/sav Markdown into the startup import fixture."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / 'content/sav'
PAGES = [
    ('start-here', 'Start here', 'lore', 'active', 'A ready crew and a short teaching job for learning core Scum and Villainy.'),
    ('a-breathing-cargo', 'A Breathing Cargo', 'jobs', 'active', 'Move a living specimen through a local Rin customs checkpoint.'),
    ('quiet-orbit', 'The Quiet Orbit', 'characters', 'active', 'A completed Stardancer with starting systems, upgrades, CRED, and faction ties.'),
    ('pregens', 'Choose a pregen', 'characters', 'active', 'Six complete scoundrels for a ten-minute pickup.'),
    ('first-job-reference', 'Your first S&V job', 'rules', 'active', 'Core actions, Gambits, equipment, and the complete aftermath loop.'),
    ('people-and-factions', 'People and factions', 'factions', 'active', 'The known cast and starting relationships around the ship.'),
    ('atlas-notes', 'Atlas notes', 'locations', 'active', 'Original local route diagram; all starter sites are in Rin.'),
    ('art-and-credits', 'Sources and artwork', 'lore', 'active', 'Rule references, image licenses, portrait provenance, and map authorship.'),
    ('gm-a-breathing-cargo', 'GM: A Breathing Cargo', 'gm', 'draft', 'Private teaching-job preparation, clocks, stakes, and aftermath.'),
    ('gm-supporting-cast', 'GM supporting cast', 'gm', 'draft', 'Private SPC motives, knowledge, leverage, and reactions.'),
    ('gm-next-arc', 'GM: After the quiet orbit', 'gm', 'draft', 'Three optional jobs with competing faction offers and consequences.'),
]
PORTRAITS = dict(drift='mott', fuse='coil', silk='amancio', anchor='brace', echo='bell', mercy='mara')
for name, book in [('drift', 'Pilot'), ('fuse', 'Mechanic'), ('silk', 'Speaker'),
                   ('anchor', 'Muscle'), ('echo', 'Mystic'), ('mercy', 'Stitch')]:
    PAGES.append((f'pregen-{name}', f'{name.title()} the {book}', 'characters', 'active',
                  'Ready to play: actions, two starting abilities, gear, contacts, and trackers.'))


def export():
    categories = [('lore', 'Start Here', 'bi-book-fill'), ('characters', 'Crew and Characters', 'bi-people-fill'),
                  ('jobs', 'Jobs', 'bi-briefcase-fill'), ('rules', 'Rules', 'bi-journal-text'),
                  ('factions', 'People and Factions', 'bi-shield-fill'), ('locations', 'Locations', 'bi-geo-alt-fill'),
                  ('sessions', 'Sessions', 'bi-calendar-event'), ('gm', 'GM Preparation', 'bi-lock-fill')]
    payload = {'campaign': {
        'slug': 'sav', 'name': 'Scum and Villainy: Quiet Orbit', 'system': 'Scum and Villainy',
        'status': 'upcoming', 'cover_image_url': '/static/sav/carina.jpg',
        'description': 'A patched freighter takes a living cargo through Rin customs. A ready-to-play learning run of core Scum and Villainy, with a completed crew and a short teaching job.',
        'wiki_categories': [dict(slug=s, name=n, icon=i) for s, n, i in categories],
    }, 'pages': []}
    for slug, title, category, status, summary in PAGES:
        portrait = PORTRAITS.get(slug.removeprefix('pregen-')) if slug.startswith('pregen-') else None
        payload['pages'].append(dict(slug=slug, title=title, category=category, status=status,
                                     summary=summary, cover_image_url=f'/static/sav/{portrait or "carina"}.jpg',
                                     body_markdown=(CONTENT / 'campaign' / f'{slug}.md').read_text()))
    target = ROOT / 'scripts/fixtures/sav_campaign.json'
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    print(f'Exported {len(payload["pages"])} pages to {target}')


if __name__ == '__main__':
    export()
