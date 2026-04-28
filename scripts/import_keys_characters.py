#!/usr/bin/env python3
"""Import Keys from the Golden Vault player characters into wiki.

Usage:
    export DATABASE_URL=$(gcloud secrets versions access latest --secret=DATABASE_URL --project=jkomg-gaming)
    export TURSO_AUTH_TOKEN=$(gcloud secrets versions access latest --secret=TURSO_AUTH_TOKEN --project=jkomg-gaming)
    python3 scripts/import_keys_characters.py
"""
from __future__ import annotations
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

_ssl_ctx = ssl._create_unverified_context()

_db_url = os.environ.get('DATABASE_URL', '')
_token  = os.environ.get('TURSO_AUTH_TOKEN', '')

if _db_url.startswith('libsql://'):
    _turso_url = 'https://' + _db_url[len('libsql://'):]
elif _db_url.startswith('https://'):
    _turso_url = _db_url
else:
    print('ERROR: DATABASE_URL must start with libsql:// or https://')
    sys.exit(1)

_endpoint = f'{_turso_url}/v2/pipeline'
_headers  = {'Authorization': f'Bearer {_token}', 'Content-Type': 'application/json'}


def _arg(v):
    if v is None:           return {'type': 'null',    'value': None}
    if isinstance(v, bool): return {'type': 'integer', 'value': str(int(v))}
    if isinstance(v, int):  return {'type': 'integer', 'value': str(v)}
    return                         {'type': 'text',    'value': str(v)}


