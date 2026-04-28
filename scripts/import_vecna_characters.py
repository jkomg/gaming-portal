#!/usr/bin/env python3
"""Import Vecna: Eve of Ruin player characters into wiki.

Usage:
    export DATABASE_URL=$(gcloud secrets versions access latest --secret=DATABASE_URL --project=jkomg-gaming)
    export TURSO_AUTH_TOKEN=$(gcloud secrets versions access latest --secret=TURSO_AUTH_TOKEN --project=jkomg-gaming)
    python3 scripts/import_vecna_characters.py
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
        'title': 'Duskin Foxglove',
        'category': 'characters',
        'status': 'active',
        'body': """\
# Duskin Foxglove

**Class & Level:** Rogue 15 (Phantom)
**Species:** Half-Elf
**Background:** Investigator
**Alignment:** Chaotic Good
**Player:** kennjason

---

## Appearance

Male, age 50. Medium, 5'9", 170 lbs. Deathly pallor skin, sickly yellow eyes, pale blond hair.

A gaunt half-elf with unkempt hair, pale skin, and sunken yellow eyes. The macabre rogue typically dresses himself in simple tunics when he's not wearing a set of studded leather armor, and regardless of the occasion he's almost always wearing his grey cloak of elvenkind.

---

## Personality

**Traits:** It doesn't matter if the whole world's against me. I'll always do what I think is right. I have morbid interests and a macabre aesthetic.

**Ideal:** Obsession. I've lived this way for so long that I can't imagine another way.

**Bond:** Spirits are drawn to me. I do all I can to help them find peace.

**Flaw:** I know the ends always justify the means and am quick to make sacrifices to attain my goals.

---

## Backstory

Unbeknownst to the man himself, Duskin was born as a result of a brief fling between a human Doomguide that once served as a warden of the Neverdeath Graveyard, and a Shadar-kai gloomweaver that had traveled to the city to assist in cleansing the undead unleashed during the Ruining. His father perished during the fighting, while his mother left her child behind in Neverwinter soon after giving birth, before returning to the Shadowfell.

Due to his heritage, as well as being born during a time of great strife, the boy who eventually took the name Duskin Foxglove had an innate connection with spirits and death that most did not, allowing him to converse with the dearly departed with relative ease. The young lad spent his troubled youth in and out of the homes of would-be parents and the temples of several gods and goddesses, where his fearful accounts of the dead who visited him often led to him being seen as delusional, or worse, as some kind of oracle or medium. Eventually he would give up almost entirely on finding a permanent home, instead wandering the streets as a young urchin that picked pockets from the wealthy and did his best to fulfill the desires of the ghosts that haunted him, hoping to put them to rest.

As years passed, the lingering wraiths began petitioning him to complete more complex tasks — bringing thieves and murderers to justice while relying on the testimonies of the dead to find evidence that eluded others.

**Allies:** Various citizens and spirits of Helm's Hold and Neverwinter that Dusk has assisted throughout the years.

**Soul Trinkets:** 1 Havok the dead god · 1 quoei · 1 red wizard

**Djinni:** Husam al-Balil ben Nafhat al-Yugayyim

---

## Stats

| | |
|-|-|
| **AC** | 17 |
| **HP** | 108 |
| **Speed** | 30 ft. |
| **Initiative** | +6 |
| **Hit Dice** | 15d8 |
| **Proficiency Bonus** | +5 |
| **Passive Perception** | 27 |
| **Passive Insight** | 17 |
| **Passive Investigation** | 29 |

**Ability Scores:** STR 10 (+0) · DEX 20 (+5) · CON 14 (+2) · INT 16 (+3) · WIS 12 (+1) · CHA 8 (−1)

**Immunities:** Magical sleep; advantage against being charmed; magic can't put him to sleep.

**Senses:** Darkvision 120 ft.

**Top Skills:** Stealth +16 · Thieves' Tools +16 · Perception +12 · Investigation +14 · Acrobatics +11 · Sleight of Hand +11 · History +9 · Arcana +9 · Religion +9

---

## Combat

| Attack | Hit | Damage |
|--------|-----|--------|
| Crossbow, Light +2 w/Sharpshooter | +7 | 1d8+17 Piercing |
| Crossbow, Light +2 | +12 | 1d8+7 Piercing |
| Dagger | +10 | 1d4+5 Piercing |
| Raven's Feather | +13 | 1d6+8 Piercing +1d6 Necrotic (Vex) |
| Unarmed Strike | +5 | 1 Bludgeoning |

**Sneak Attack:** 8d6 extra damage once per turn with advantage or an ally adjacent to the target.

---

## Key Features

**Phantom (Roguish Archetype)** — A connection to death itself.

**Whispers of the Dead** — On short or long rest, choose a skill or tool proficiency from a ghostly presence.

**Wails from the Grave** — After dealing Sneak Attack damage, deal 4d6 necrotic to a second creature within 30 ft. of the first (uses = proficiency bonus per long rest).

**Tokens of the Departed** — When a creature dies within 30 ft., create a soul trinket as a reaction. Up to 5 trinkets at a time. Use trinkets to: gain advantage on death saves/CON saves (while on person), deal Sneak Attack + destroy a trinket to use Wails from the Grave for free, or destroy a trinket to question the spirit (1 action).

**Ghost Walk (1/Long Rest)** — Bonus action: assume spectral form. Flying speed 10 ft., hover, pass through creatures and objects (1d10 force damage if you end turn inside one), attack rolls have disadvantage against you. Lasts 10 minutes.

**Reliable Talent** — Treat any d20 roll of 9 or lower as a 10 on ability checks that add proficiency.

**Uncanny Dodge** — Reaction: halve damage from one attack.

**Evasion** — DEX save for half damage: take none on success, half on failure.