def sql(query, params=None):
    stmt = {'sql': query}
    if params:
        stmt['args'] = [_arg(p) for p in params]
    body = json.dumps({'requests': [{'type': 'execute', 'stmt': stmt}, {'type': 'close'}]})
    req  = urllib.request.Request(_endpoint, data=body.encode(), headers=_headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Turso HTTP {exc.code}: {exc.read().decode()}') from exc
    result = data['results'][0]
    if result['type'] == 'error':
        raise RuntimeError(f'SQL error: {result["error"]["message"]}')
    return result['response']['result']


def fetchone(query, params=None):
    rows = sql(query, params).get('rows', [])
    if not rows:
        return None
    return tuple(c.get('value') for c in rows[0])


def slugify(text: str) -> str:
    s = re.sub(r'[^\w\s-]', '', text.lower())
    s = re.sub(r'[\s_]+', '-', s).strip('-')
    return s


def unique_slug(campaign_id: int, base: str) -> str:
    slug, i = base, 1
    while fetchone('SELECT id FROM wiki_pages WHERE campaign_id=? AND slug=?', [campaign_id, slug]):
        i += 1
        slug = f'{base}-{i}'
    return slug


def first_paragraph(text: str) -> str:
    for line in text.split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('!') and not line.startswith('>'):
            return line[:300]
    return ''


PAGES = [

    {
        'title': "Aurora 'Tatiana' Jones",
        'category': 'characters',
        'status': 'active',
        'body': """\
# Aurora 'Tatiana' Jones

**Class & Level:** Monk 6 (Way of the Drunken Master)
**Species:** Wood Elf
**Background:** Charlatan
**Alignment:** Chaotic Good
**Faith:** Ilmater
**Player:** kennjason

---

## Appearance

Female, age 24. 5'4", 143 lbs. Fair but sunkissed skin, emerald green eyes, long pale blonde hair.

Long pale blonde hair set high in a ponytail, weaved into a long fishtail braid. Multiple small gems are woven into her ponytail and through the braid. A pale lavender button-down shirt under a soft, well-fitted brown jacket that moves like a second skin. Dark pants tucked into well-worn knee-high leather boots, with a small dagger slightly poking out from the top edge of her left boot. She carries a long slender pole with some random ribbons tied along the top, and a slightly battered leather-bound notebook she whistles and writes her various "poems and stories of inspiring great loves" in as they travel about and meet new people.

She comes off as very bubbly and asks as many questions to as many people she can come across, but easily switches to quiet and focused when the time calls.

---

## Personality

**Traits:** I fall in and out of love easily, and I'm always bounding for the next adventure. I watch and study everyone and everything around me and have a knack for getting stuck in a good book. I have a joke for every occasion, especially occasions where humor is inappropriate.

**Ideal:** Fairness. I never target people who can't afford to lose a few coins. I always gather all the information before acting.

**Bond:** I owe everything to my mentor and family for guiding my new path. I will try my best to keep on my track.

**Flaw:** I can't resist a pretty face, good ale, or the chance of some serious coin.

---

## Backstory

Born to a poor human mother, Aurora never knew anything of her father besides being a charming elvish gentleman passing through. Growing up in a poorer district of Kleable, the capital of the Ish Empire, the world was her oyster. Free-spirited and full of mischief from a young age, she watched and listened to everything she could, soaking it up like a sponge.

Her mother saw the spark and endless potential of her daughter, and tried her best to guide her out of trouble. It didn't help that Aurora was most fascinated by some of the more vibrant personalities hanging around port. She learned a variety of scrupulous talents from them, eventually getting caught into her own whirlwind of mischief. It wasn't until she was 17 that her mother found out how deep her daughter had gotten caught up — when Aurora found herself on the wrong side of a con gone bad with the head of a local mercenary band. Smuggling her daughter out of port was a last fleeting hope of keeping her out of her binds.

It was a few weeks later, traveling through to the border of the Ilmese Empire, that the two came across a small group of priests to the Crying God Ilmater sitting around a campfire at dusk. It seemed her mother's prayers had been heard — they warmly offered food and safety. As Aurora slept, her mother told the small band everything: of Aurora's missing father, her past and present, and of the dreams she had hoped for her wayward daughter.

Come morning, the group offered to escort the ladies to their humble monastery. Along the way, the senior priest Brother Fanthal questioned Aurora on her ideals and watched her interactions with others. After a week of conversation and discovery, Aurora awoke one day to a note from her mother — and a new path forward.

---

## Stats

| | |
|-|-|
| **AC** | 16 |
| **HP** | 51 |
| **Speed** | 50 ft. (Walking), 30 ft. (Flying) |
| **Initiative** | +3 |
| **Hit Dice** | 6d8 |
| **Proficiency Bonus** | +3 |
| **Ki Points** | 6 / Short Rest |
| **Ki Save DC** | 14 |

**Ability Scores:** STR 9 (−1) · DEX 17 (+3) · CON 16 (+3) · INT 8 (−1) · WIS 16 (+3) · CHA 10 (+0)

**Saving Throws:** Advantage against being charmed; Immune to magical sleep.

**Top Skills:** Acrobatics +6 · Perception +6 · Sleight of Hand +6 · Stealth +6 · Insight +3 · Deception +3

**Senses:** Darkvision 60 ft. · Passive Perception 16

---

## Combat

| Attack | Bonus | Damage |
|--------|-------|--------|
| Unarmed Strike | +7 | 1d6+4 Bludgeoning |
| Flurry of Blows | +7 | 1d6+4 Bludgeoning |
| Quarterstaff | +6 | 1d6+3 Bludgeoning |
| Dart | +6 | 1d4+3 Piercing |
| Deflect Missiles Attack | +6 | 1d6+3 |

---

## Key Features

**Way of the Drunken Master** — Unpredictable, flowing combat style. Flurry of Blows also grants Disengage and +10 ft. speed until end of turn.

**Flurry of Blows** — Spend 1 ki after Attack action to make two unarmed strikes as a bonus action.

**Patient Defense** — Spend 1 ki to Dodge as a bonus action.

**Step of the Wind** — Spend 1 ki to Disengage or Dash as a bonus action; jump distance doubled.

**Deflect Missiles** — Reaction to reduce ranged weapon damage; if reduced to 0, can spend 1 ki to throw it back (range 20/60, +6, 1d6+3).

**Stunning Strike** — On hit, spend 1 ki to force CON save (DC 14) or target is stunned until end of next turn.

**Extra Attack** — Attack twice when taking the Attack action.

**Ki-Empowered Strikes** — Unarmed strikes count as magical.

**Focused Aim** — On a miss, spend 1–3 ki to add +2 per ki point to the attack roll.

**Slow Fall** — Reaction to reduce falling damage by 30.

**Wood Elf:** Fleet of Foot (speed 35 ft.), Mask of the Wild, Fey Ancestry, Trance, Elf Weapon Training.

---

## Equipment

**Attuned:** Eldritch Claw Tattoo · Winged Boots

**Notable:** Quarterstaff · Darts (×10) · Disguise Kit · Forgery Kit · Potion of Healing · Wraps of Dyamak (Dormant) · Fine Clothes

**Languages:** Common, Elvish

**Tools:** Brewer's Supplies, Disguise Kit, Flute, Forgery Kit
""",
    },

    {
        'title': 'Eduardo "Eddie" Le Petomane',
        'category': 'characters',
        'status': 'active',
        'body': """\
# Eduardo "Eddie" Le Petomane

**Class & Level:** Barbarian 3 / Rogue 3 (Wild Magic Barbarian / Mastermind Rogue)
**Species:** Human
**Background:** Soldier
**Alignment:** Lawful Neutral
**Player:** kennjason

---

## Stats

| | |
|-|-|
| **AC** | 17 |
| **HP** | 53 |
| **Speed** | 30 ft. |
| **Initiative** | +3 |
| **Hit Dice** | 3d12 + 3d8 |
| **Proficiency Bonus** | +3 |

**Ability Scores:** STR 16 (+3) · DEX 16 (+3) · CON 14 (+2) · INT 11 (+0) · WIS 10 (+0) · CHA 10 (+0)

**Saving Throws:** Advantage on DEX saves against effects you can see while not blinded, deafened, or incapacitated (Danger Sense).

**Top Skills:** Stealth +9 · Thieves' Tools +9 · Athletics +6 · Sleight of Hand +6 · Intimidation +3 · Perception +3

**Senses:** Passive Perception 13

---

## Combat

| Attack | Bonus | Damage |
|--------|-------|--------|
| Rapier | +6 | 1d8+3 Piercing |
| Dagger | +6 | 1d4+3 Piercing |
| Whip | +6 | 1d4+3 Slashing (Reach) |
| Blowgun | +6 | 4 Piercing |
| Unarmed Strike | +6 | 4 Bludgeoning |

**Sneak Attack:** +2d6 damage when hitting with advantage (or ally adjacent to target) with a finesse or ranged weapon.

---

## Key Features

**Rage (3/Long Rest)** — Bonus action to rage for 1 minute. Advantage on STR checks and saves (not attacks), +2 melee damage with STR weapons, resistance to bludgeoning/piercing/slashing. Can't cast or concentrate on spells while raging.

**Wild Magic Surge** — On entering rage, roll on the Wild Magic table. DC 13 save if a saving throw is required.

**Magic Awareness (3/Long Rest)** — Action to sense the location of any spell or magic item within 60 ft. that isn't behind total cover until end of next turn. Learn which school of magic it belongs to.

**Reckless Attack** — Advantage on STR melee attacks this turn; attack rolls against you have advantage until next turn.

**Unarmored Defense (Barbarian)** — AC = 10 + DEX + CON when not wearing armor.

**Sneak Attack** — Extra 2d6 damage once per turn with finesse/ranged weapon when you have advantage, or when an ally is adjacent to the target.

**Cunning Action** — Bonus action to Dash, Disengage, or Hide.

**Expertise** — Proficiency bonus doubled for two chosen skills.

**Mastermind — Master of Intrigue** — Proficiency with Disguise Kit, Forgery Kit, one gaming set. Can mimic speech patterns and accents after listening for 1 minute.

**Mastermind — Master of Tactics** — Use Help as a bonus action. Target of the Help can be within 30 ft. (not adjacent).

**Thieves' Cant** — Secret language hidden in normal conversation.

---

## Equipment

**Armor:** Shield (AC +2)

**Weapons:** Rapier · Dagger · Whip · Blowgun

**Notable:** Cursed Luck Stone · Poison, Basic (vial) · Drow Poison (Injury) · Dice Set · Lantern, Hooded

**Languages:** Common, Draconic, Elvish, Gnomish, Thieves' Cant

**Tools:** Dice Set, Disguise Kit, Forgery Kit, Playing Card Set, Thieves' Tools, Vehicles (Land)

---

## Backstory

_Eddie's backstory is known to the GM._
""",
    },

    {
        'title': 'Foban Vatsk',
        'category': 'characters',
        'status': 'active',
        'body': """\
# Foban Vatsk

**Class & Level:** Cleric 6 (Arcana Domain)
**Species:** High Elf
**Background:** Cloistered Scholar
**Player:** kennjason

---

## Stats

| | |
|-|-|
| **AC** | 17 |
| **HP** | 45 |
| **Speed** | 30 ft. |
| **Initiative** | +3 |
| **Hit Dice** | 6d8 |
| **Proficiency Bonus** | +3 |
| **Spellcasting Ability** | WIS |
| **Spell Save DC** | 15 |
| **Spell Attack Bonus** | +7 |
| **Channel Divinity** | 2 / Short Rest |

**Ability Scores:** STR 10 (+0) · DEX 16 (+3) · CON 14 (+2) · INT 12 (+1) · WIS 16 (+3) · CHA 10 (+0)

**Saving Throws:** Advantage against being charmed; Immune to magical sleep.

**Top Skills:** Insight +6 · Arcana +4 · History +4 · Investigation +4 · Nature +4 · Religion +4

**Senses:** Darkvision 60 ft. · Passive Perception 13 · Passive Insight 16

---

## Combat

| Attack | Bonus | Damage |
|--------|-------|--------|
| Shortsword | +6 | 1d6+3 Piercing |
| Dagger | +6 | 1d4+3 Piercing |
| Fire Bolt | +6 | 2d10 Fire |
| Guiding Bolt | +7 | 4d6 Radiant |

---

## Key Features

**Arcana Domain** — Additional spells always prepared: Magic Missile, Detect Magic, Magic Weapon, Arcanist's Magic Aura, Dispel Magic, Magic Circle.

**Arcane Initiate** — Proficiency in Arcana. Cantrips: Green-Flame Blade, Fire Bolt (INT is spellcasting ability for the cantrip).

**Harness Divine Power (2/Long Rest)** — Bonus action: expend a Channel Divinity use to regain a spell slot of up to 2nd level.

**Channel Divinity — Arcane Abjuration** — Action: one celestial/elemental/fey/fiend within 30 ft. must make WIS save (DC 14) or be turned/banished for 1 minute.

**Destroy Undead** — When undead fails Turn Undead save, instantly destroyed if CR 1/2 or lower.

**Spell Breaker** — When restoring HP to an ally with a 1st level+ spell, also end one spell on them of equal or lower level than the healing spell.

**Cantrip Versatility** — Can replace a cantrip on ASI.

**High Elf:** Darkvision, Fey Ancestry, Trance, Elf Weapon Training, bonus wizard cantrip.

---

## Spells

**Cantrips:** Guidance · Sacred Flame · Spare the Dying · Light · Create Bonfire · Green-Flame Blade · Fire Bolt

**1st Level (4 slots):** Cure Wounds · Guiding Bolt · Healing Word · Inflict Wounds · Bless · Bane · Command · Sanctuary · Shield of Faith · Detect Magic *(prep)* · Magic Missile *(prep)* · + full cleric list

**2nd Level (3 slots):** Spiritual Weapon · Prayer of Healing · Silence · Magic Weapon *(prep)* · Arcanist's / Nystul's Magic Aura *(prep)* · + full cleric list

**3rd Level (3 slots):** Spirit Guardians · Revivify · Remove Curse · Sending · Dispel Magic *(prep)* · Magic Circle *(prep)* · + full cleric list

---

## Equipment

**Attuned:** Amulet of the Devout +1

**Armor:** Studded Leather · Shield

**Weapons:** Shortsword · Dagger · Mace

**Notable:** Holy Symbol · Ink & Parchment

**Languages:** Common, Draconic, Dwarvish, Elvish, Goblin

**Tools:** Thieves' Tools

---

## Backstory

_Foban's backstory is known to the GM._
""",
    },

    {
        'title': 'Sister Kassira',
        'category': 'characters',
        'status': 'active',
        'body': """\
# Sister Kassira

**Class & Level:** Armorer Artificer / Cleric multiclass (Level 6)
**Species:** Dragonborn
**Player:** kennjason

---

## Stats

| | |
|-|-|
| **AC** | 16 |
| **HP** | 40 |
| **Speed** | 30 ft. |
| **Hit Dice** | 6d8 |
| **Proficiency Bonus** | +3 |

**Ability Scores:** STR 14 (+2) · DEX 10 (+0) · CON 12 (+1) · INT 16 (+3) · WIS 16 (+3) · CHA 10 (+0)

---

## Combat

| Attack | Bonus | Damage |
|--------|-------|--------|
| Thunder Gauntlets | +6 | 1d8+3 Thunder |
| Lightning Launcher | +6 | 1d8+3 Lightning |
| Guiding Bolt | +6 | 4d6 Radiant |
| Sacred Flame | DC 15 | 2d8 Radiant |
| Lightning Lure | DC 15 | 2d8 Lightning |
| Cure Wounds | — | Healing |
| Breath Weapon | — | (2 uses / rest) |

---

## Key Features

**Armorer (Artificer)** — Wears arcane armor integrated with Thunder Gauntlets (melee, target has disadvantage on attacks against anyone but her until her next turn) and Lightning Launcher (ranged).

**Infusions** — Magical item infusions (1 charge shown).

**Spellcasting** — Casts both Artificer spells (INT-based) and Cleric spells (WIS-based).

**Dragonborn — Breath Weapon** — 2 uses per rest.

---

## Backstory

_Sister Kassira's backstory is known to the GM._
""",
    },

]


def main():
    if not _token:
        print('ERROR: TURSO_AUTH_TOKEN not set')
        sys.exit(1)

    print('Connecting to Turso…')
    row = fetchone("SELECT id FROM campaigns WHERE slug='keys'")
    if not row:
        print('ERROR: keys campaign not found in DB')
        sys.exit(1)
    campaign_id = int(row[0])
    print(f'Keys campaign_id = {campaign_id}')
    print(f'Importing {len(PAGES)} character pages…\n')

    created = skipped = 0
    for page in PAGES:
        title     = page['title']
        category  = page['category']
        status    = page['status']
        body      = page['body'].strip()
        base_slug = slugify(title)
        summary   = first_paragraph(body)

        existing = fetchone(
            'SELECT id FROM wiki_pages WHERE campaign_id=? AND slug=?',
            [campaign_id, base_slug]
        )
        if existing:
            print(f'  SKIP (exists): {title}')
            skipped += 1
            continue

        slug = unique_slug(campaign_id, base_slug)
        sql(
            '''INSERT INTO wiki_pages
               (campaign_id, slug, title, summary, body_markdown,
                category, status, source, notion_page_id, updated_by)
               VALUES (?,?,?,?,?,?,?,'manual','','import')''',
            [campaign_id, slug, title, summary, body, category, status],
        )
        print(f'  CREATED [{category}/{status}]: {title}')
        created += 1

    print(f'\nDone. Created: {created}  |  Skipped: {skipped}')


if __name__ == '__main__':
    main()