**Steady Aim** — Bonus action: advantage on next attack this turn (haven't moved this turn; speed becomes 0).

**Cunning Action** — Bonus action to Dash, Disengage, or Hide.

**Expertise** — Proficiency doubled for Investigation, Perception, Stealth, Thieves' Tools, Sleight of Hand.

**Blindsense** — Aware of any hidden or invisible creature within 10 ft. (if able to hear).

**Slippery Mind** — Proficiency in WIS saving throws.

**Feats:** Observant (+5 passive Perception/Investigation, lip reading) · Sharpshooter (no disadvantage at long range, ignore half/3/4 cover; −5/+10 option) · Elven Accuracy (reroll one die when advantage on DEX/INT/WIS/CHA attacks)

---

## Spells

**5th Level (item):** Commune *(from First Rod Piece)*

---

## Equipment

**Attuned:** Cloak of Elvenkind · Stone of Good Luck (Luckstone) · Raven's Feather

**Armor:** Studded Leather · Light Armor

**Weapons:** Crossbow, Light +2 · Crossbow, Light +2 w/Sharpshooter · Daggers ×2

**Notable:** Goggles of Night · Potion of Healing (Greater) · Shortsword of Warning · First Rod Piece · Thieves' Tools · Magnifying Glass · Holy Water (flask)

**Languages:** Abyssal, Common, Elvish, Thieves' Cant

**Tools:** Disguise Kit, Forgery Kit, Thieves' Tools
""",
    },

    {
        'title': 'Manzat',
        'category': 'characters',
        'status': 'active',
        'body': """\
# Manzat

**Class & Level:** Warlock 15 (The Celestial)
**Species:** Air Genasi
**Background:** Custom
**Player:** kennjason

---

## Stats

| | |
|-|-|
| **AC** | 18 |
| **HP** | 123 |
| **Speed** | 35 ft. |
| **Initiative** | +8 |
| **Hit Dice** | 15d8 |
| **Proficiency Bonus** | +5 |
| **Spellcasting Ability** | CHA |
| **Spell Save DC** | 18 |
| **Spell Attack Bonus** | +12 |
| **Passive Perception** | 10 |

**Ability Scores:** STR 16 (+3) · DEX 16 (+3) · CON 16 (+3) · INT 10 (+0) · WIS 10 (+0) · CHA 20 (+5)

**Resistances:** Lightning, Radiant

**Senses:** Darkvision 60 ft.

**Saving Throw Bonus:** +2 on saves; advantage on CON saves to maintain concentration.

**Top Skills:** Persuasion +10 · Religion +5 · Arcana +5 · Intimidation +5

---

## Combat

| Attack | Hit | Damage |
|--------|-----|--------|
| Eldritch Blast | +12 | 1d10+5 Force (×3 beams) |
| Shocking Grasp | +14 | 3d8 Lightning |
| Primal Savagery | +12 | 3d10 Acid |
| Produce Flame | +12 | 3d8 Fire |
| Staff of Power | +10 | 1d6+5 Bludgeoning +1d6 Force |
| Dagger | +8 | 1d4+3 Piercing |

---

## Key Features

**Otherworldly Patron: The Celestial** — Powers drawn from the Upper Planes.

**Pact of the Tome** — Grimoire granting additional cantrips and ritual casting.

**Healing Light (16d6 / Long Rest)** — Bonus action: heal one creature within 60 ft. by spending dice from the pool (max 5d6 at once).

**Expanded Spell List** — Celestial bonus spells always available.

**Bonus Cantrips:** Light · Sacred Flame *(count as warlock cantrips but don't count against cantrips known)*

**Radiant Soul** — Resistance to radiant damage. Add +5 to one radiant or fire damage roll per cast.

**Celestial Resilience** — Gain +20 temp HP on short or long rest. Also grant up to 5 creatures +12 temp HP each on rest.

**Searing Vengeance (1/Long Rest)** — At the start of your turn while making a death saving throw, spring back to 1 HP and deal 2d8+5 radiant damage to nearby creatures; they're blinded until end of current turn.

**Mystic Arcanum:** Investiture of Flame *(6th)* · Crown of Stars *(7th)* · Power Word Stun *(8th)*

**Eldritch Invocations:** Agonizing Blast (+5 to Eldritch Blast damage) · Armor of Shadows (Mage Armor at will) · Aspect of the Moon (no sleep needed) · Eldritch Mind (advantage on CON concentration saves) · Gift of the Protectors *(see below)* · Tomb of Levistus (1/SR reaction: encase in ice for 100 temp HP, then vulnerable to fire, speed 0, incapacitated until ice melts) · Witch Sight (see true form of shapechangers/illusions within 30 ft.)

**Gift of the Protectors** — Any creature whose name is written in the Book of the Pact drops to 1 HP instead of 0 (once per long rest per creature). Names in the book: Tari · Ula · Letum · Duskin · Wanker.

**Feats:** Alert (+5 to initiative, can't be surprised, attackers don't gain advantage from being unseen)

**Air Genasi Traits:** Unending Breath · Lightning Resistance · Mingle with the Wind (Shocking Grasp at will; Feather Fall 1/LR; Levitate 1/LR at 5th level) · Darkvision 60 ft.

---

## Spells

**Cantrips:** Eldritch Blast · Thunderclap · Mage Hand · Poison Spray · Shocking Grasp · Light · Sacred Flame · Word of Radiance · Primal Savagery · Produce Flame

**Pact Slots (5th level, ×3):**
- *1st:* Guiding Bolt · Cure Wounds · Magic Missile *(Staff)* · Feather Fall · Mage Armor *(Invocation)*
- *2nd:* Shatter · Levitate
- *3rd:* Gaseous Form
- *4th:* Guardian of Faith · Sickening Radiance · Raulothim's Psychic Lance
- *5th:* Flame Strike · Greater Restoration · Wall of Light · Synaptic Static · Far Step · Cone of Cold *(Staff)* · Fireball *(Staff)* · Hold Monster *(Staff)* · Lightning Bolt *(Staff)* · Wall of Force *(Staff)*
- *6th (Staff):* Globe of Invulnerability
- *6th (Mystic Arcanum):* Investiture of Flame
- *7th (Mystic Arcanum):* Crown of Stars
- *8th (Mystic Arcanum):* Power Word Stun

---

## Equipment

**Attuned:** Periapt of Wound Closure · Staff of Power · Tiara of Jarvis (Dormant)

**Weapons:** Staff of Power · Dagger · Rod of the Pact Keeper +2

**Notable:** Third Rod Piece · Spell Scroll (Level 5) · Spell Scroll (Level 6) · Holy Water (flask ×8) · Potion of Healing (Greater ×5)

**Languages:** Celestial, Common, Primordial

**Tools:** Glassblower's Tools
""",
    },

    {
        'title': 'Tari Reth',
        'category': 'characters',
        'status': 'active',
        'body': """\
# Tari Reth

**Class & Level:** Fighter 15 (Echo Knight)
**Species:** Kalashtar
**Background:** Outlander
**Alignment:** Lawful Neutral
**Faith:** Quori Reth
**Player:** kennjason

---

## Backstory

To escape the Dreaming Dark in her home area of Dor Maleer, and to have a chance to survive against the Inspired agents hunting her family lineage, Tari's full family pooled their resources and sought a high wizard to send their young eight-year-old daughter through the planes to another land that might give her a fighting chance to live.

She materialized in the realms of Faerûn on the marsh outskirts of Everlund, and with the warning of her family never to tell of what she is, made her way to the nearest settlement. She was drawn to the keep of vigilance where she was taken in as an orphan — more reserved than the others her age, and plagued by the memories and dreams of her family and quori, she was thought to be afflicted by either demons and nightmares or mental illness. She was brought to Silverymoon to be examined by the House of Invincible.

It was here she first met her mentor, a member of the Vigilant Eye, who recognized that there was something different — other worldly — about the odd girl. Her reserved nature but focused eye led her to begin training with other young ones of the order. As much as her skills excelled during training, her ability of divine intervention never manifested, and her odd behaviors led her to work better alone than in a larger order as she got older.

When she was in her late teens, without any divine power still, it was decided to transition the young fighter to the Order of Everwatch Knights. Here she was given more freedom to flourish on her own and left alone for her eccentric but harmless nature of speaking with herself. By her 20s she began to take on small assignments of her own within the eastern borders, helping escort various travel parties between the citadels for trade and around the Evermoors. Soon Tari had come to be known as the whispering guardian — the unusual knight who always seemed to know what was around the corner.

---

## Stats

| | |
|-|-|
| **AC** | 21 |
| **HP** | 166 |
| **Speed** | 30 ft. |
| **Initiative** | +0 |
| **Hit Dice** | 15d10 |
| **Proficiency Bonus** | +5 |
| **Passive Perception** | 17 |
| **Passive Insight** | 12 |

**Ability Scores:** STR 29 (+9) · DEX 10 (+0) · CON 18 (+4) · INT 8 (−1) · WIS 14 (+2) · CHA 10 (+0)

**Resistances:** Psychic · Bludgeoning, Piercing, and Slashing from Nonmagical Attacks

**Senses:** Darkvision 60 ft.

**Saving Throws:** STR (+14), CON (+9) proficient; advantage on WIS saves.

**Top Skills:** Athletics +14 · Intimidation +5 · Survival +7

---

## Combat

| Attack | Hit | Damage |
|--------|-----|--------|
| Sun Blade | +16 | 1d8+13 Radiant +1d8 Radiant (Finesse, Versatile, Sap) |
| Handaxe | +14 | 1d6+11 Slashing (Light, Thrown, Vex, Range 20/60) |
| Weapon of Certain Death, Morningstar | +14 | 1d8+11 Piercing (Sap) |
| Unarmed Strike | +14 | 10 Bludgeoning |

**Three attacks per Attack action** (Extra Attack ×2).

---

## Key Features

**Echo Knight** — Manifest an echo of yourself as a bonus action: spectral, translucent, gray image (AC 19, 1 HP, immune all conditions). It lasts until destroyed, dismissed, you manifest another, or you're incapacitated.

**Echo Uses:**
- Mentally command echo to move up to 30 ft. (no action)
- Teleport to echo's space (bonus action, costs 15 ft. movement)
- Attacks can originate from you or your echo's space (choose per attack)
- Opportunity attacks as if you were in echo's space
- If a creature within 5 ft. of echo can be seen, use reaction to make opportunity attack from echo's space

**Unleash Incarnation (4 / Long Rest)** — When taking the Attack action, make one additional melee attack from the echo's position.

**Echo Avatar (1 Action)** — Temporarily transfer consciousness to echo. See/hear through it up to 1,000 ft. away; you are deafened and blinded. Lasts up to 10 minutes.

**Shadow Martyr (1 / Short Rest)** — Reaction before an attack roll: teleport echo in front of the targeted creature. The attack is made against the echo instead.

**Reclaim Potential (4 / Long Rest)** — When your echo is destroyed by taking damage, gain temp HP equal to 2d6 + CON modifier.

**Second Wind (1 / Short Rest)** — Bonus action: regain 1d10+15 HP.

**Action Surge (1 / Short Rest)** — Take one additional action.

**Indomitable (2 / Long Rest)** — Reroll a failed saving throw.

**Fighting Style: Dueling** — +2 damage when wielding a melee weapon in one hand with no other weapons.

**Martial Versatility** — Replace a fighting style or maneuver on ASI.

**Feats:** Savage Attacker (reroll melee damage dice once per turn, use either total) · Fighting Initiate: Protection (reaction to impose disadvantage on an attack against another creature within 5 ft. while wielding a shield)

**Kalashtar Traits:** Dual Mind (advantage on WIS saves) · Mental Discipline (resistance to psychic damage) · Mind Link (speak telepathically to any creature within 150 ft., regardless of shared language; can grant them the ability to speak back for 1 hour) · Severed from Dreams (immune to magical sleep effects)

---

## Spells

**6th Level (item):** Arcane Gate *(from Second Rod Piece)*

---

## Equipment

**Attuned:** Armor of Invulnerability · Sun Blade · Belt of Storm Giant Strength

**Armor:** Armor of Invulnerability (Mithral Splint, 65 lb.) · Sentinel Shield

**Weapons:** Sun Blade · Handaxe ×2 · Weapon of Certain Death, Morningstar · Double-Bladed Scimitar

**Notable:** Goggles of Night · Necklace of Adaptation · Stone of Good Luck (Luckstone) · Figurine of Wondrous Power (Obsidian Steed) · Mithral Splint · Second Rod Piece

**Languages:** Common, Infernal, Quori, Undercommon

**Tools:** Lyre
""",
    },

    {
        'title': 'Ula Zorr',
        'category': 'characters',
        'status': 'active',
        'body': """\
# Ula Zorr

**Class & Level:** Wizard 15 (School of Enchantment)
**Species:** Custom Lineage
**Background:** Failed Merchant
**Alignment:** Neutral Good
**Player:** kennjason

---

## Appearance

Male, age 40. Small, 4'0", 110 lbs. Pale tan skin, green eyes, dark brown hair.

---

## Personality

**Traits:** I need to pry into people's lives. It's the only way to get to the truth.

**Ideal:** If I can get to the truth, the heart of the matter, then I can handle anything.

**Bond:** The truth will set you free. My spellbook helps me track all the little truths of the world.

**Flaw:** Everyone has secrets, despite what they say. People lie to protect themselves, but that won't stop me.

**Allies:** Alathene Moonstar, proprietress of The Blushing Mermaid and arch-lich.

---

## Backstory

Born and raised in Waterdeep. Instead of joining a guild, he opened his own magical item shop in the Southern Ward. Eventually, his shop started getting pressured by the Xanathar Guild for protection. He tried using charm magic on a bugbear to figure out how to stop them — the spell didn't work and the bugbear attacked him and trashed his shop. After that, the guild left him alone, but his business was blacklisted and shortly went under.

After Ula was made homeless, the Xanathar himself appeared to Ula and offered him a job. He became a low-level clerk tracking the guild's plunder and treasure. He kept using charm magic to learn more and more about the guild and the Xanathar himself, eventually becoming the Keeper of Secrets — the guild's foremost "information extraction specialist."

All was well until one day Xanathar became weary of Ula and tried to have him killed. He escaped the Xanathar's ire (with help from a Feign Death spell) and left Waterdeep. With a new lease on life and a deep sense of betrayal, he made his way to Neverwinter.

*Core Moral Beliefs:* I can handle things if they just tell me the truth.

*Long-term goal:* Resurrect his parents. His parents were Harpers — that's why they never told him what was going on. He was tricked when he was younger by a Zhentarim and accidentally sold them out. When he found them dead, he was enraged that they never told him the truth.

---

## Stats

| | |
|-|-|
| **AC** | 16 |
| **HP** | 92 |
| **Speed** | 30 ft. (Walking) · 50 ft. (Flying) |
| **Initiative** | +0 |
| **Hit Dice** | 15d6 |
| **Proficiency Bonus** | +5 |
| **Spellcasting Ability** | INT |
| **Spell Save DC** | 20 |
| **Spell Attack Bonus** | +12 |
| **Passive Perception** | 9 |
| **Passive Insight** | 14 |
| **Passive Investigation** | 20 |

**Ability Scores:** STR 10 (+0) · DEX 10 (+0) · CON 14 (+2) · INT 20 (+5) · WIS 8 (−1) · CHA 16 (+3)

**Saving Throw Bonus:** +1 on saves; advantage against spells and magical effects.

**Senses:** Darkvision 60 ft.

**Top Skills:** Arcana +10 · Investigation +10 · History +5 · Nature +5 · Religion +5 · Insight +4

---

## Combat

| Attack | Hit | Damage |
|--------|-----|--------|
| Fire Bolt | +12 | 3d10 Fire |
| Shocking Grasp | +12 | 3d8 Lightning |
| Staff of Defense | +5 | 1d6 Bludgeoning (9/10 charges) |
| Dagger | +5 | 1d4 Piercing |

---

## Key Features

**School of Enchantment** — Master of charming, compelling, and mind-altering magic.

**Enchantment Savant** — Copy enchantment spells into spellbook at half cost/time.

**Hypnotic Gaze** — Action: charm one creature within 5 ft. (WIS DC 20 or charmed, speed 0, incapacitated until end of next turn). Can extend each turn as an action.

**Instinctive Charm (Reaction)** — When attacked by a creature within 30 ft., divert the attack to the nearest other creature within range (WIS DC 20 to resist). On failure, attacker targets someone else.

**Split Enchantment** — When casting a 1st+ level enchantment that targets only one creature, target a second creature as well.

**Alter Memories** — When charming with an enchantment, alter one creature's understanding so it remains unaware of being charmed. Before spell expires, can make creature forget up to 4 hours of charmed time (INT DC 20).

**Arcane Recovery (1 / Long Rest)** — Short rest: recover spell slots totaling up to 8 combined levels (no 6th level or higher).

**Cantrip Formulas** — Replace one wizard cantrip on long rest by consulting spellbook.

**Telekinetic Shove (Bonus Action)** — Telekinetically shove one creature within 30 ft. (STR DC 18 or moved 5 ft. toward or away).

**Feats:** Telepathic (INT +1; Detect Thoughts 1/LR; telepathic communication within 60 ft.) · Telekinetic (INT +1; Mage Hand invisible and silent; telekinetic shove bonus action) · Fey Touched (INT +1; Misty Step 1/LR; Silvery Barbs 1/LR)

**Custom Lineage Traits:** Darkvision 60 ft. · Feat at 1st level · Variable Trait

---

## Spells

**Cantrips:** Shocking Grasp · Elementalism · Fire Bolt · Mind Sliver · Minor Illusion · Light *(Driftglobe)* · Mage Hand *(Telekinetic)*

**1st Level (4 slots):** Charm Person · Absorb Elements · Comprehend Languages [R] · Identify [R] · Detect Magic [R] · Alarm [R] · Disguise Self · Find Familiar [R] · Magic Missile · Shield · Silent Image · Silvery Barbs *(Fey Touched)*

**2nd Level (3 slots):** Suggestion · Tasha's Mind Whip · Mirror Image · Hold Person · Knock · Darkvision · See Invisibility · Gift of Gab · Earthbind · Detect Thoughts *(Telepathic)* · Misty Step *(Fey Touched)*

**3rd Level (3 slots):** Counterspell · Hypnotic Pattern · Haste · Dispel Magic · Tongues · Speak with Dead · Fireball · Enemies Abound · Daylight *(Driftglobe)*

**4th Level (3 slots):** Charm Monster · Phantasmal Killer · Greater Invisibility · Mab's Psychic Lance

**5th Level (2 slots):** Dominate Person · Modify Memory · Hold Monster · Synaptic Static · Wall of Force · Arcane Hand

**6th Level (1 slot):** Chain Lightning · Otto's Irresistible Dance · Circle of Death · Sunbeam · Disintegrate

**7th Level (1 slot):** Plane Shift

**8th Level (1 slot):** Dominate Monster

---

## Equipment

**Attuned:** Cloak of Protection · Robe of the Archmagi · Heart Weaver's Primer

**Armor:** Robe of the Archmagi

**Weapons:** Staff of Defense · Dagger

**Notable:** Broom of Flying · Iron Flask · Ring of Spell Storing · Wand of Magic Missiles · Well of Many Worlds · Driftglobe · Moonblade · Libram of Souls and Flesh · Ioun Stone of Intellect · Ring of the Ram · Scarab of Protection · Tome of the Stilled Tongue · Hat of Wizardry · DRAGON Spellbook · God Blood Vial · Eberon Quicksilver Flask · Obsidian Horse

**Languages:** Common, Dwarvish, Gnomish, Telepathy

**Tools:** Tinker's Tools
""",
    },

    {
        'title': 'Wankershim',
        'category': 'characters',
        'status': 'active',
        'body': """\
# Wankershim

**Class & Level:** Bard 5 / Paladin 10 (College of Valor / Oath of Redemption)
**Species:** Half-Elf
**Background:** Urchin
**Alignment:** Neutral Good
**Player:** kennjason

---

## Stats

| | |
|-|-|
| **AC** | 17 |
| **HP** | 118 |
| **Speed** | 30 ft. (Walking) · 30 ft. (Flying) |
| **Initiative** | +5 |
| **Hit Dice** | 5d8 + 10d10 |
| **Proficiency Bonus** | +5 |
| **Spellcasting Ability** | CHA (both classes) |
| **Spell Save DC** | 17 (Bard) / 17 (Paladin) |
| **Spell Attack Bonus** | +9 / +9 |
| **Passive Perception** | 15 |
| **Passive Insight** | 20 |

**Ability Scores:** STR 11 (+0) · DEX 16 (+3) · CON 14 (+2) · INT 12 (+1) · WIS 10 (+0) · CHA 18 (+4)

**Immunities:** Magical sleep · Disease · Frightened · Critical Hits

**Senses:** Darkvision 60 ft.

**Saving Throw Bonus:** +4 on saves; advantage against being charmed; magic can't put him to sleep.

**Top Skills:** Persuasion +14 · Insight +10 · Sleight of Hand +8 · Stealth +8 · Deception +6 · History +6 · Intimidation +6 · Performance +6 · Perception +5 · Athletics +5 · Acrobatics +5

---

## Combat

| Attack | Hit | Damage |
|--------|-----|--------|
| Holy Avenger Rapier | +11 | 1d8+8 Piercing +2d10 Radiant (Finesse, Vex) |
| Moonblade | +11 | 1d8+8 Slashing (Versatile, Finesse, Sap; 6/6 charges) |
| Dagger | +8 | 1d4+5 Piercing |
| Unarmed Strike | +5 | 1 Bludgeoning |

**Divine Smite** — Expend a spell slot to deal 2d8 extra radiant damage (+1d8 per slot level above 1st, max 5d8; +1d8 vs undead/fiends).

---

## Key Features

**Sacred Oath: Oath of Redemption** — Dedicated to peaceful resolution and protecting others.

**Channel Divinity (1 / Short Rest):**
- *Emissary of Peace* — Bonus action: +5 to CHA (Persuasion) checks for 10 minutes.
- *Rebuke the Violent* — Reaction immediately after an attacker within 30 ft. hits another creature: the attacker makes WIS save (DC 17) or takes radiant damage equal to the damage dealt (half on success).

**Oath Spells (always prepared):** Sanctuary · Sleep · Calm Emotions · Hold Person · Counterspell · Hypnotic Pattern · Dimension Door · Guardian of Faith · Hold Monster · Wall of Force

**Divine Sense (5 / Long Rest)** — Detect celestials, fiends, and undead within 60 ft. (not behind total cover) until end of next turn.

**Lay on Hands (50 HP / Long Rest)** — Touch to restore any HP amount from pool, or 5 HP to cure a disease or neutralize a poison.

**Fighting Style: Dueling** — +2 damage when wielding a melee weapon in one hand.

**Divine Health** — Immune to disease.

**Extra Attack** — Attack twice when taking the Attack action.

**Aura of Protection** — Friendly creatures within 10 ft. add +4 (CHA modifier) to all saving throws while conscious.

**Aura of the Guardian (Reaction)** — When a creature within 10 ft. takes damage, magically take that damage instead.

**Aura of Courage** — Friendly creatures within 10 ft. can't be frightened while conscious.

**Indomitable** *(Bard: Jack of All Trades)* — Add +2 to any ability check not already including proficiency.

**Bardic Inspiration (4 / Short Rest, d8)** — Bonus action: grant a creature within 60 ft. an inspiration die to add to one ability check, attack roll, or saving throw.

**Combat Inspiration** — A creature with Bardic Inspiration can use it to add the die to a weapon damage roll or AC against one attack (after seeing roll, before outcome).

**Song of Rest** — During short rest, creatures regaining HP spend Hit Dice and regain an extra 1d6.

**Expertise** — Proficiency doubled for Persuasion and Insight.

**Font of Inspiration** — Regain all Bardic Inspiration uses on short or long rest.

**Feats:** Defensive Duelist (Reaction: add +5 to AC when hit with a finesse weapon you're proficient with)

**Half-Elf Traits:** Darkvision 60 ft. · Fey Ancestry (advantage vs charmed, immune to magical sleep) · Skill Versatility

---

## Spells

**Bard Cantrips:** Vicious Mockery · Light · Prestidigitation

**Bard Slots (1st–3rd, folded into multiclass pool):**
- *1st:* Feather Fall · Heroism · Speak with Animals [R]
- *2nd:* Invisibility · Knock
- *3rd:* Glyph of Warding · Tiny Hut [R] · Dispel Magic

**Paladin Prepared + Always Prepared:**
- *1st:* Protection from Evil and Good · Shield of Faith · Cure Wounds · Ceremony · Sanctuary [AP] · Sleep [AP] · Bless · Command · Detect Evil and Good · Detect Magic · Detect Poison and Disease · Divine Favor · Heroism · Purify Food and Drink · Compelled Duel · Searing Smite · Thunderous Smite · Wrathful Smite · Divine Smite
- *2nd:* Find Steed · Locate Object · Magic Weapon · Protection from Poison · Branding Smite · Shining Smite · Aid · Lesser Restoration · Gentle Repose · Warding Bond · Zone of Truth · Calm Emotions [AP] · Hold Person [AP]
- *3rd:* Crusader's Mantle · Revivify · Counterspell [AP] · Hypnotic Pattern [AP] · Create Food and Water · Daylight · Dispel Magic · Magic Circle · Remove Curse · Aura of Vitality · Blinding Smite · Elemental Weapon · Spirit Shroud
- *4th (1 slot):* Dimension Door *(Cape of the Mountebank)*
- *5th (2 slots):* Gaseous Form *(Moonblade)* · Haste *(Moonblade)*
- *6th (Moonblade):* Counterspell

---

## Equipment

**Attuned:** Winged Boots · Holy Avenger Rapier · Moonblade

**Armor:** Adamantine Breastplate

**Weapons:** Holy Avenger Rapier · Moonblade · Dagger · Rapier

**Notable:** Cape of the Mountebank · Ring of Evasion · Ring of Spell Storing · Potion of Healing (Superior ×2) · Potion of Healing · Holy Water (×10) · Bombs (×9) · God Juice (×25) · Chesterfield (Draft Horse) · Wagon

**Languages:** Common, Elvish, Orc

**Tools:** Disguise Kit, Drum, Horn, Lute, Thieves' Tools
""",
    },

]


def main():
    if not _token:
        print('ERROR: TURSO_AUTH_TOKEN not set')
        sys.exit(1)

    print('Connecting to Turso…')
    row = fetchone("SELECT id FROM campaigns WHERE slug='vecna'")
    if not row:
        print('ERROR: vecna campaign not found in DB')
        sys.exit(1)
    campaign_id = int(row[0])
    print(f'Vecna campaign_id = {campaign_id}')
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
