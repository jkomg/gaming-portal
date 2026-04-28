#!/usr/bin/env python3
"""Import Scum & Villainy setting lore into GotW wiki.

Creates pages in three categories:
  lore      — The Procyon Sector, The Hegemony, Precursors, The Way, Guilds, Xenos
  locations — All four systems + major notable locations
  factions  — Hegemony factions, Criminal/Fringe factions, Weirdness factions

Usage:
    export DATABASE_URL=$(gcloud secrets versions access latest --secret=DATABASE_URL --project=jkomg-gaming)
    export TURSO_AUTH_TOKEN=$(gcloud secrets versions access latest --secret=TURSO_AUTH_TOKEN --project=jkomg-gaming)
    python3 scripts/import_gotw_lore.py
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

# ── Turso connection ───────────────────────────────────────────────────────────

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


# ── Page definitions ───────────────────────────────────────────────────────────

PAGES = [

    # ══════════════════════════════════════════════════════════════════════════
    # LORE
    # ══════════════════════════════════════════════════════════════════════════

    {
        'title': 'The Procyon Sector',
        'category': 'lore',
        'status': 'active',
        'body': """\
# The Procyon Sector

The Procyon Sector is a distant, underdeveloped corner of Hegemonic space — far enough from the galactic Core that the Hegemon pays it little attention. Four star systems, dozens of worlds, and a tangle of jump gates connect a region full of opportunity, danger, and ancient mystery.

The sector is nominally administered by **House Malklaith**, one of the Hegemony's seven Noble Houses. Malklaith's Governor, Ritam al'Malklaith, keeps his seat on Warren (moon of Aleph, in the Rin system). Galactic law is present here, but slower and less certain than in the Core worlds.

## The Four Systems

| System | Character | Notable For |
|--------|-----------|-------------|
| **Rin** | Entry point, administrative hub | Three jump gates (including path to Core), Warren city-moon, Ashtari Cloud pirate nebula |
| **Holt** | Ocean world, crystalline planets | Mem ocean planet (Memish xenos), Vos "Glimmer" crystal world, unstable Rin–Holt gate |
| **Iota** | Binary stars, industrial powerhouse | Iota shipyards, Amerath garden world, Indri factory planet |
| **Brekk** | Civilized, wealthy, lots of dark lanes | Nightfall culture capital, Aketi jungle preserve, Shimaya desert world |

## Getting Around

Jump gates connect the systems. Travel through a gate is near-instant, but gates can be temperamental — the Rin–Holt gate is notoriously unstable, and the Hantu Gate in Holt has never been activated at all.

Within a system, travel between planets takes hours to days by conventional drive. Ansible networks handle in-system communication instantly; cross-system messages travel by courier ship, making live conferences between systems rare.

## The Mysterious Signal

A Precursor signal bleeds through the Procyon Sector — its origin unknown, its meaning unclear. Multiple factions want it. Your crew just wanted a simple job.
""",
    },

    {
        'title': 'The Hegemony',
        'category': 'lore',
        'status': 'active',
        'body': """\
# The Hegemony

The Hegemony is the dominant galactic government, ruled by the **Hegemon** from a seat near the galactic Core. It is vast, ancient, and slow — which means the Procyon Sector, on the fringe, operates with considerable de facto autonomy.

## Structure

The galaxy is carved into sectors, each placed under the stewardship of one of **seven Noble Houses**. The Procyon Sector belongs to **House Malklaith**. Technology and science fall under approved **Hegemonic Guilds** (such as the Guild of Engineers and Starsmiths Guild). Mysteries and arcane matters fall to approved **Hegemonic Cults** (such as the Church of Stellar Flame).

The Hegemon's greatest task is keeping power divided between factions so they always squabble over it and never unify to seat a new Hegemon.

## Law & Order

Legal matters are handled planet by planet. Planets with larger populations and wealth have local law enforcement agencies answering to the planetary Governor. **System Police** handle intersystem crimes. The **Legion** (military) can be called in for matters too complex for the System Police.

In Procyon, police wear the green and black of House Malklaith.

## Life Under the Hegemony

- Planets that can't sustain life are **resource-stripped** to the core (see: Baftoma in the Rin system).
- All ships must be certified and registered with the **Starsmiths Guild** — though forged papers are common.
- The **Counters Guild** maintains the galactic currency network, building shadow repositories in every system.
- The Hegemony is a distant source of law and power. In Procyon, it shows up slowly, and often incompletely.

## House Malklaith in Procyon

Governor Ritam al'Malklaith rules from Warren (Rin system). He is in disgrace within House Malklaith and seeks to improve his position by acquiring illegal Ur artifacts. The Governor is more focused on Core politics than day-to-day sector administration — which leaves a lot of room for crews to operate.

The **Starless Veil** (Hegemonic counterintelligence and spies) is currently at odds with House Malklaith and seeks to undermine the Governor to make a case for change in House control.
""",
    },

    {
        'title': 'The Precursors & Ur Artifacts',
        'category': 'lore',
        'status': 'active',
        'body': """\
# The Precursors & Ur Artifacts

Before humanity spread through the galaxy, another civilization — the **Ur** (sometimes called the Precursors) — built the jump gate network. They have been gone for a very long time. What they left behind still shapes the sector.

## The Ur Legacy

No one knows exactly what the Ur were. They built the jump gates that make interstellar travel possible. They built structures on various worlds — ruins, temples, installations — many still unexplored or inaccessible. The **Ashtari Cloud** in the Rin system is the remnant of a massive Ur ship, its wreckage generating an in-system nebula.

The Ur also seem to have manipulated stars: the Holt system star burns white but is far older than stars of that type should be, which Hegemonic scientists attribute to ancient Ur manipulation.

## Ur Artifacts

Ur artifacts surface occasionally, usually in ruins or via deep-space salvage. They are extraordinary — and often dangerous.

**Known artifact examples:**
- **Lightblade** — A melee weapon of pure energy, its blade adjustable from hair-thin to broad. Can cut through almost anything, and through some things that don't have a physical form.
- **Anzani Key** — A black key that opens almost any door, vault, or sealed container.
- **Cloak of Night** — A shimmering cloak that bends light, making the wearer near-invisible.
- **The Heart** — A fist-sized crystalline object that pulses like a heartbeat. Causes strange dreams and seems to affect the Way in its vicinity.
- **Void Gate** — A portable doorway device that creates a short-range point-to-point passage.

## Artifacts in Play

Artifacts are not just weapons — they're leverage. They're what factions fight over, what Guilds want to control, and what mystics believe are keys to understanding the Way. Bringing an artifact to market means navigating who wants it, who will kill to get it, and whether it does something unexpected when you pick it up.

The **Church of Stellar Flame** seeks to eradicate dangerous artifacts. The **Cult of the Seekers** wants to open the Hantu Gate. The **Ashtari Cult** communes with Ur gas from the Ashtari Cloud. **Suneaters** are Ur-archaeologists obsessed with recreating jump gate technology.

## The Hantu Gate (Holt System)

The Hegemony has never been able to activate this jumpgate. It seems to be missing a few small but key pieces. Some speculate the Ur locked the gate and hid the keys — though it's anyone's guess as to why. The **Cult of the Seekers** (whose members include the Hegemon's own mother) is determined to open it.
""",
    },

    {
        'title': 'The Way & Mystic Cults',
        'category': 'lore',
        'status': 'active',
        'body': """\
# The Way & Mystic Cults

The **Way** is the name given to a poorly-understood force that permeates the galaxy. Those who can access it — called **mystics** — can sense things at a distance, move objects, read minds, and do stranger things still. The Way seems to be connected to the Precursor (Ur) ruins scattered across the sector.

## Accessing the Way

Mystics learn to **Attune** to the Way — a process of opening themselves to its currents. This can be done through meditation, through exposure to Ur artifacts, through certain drugs, or through dangerous practices like those of **The Agony** (a cult that infects members with Way creatures to access the universe in unsettling ways).

The Way is not perfectly understood, even by those who use it. In the deep ocean of Mem, attuning for long-term projects grants +1d — but low rolls may attract dangerous Way attention.

## Approved Hegemonic Cults

The Hegemony controls mystic practice through official cults:

- **Church of Stellar Flame** *(Tier IV)* — Religious zealots seeking to root out heretics and destroy dangerous artifacts and mystic activity. Led by High Priestess **Alaana** (driven, ex-heretic). Each member is branded with the "Kiss of Light." They operate the battle cruiser *Way of Light*.
- **Mendicants** — Originally the Church of the Emerald Heart. Politically destroyed, they now wander the stars as traveling physicians and healers. They will tend to anyone who requests aid.

## Unofficial & Outlawed Groups

- **The Agony** *(Tier III)* — Human cultists who infect themselves with Way creatures to access strange abilities. Named for the pain. Based on a platform orbiting Planet Omega (Holt system). They plan to move Planet Omega toward Mem to "feed the oceans."
- **Ashtari Cult** *(Tier III)* — Precursor worshipers who claim Ur descent. They inhale gases from the Ashtari Cloud and receive visions of Ur lives eons ago. They believe Ur sites on Nightfall's moons can control the planetoids themselves.
- **Nightspeakers** *(Tier II)* — Mystics with dark proclivities, seeking a set of dangerous Precursor artifacts. Initiates train aboard the vast, unlit ship *Blackstarr* (Brekk system).
- **Cult of the Seekers** *(Tier II)* — Wandering mystics studying artifacts and seeking new places. They want to open the Hantu Gate. The Hegemon's mother is a member.
- **Vignerons** *(Tier III)* — A small handful of immortality seekers using artifact-tech implants and chemicals distilled from the living. Several have been around for hundreds of years.
- **Vigilance** *(Tier I)* — Warrior mystics bearing artifact blades, enforcing an ancient code of justice.
- **Conclave 01** *(Tier I)* — Independent, sentient Urbots led by an ancient Urbot called the Prime. Working to control mining sites and gain control over Precursor AI modules.

## The Way in the Iota System

A long-period comet (ZX-1138) has recently diverged from its course, moving much closer to Indri. Mystics claim this has shifted the system's Way lines, making the Way sometimes act unpredictably in Iota.
""",
    },

    {
        'title': 'The Guilds of the Hegemony',
        'category': 'lore',
        'status': 'active',
        'body': """\
# The Guilds of the Hegemony

Hegemonic Guilds are the official bodies that control technology, commerce, and infrastructure across the galaxy. Having a Guild License matters — expired licenses mean your ship doesn't get serviced, your cargo doesn't get cleared, and the system police start paying attention.

## Major Guilds in Procyon

### Guild of Engineers *(Tier V)*
The most powerful Guild presence in Procyon. Responsible for resource acquisition, cybernetics, AI, tech advancement, and research. They often have the best toys. They control **SB-176** (the platform above Vet in Rin), the **Iota Shipyards**, and the **IA-23** station above Vos. Known for ever-present monitoring — engagement rolls on SB-176 are always at -1d due to station surveillance.

### Starsmiths Guild *(Tier III)*
Maintain the jumpgates and hyperspace lanes, and build ships. All ships in Hegemonic space must be certified and registered with the Starsmiths — though forged papers are all too common. Allied with House Malklaith and the 51st Legion.

### Counters Guild *(Tier IV)*
Officials who maintain the galactic currency network and build shadow repositories in any system the Guild has a presence in, storing mysterious items and securing auctions and commerce.

### Yaru (Makers Guild) *(Tier II)*
Force-grows clones for labor. Clones are short-lived, have a symbol on their foreheads, and are supposedly only barely sentient. Folks are distinctly uncomfortable around the clones.

## Guild Rules

- Guilds guard their domains jealously.
- There are ship repair shops with mechanics using expired Guild Licenses — common in the fringe.
- Plenty of mystic groups walk freely through the streets of every world — even though they're not part of any official Hegemonic Cult.

## Vos (Glimmer) — Guild Mining

The crystalline world Vos is closely monitored by the Guild of Engineers, which controls crystal extraction via Guild station **IA-23**. Any job done on Vos earns +1 Cred but also +1 Heat — the Guild watches everything here. **Morek and Ra-na** (most feared bounty hunters in Procyon) are on retainer to hunt anyone who loots Vos.
""",
    },

    {
        'title': 'Xenos of Procyon',
        'category': 'lore',
        'status': 'active',
        'body': """\
# Xenos of Procyon

The Hegemony is predominantly human — or close to it. The most commonly found xenos are those that can breathe human atmospheres, function in near-1G gravity, and are roughly human-sized. Many have modifications suited to their homeworlds: more eyes, extra arms, gills, different skin colors, tentacles.

That's not to say you won't find 10-foot-tall, reptile-scaled Norsicans at the docks, or the occasional three-foot furry Wrinlian engineer using their six limbs to perform delicate adjustments inside the wiring of a Guild starbase.

## The Memish (Holt System — Mem)

The Memish are native to **Mem**, the ocean planet in the Holt system. Generally humanoid, they have pitch-black eyes and skin in shades of blue, purple, and green. Instead of hair, they have tentacles. They are able to survive at extreme depths, navigate waters with virtually no light, and organize in complex extended family groups. Their religion involves ritual carving of their scaled hides and imbuing the carvings with carefully tended bioluminescent deep-sea plant life.

The Hegemonic forces broke the Memish military and incorporated them into the Hegemony. Today, Mem is under a Hegemony-appointed Planetary Governor (**Victor Kromyl**), who seeks proof of Memish rebellion. A quiet **Memish Rebellion** faction simmers beneath the surface.

**Memish abilities:**
- *0 Stress:* Breathe water. Hear very low sound waves. Swim incredibly quickly.
- *1 Stress:* Sense electricity (prey-hunting sense from the deeps). Extend rending claws capable of filleting sharkskin. Use deep-water muscles to lift a thug one-handed.
- *2 Stress:* Navigate flawlessly in pitch blackness. Survive briefly in space unharmed. **Attune** to the Way to sense gravitic disturbances and the mystic ability of anyone nearby.
- *Memish Weakness (Optional):* In significantly warm climates, take level 2 or level 3 harm called "Memish Weakness." Removed by immersion in water for 24 hours.

## Xenos in Play

If a player chooses the Xeno starting ability, some guidelines:

- **0 Stress abilities** — Constant, passive. Breathing water, seeing in UV, having a prehensile tail, multiple eyes.
- **1 Stress abilities** — Require exertion. Pushing heat immunity, using sonar in a metal corridor, running faster than prey.
- **2 Stress abilities** — Things humans couldn't attempt. Ripping chains through sheer strength. Breathing fire. A deep-sea xeno ignoring knock-out gas being pumped into a room.

**Optional Rule:** A significant xeno weakness (level 2 or 3 harm equivalent) that can take you out of a scene adds a **gambit** for your crew when it comes up in game.
""",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # LOCATIONS
    # ══════════════════════════════════════════════════════════════════════════

    {
        'title': 'System: Rin',
        'category': 'locations',
        'status': 'active',
        'body': """\
# System: Rin

**Gates:** 3 — Rin–Ecliptis (path toward the Core), Rin–Holt (unstable), Rin–Iota.

**Planets:** Aleph (gas giant with moons Warren, Hock, Batter), Vet (gas giant with rings; Space Station SB-176), Baftoma (mined-out husk).

**Major Ports:** Warren (moon of Aleph, Governor's seat), SB-176 (Guild of Engineers controlled), The Cove (pirate base inside the Ashtari Cloud).

## System Overview

Rin is the entry point to the Procyon Sector, colonized just over a hundred years ago by House Nim-Amar. It has never been an important sector, so Malklaith has invested only a minimum of resources in it. Instead, it's used to train young House members or as an assignment to punish those who fail the House. Galactic law is more present here than the rest of the sector — this is the seat of the sector's administration, containing gates to three systems, including a path toward the rest of the Hegemony.

## Notable Places

**Aleph** — Between poisonous gases and tectonic instability, Aleph would be a planet to avoid if not for its mineral stores. Most of the wealth dug from the planet is taxed heavily by the Governor, leading to frequent unrest with the miners.

**Baftoma "The Husk"** — Resource exploitation by the Hegemony is comprehensive, and planets incapable of sustaining life are stripped to the core. Baftoma was once such a planet — now only scaffolding of rock remains, its broken form only used by folks hiding or dodging pursuit.

**The Straylight** — The latest fad: an upscale club and cocktail bar where elites can wine and dine. It usually orbits Aleph, though it can move to other planets and moons in the system. Its owner, Chance, runs a tight establishment, but things can sometimes get out of hand.

**The Ashtari Cloud** — An ancient damaged remnant of a massive Ur ship lies in space, generating an in-system nebula. Within it, normal propulsion is minimal and nav systems are dodgy. The **Maelstrom** pirates figured out how to navigate the cloud and made their base of operations within its protective shroud.
""",
    },

    {
        'title': 'Warren',
        'category': 'locations',
        'status': 'active',
        'body': """\
# Warren (Rin System — Moon of Aleph)

Warren is one of the moons of Aleph and the home to an ecumenopolis — a city spanning the entire surface of the moon. It's the capitol of the Rin system, and system Governor **Ritam al'Malklaith** makes his residence here. On Warren, you can find anything you need — for a price. Its high-rises are full of legitimate business dealings, and its streets far less so.

**Rule:** *Warren is a wretched hive of villainy, yet also the Hegemonic seat of power in the system. You can take +1d to acquire assets here, if you also accept +2 Heat.*

**Scene:** A bustling street market with neon signs promising foods of all kinds in several languages. Hovercars streaming between towering buildings. The bass beat of a basement club playing the latest mix; patrons stumbling onto the street, singing. Socialites attending a gala at the Governor's mansion.

## Notables

- **Ritam al'Malklaith** — Governor of the Rin system, in disgrace within House Malklaith. Seeks to improve his position by acquiring illegal Ur artifacts. (*callous, ambitious, strange*)
- **Liara Uria** — Owner and operator of the Lock Luna, the most infamous bar in the undercity. (*cunning, unforgiving, popular*)
- **Rocco Apple** — Ship designer extraordinaire. Only makes one of each ship designed. (*artistic, aloof*)
- **Pasha Qu'olin** — Once a feared assassin among the Knives, now a Syndicate leader. Loves good food and pit fights. (*sly, corpulent, sartorial, decadent*)
""",
    },

    {
        'title': 'SB-176',
        'category': 'locations',
        'status': 'active',
        'body': """\
# SB-176 (Rin System — Above Vet)

You don't need a planet in order to mine. Or at least, you don't need ground. This combination "mining" platform and space colony is responsible for extracting resources from Vet, the gas planet below. The mining rigs in the skies below — mostly manned by Urbots — send their goods to this central hub. Most of those are packaged and fired towards the Rin–Ecliptis gate.

**Rule:** *Engagement rolls on SB-176 itself are always at -1d due to ever-present station monitoring. Any jobs run against Guilders here are considered to be on hostile turf.*

**Scene:** Cold clacking of footsteps on the brilliantly clean main concourse. Whispers of politicos taking tea at a parlor. Children running down halls, laughing. The hum of generators in the darkened side passages leading to the lower levels. Dingy workers shouting in the cramped quarters of the mining rigs.

## Notables

- **Yast Jor** — Guilder head of the outpost. Known for getting things done, even if it means bending the rules. A thrill-seeker; keeps a Guild-enhanced racing ship for rare days off. (*commanding, shrewd, bold*)
- **Kasumi Ortcutt** — A mystic who claims to hear the voice of Vet, the gas giant the platform is mining. Trades information, including esoterica on the Ur. (*passionate, strange, religious*)
- **Espa "Bolt" Wu** — Labor organizer for the Guild miners. Rabble-rouser beloved by the workers. Has been incarcerated numerous times for crimes both real and fabricated. (*popular, dissident, ambitious*)
""",
    },

    {
        'title': 'The Cove',
        'category': 'locations',
        'status': 'active',
        'body': """\
# The Cove (Rin System — Ashtari Cloud)

The Maelstrom pirates have made a station out of derelict freighters, cargo containers, and stolen scrap metal. They call this home "the Cove." Enterprising individuals can discover where it is located if they have the tenacity or contacts — though it moves about within the Ashtari Cloud. Only the best friends of pirates might be granted storm drives to better navigate with.

**Rule:** *Conflicts at the Cove are rampant, but by Banshee's decree no murder is allowed. Those needing to settle blood feuds resort to kidnapping and killing folks outside the Cloud.*

**Scene:** Quick bets taken on an open brawl between two captains over slights. Blue-white sparks of maintenance workers welding on a new ship. Fresh water misting over rows of hydroponics. A station-wide broadcast of the Banshee's latest conquest, followed by cheers throughout the halls.

## Notables

- **Pirate Queen Alanda "The Banshee" Ryle** — A larger-than-life figure with a hatred for the Hegemony. Tough and violent, she enforces a pirate code on those who would follow her. Once stranded her first lieutenant on a barren world for mutiny. (*proud, demanding, honorable*)
- **Praxis Ivanov** — Merchant always willing to make a deal. His tentacles are tattooed with the story of his several-hundred-year life. (xeno, *experienced, shrewd, loves to barter*)
- **Kai Quag** — Mid-level Cobalt boss. Arranges protection for Cobalt smuggling runs and meets with potential clients at the Cove. (*cautious, charming, confident*)
""",
    },

    {
        'title': 'System: Holt',
        'category': 'locations',
        'status': 'active',
        'body': """\
# System: Holt

**Gates:** 2 — Holt–Rin (unstable), Holt–Hantu (unopened).

**Planets:** Sonhandra (tidally locked), Mem (ocean planet), Vos (crystalline, aka "Glimmer").

**Major Ports:** Spaceport Keyan (artificial island chain near the government palace on Mem), IA-23 (Guild of Engineers, above Vos), Ugar (low-key spaceport on Sonhandra).

## System Overview

Holt was the second Procyon system to be colonized, though the Rin–Holt gate was troublesome to stabilize. Hegemonic scientists eventually found a series of Ur keys in the system that forced the gate to consistently lead to Holt. The gate remains temperamental, however, and has been known to open on its own. No ships have come through during these spontaneous openings — so far.

The Holt system star burns white, though it is far older than stars of this type should be, which Hegemonic scientists attribute to ancient Ur manipulation.

## Notable Places

**Jerec's Junkyard** — A free-floating mass of ships and parts, connected via magnetism and cabling. If you're looking for equipment on the cheap, the Junkyard is your place — though it will likely be missing a piece or two. Jerec also buys, and is a canny haggler.

**Hantu Gate** — The Hegemony has never been able to activate this jumpgate. Compared to other jumpgates it seems to be missing a few small but key pieces. It has been speculated that the Ur locked the gate and hid the keys somewhere, though it's anyone's guess as to why. The **Cult of the Seekers** is determined to open it.

**Trade Platform Auto #4** — The Guild set up an automated platform for selling fuel, covered in defensive systems to deter theft. Because of this, some parties conduct negotiations here to discourage escalation. Nobody knows what happened to the first three platforms.

**Planet Omega** — Three survey crews and one military expedition vanished before the Legion quarantined this planet. It's overrun by a deadly life form that nests within Ur ruins and can resist nukes from orbit. The Hegemony considers it hostile, but insignificant to its plans. The **Agony** cult has established a base platform in orbit.
""",
    },

    {
        'title': 'Mem',
        'category': 'locations',
        'status': 'active',
        'body': """\
# Mem (Holt System — Ocean Planet)

Mem is an ocean planet colonized by the Hegemony almost a hundred years ago — but not without a fight. The aquatic xeno inhabitants, the **Memish**, made themselves (and their planetary claims) known. Hegemonic forces broke the Memish military and incorporated them into the Hegemony. Exploration of Mem has proven difficult because of the free-standing gravity wells deep beneath the waves.

**Frozen moon:** Yuura.

**Rule:** *The deeps are littered with Ur sites and strange glows. When in the deeps, using* **Attune** *for long-term projects grants +1d. Low rolls may attract dangerous Way attention.*

**Scene:** Hegemonic officials in sashes, talking with Memish labor bosses. See-through spires rising from the underwater government palace to open-air pavilions. Tourists embarking on submersibles to take in the local sea life. Scientists in exo-suits on deep-sea missions while the Memish watch from the waters.

## Notables

- **Victor Kromyl** — Planetary Governor. Seeks proof of Memish rebellion after a few subordinates vanished. Always with his Legion bodyguard. (*vigilant, meticulous, paranoid*)
- **Espa Nur** — Memish labor boss. His scars are packed with deep-ocean bioluminescence. Reports to Kromyl on seditious behavior, but hides his knowledge of Memish occultism. (xeno, *ambitious, cunning, treacherous*)
- **Wyndam Taru Zahn** — Biology researcher seeking a connection between the Mem and other planetary life, with little success. Gathering an exploration of the ancient Mem city of Bok-Dar. (*wealthy, brilliant, passionate*)
""",
    },

    {
        'title': 'Vos "Glimmer"',
        'category': 'locations',
        'status': 'active',
        'body': """\
# Vos "Glimmer" (Holt System)

Known throughout Procyon by its nickname "Glimmer," the surface of this enormous planet is made of carbon compounds such as graphite and diamond. At night, the largest crystal formations glow with unearthly light — a property many of the crystals retain after being cut. One must dock at Guild station **IA-23** in orbit and shuttle down to do business on the surface.

**Rule:** *Vosian crystals are prized by Guilds and mystics alike. Vos is full of money, but also closely monitored by the Guild. When you do a job on Vos, you earn +1 Cred and +1 Heat.*

**Scene:** Well-armed, permanent blockade in space, with ships waiting for clearance. Smooth walls of dense carbon brick, windows looking out onto the black surface. Diamond-scarred and sooty-faced miners, drinking with shaking hands by their bulky sonic cutters. Pristine shops of the visitor settlement.

## Notables

- **Morek and Ra-na** — Most feared bounty hunters in Procyon. Ra-na, his AI partner, helms his artifact ship and runs ops on his hunts via the strange armor he wears. On retainer to hunt anyone who loots Vos. (*ruthless, vigilant, commanding*)
- **Impera Evazan** — High-ranking Guild logistics officer, responsible for crystal mining. Privy to much of the Guild's supply structure. (*popular, demanding, shrewd*)
- **Yola Sprekk** — Jeweler known for using the unique properties of Vos crystals. Her creations may be the most artful pieces in Procyon. A Sprekk piece can open doors in the most elite circles. (*artistic, charming, proud*)
""",
    },

    {
        'title': 'Sonhandra',
        'category': 'locations',
        'status': 'active',
        'body': """\
# Sonhandra (Holt System)

This planet is tidally locked — the same side of the planet faces the Holt star at all times. The day side is blistering. Oddly, all light sources extinguish about a kilometer into the night side. Most of the settlements are in the twilight border zone, including the capital of **Ugar**. Known for its lax policies regulating trade, Sonhandra has become a choice destination for smugglers and fences alike.

**Moons:** Reigos and Diam — both tiny and can't be landed on.

**Rule:** *Everything is available on Sonhandra for a price. You can always take +1d to acquire assets, but on a 1–3 roll the asset also comes with strings (even if you boost the result with Cred).*

**Scene:** Perpetual twilight amid paved streets and concrete buildings. Howling of frequent wind storms between the two regions. Masked and cloaked strangers congregating around a steel warehouse before an auction begins. Row after row of ships parked in the open dirt on the outskirts of Ugar.

## Notables

- **Del Hex** — Outlaw gunslinger. Has some obvious cybernetics from his Guild days. Wanted in several systems. Runs a vibro-weapon fighting ring deep in the day side. (*ruthless, fast, cautious*)
- **Abra Drake** — Fixer for hire and auctioneer. If she can't get it or sell it, she knows someone who can. (*connected, confident, bold*)
- **Zeed "Tank" Marak** — Mercenary turned Nyct farmer. Knows where and how to hide ships on the night side. (*gambler, commanding, experienced*)
- **Osha** — Nyct-smoking, grizzled ex-Legionnaire. Runs the Three Suns, a gambling den and the biggest local dive. (*deadly, retired, steely*)
""",
    },

    {
        'title': 'System: Iota',
        'category': 'locations',
        'status': 'active',
        'body': """\
# System: Iota

**Gates:** 2 — Iota–Rin, Iota–Brekk.

**Planets:** Amerath (guild garden planet), Indri (manufacturing planet), Lithios (ice planet, hosts a Yaru creche).

**Major Ports:** Reeves (Indri), Solitude Colony (Lithios), Rost (Amerath, Guild), Station CM-5 (Starsmith Yards).

## System Overview

The planets in Iota orbit a pair of stars — a yellow sun (Iota-1) and a brown dwarf (Iota-2). By the time the Hegemony arrived, there were two asteroid belts, one of which still has a large portion of a shattered planet remaining in its midst. The Guilds didn't look a gift horse in the mouth — they set up the **Iota Shipyards**, which service many ships in the sector using metals from the belts.

## Notable Places

**Shipyards** — While the primary yard is run by Starsmiths, many smaller, licensed hubs work on repairs and ship refits. These stations are full of bored spacers looking for any distraction from the wait. Starsmiths sometimes hire foolhardy pilots for prototype tests.

**Belt of Fire** — The region of superheated plasma currents between the Iota binary stars. Spacers spin yarns about the Old Dragon — a vast space creature living there. While the name is whimsical, the Hegemony issued a Quarantine order for the area after several ships disappeared.

**Way Line** — The Iota gates produce a region between them where engines have more thrust, akin to "winds" of a planet. The path is hard to find and switches direction. Pilots in the know use this to gain an advantage on rush deliveries (or daring escapes).

**ZX-1138** — A long-period comet has recently diverged from its course, moving much closer to Indri. Reasons for the course change are unclear, but locals have requested the Governor investigate. Mystics claim this has shifted the system Way lines, making the Way sometimes act unpredictably.
""",
    },

    {
        'title': 'Amerath',
        'category': 'locations',
        'status': 'active',
        'body': """\
# Amerath (Iota System)

With a lush biome, this planet has become well known for pharmaceuticals research and manufacturing. Many regions of the planet are well tended, and due to the comprehensive attentions of the Guild, the garden city of Rost is in perennial bloom. Warm, gentle rains come frequently. The deep forests hide some pirate lairs and **Mendicant** temples amid overgrown ruins.

**Moons:** Gap — a shattered moon that rings the planet.

**Rule:** *While it's ruined and unsanctified, the Mendicants keep their temple and their mystics tend to any and all that request aid. Take +1d when you recover in their care.*

**Scene:** Massive, person-sized flowers blooming along a vine-supported path through the trees. The sweet smell of honey in the air. Scientists having lunch at treetop cafés while reviewing project schedules. Sick pilgrims praying for a cure while waiting to travel to the old Mendicant temple deep in the forests.

## Notables

- **Yon Lirak** — High-end drug dealer. Runs a factory in Rost that never shuts down, producing synthetic narcotics for several major species. (*experienced, ruthless, unforgiving*)
- **Ara Blaze** — Once a star athlete, now a preeminent pit fighter in the underground fight clubs. Has tried every performance-enhancing drug offered to her, and it has changed her. (*ruthless, unforgiving, engineered*)
- **Uyen Al'Vorron** — Famous Noble duelist from the religious House Vorron. Seeking to cultivate a plant for the new vineyard he's planning to grow on a moon near the Core. (*armed, deadly, observant*)
""",
    },

    {
        'title': 'Indri',
        'category': 'locations',
        'status': 'active',
        'body': """\
# Indri (Iota System)

Over 25 percent of all goods manufactured in the Procyon Sector come from this incredibly industrialized planet. Thick, rust-colored clouds create dusk even during the day. From the warehouse-surrounded spaceport of Reves, one can view the impressive skyline of smokestacks and flames from gas burn-offs. Travel without protective gear is not advised.

**Rule:** *The factories have caused massive air pollution; anyone spending any amount of time outside without proper equipment or xeno abilities gains level 2 harm "Indri Lung."*

**Scene:** Hovercar traffic reflecting adverts on buildings. Gas-masked pedestrians walking hurriedly down metal sidewalks with umbrellas treated to deflect acid rain damage. Slow-moving containers being shuttled to warehouses. Storm clouds with multi-hued lightning rolling in.

## Notables

- **Piro Locke** — Owns a number of discreet, well-guarded storage spaces in orbit with a strict no-questions policy. If it's illegal, it's certainly stored by Locke. (*honorable, wealthy, confident*)
- **Zo Yun Ta Ri** — Xeno weapons dealer known for prototypes and specialty armaments. Recently acquired an Ur ship weapon and plans to auction it under the cover of a storm. (xeno, *connected, cautious, meticulous*)
- **Pasha "The Roc" Lensarr** — Local head of the Ashen Knives. Known for a brutal approach to criminal organization. Wears custom-tailored suits that allow his wings to unfurl as needed. (xeno, *fierce, ruthless, demanding*)
""",
    },

    {
        'title': 'Lithios',
        'category': 'locations',
        'status': 'active',
        'body': """\
# Lithios (Iota System — Ice Planet)

Ancient ice palaces dot the surface of this frozen planet, but the race to which they belong has long since passed. Entry to the palaces has been restricted after a string of mysterious explorer deaths. Orbital mirrors shine like artificial suns, keeping a few larger settlements warm and powering large mining rigs for extracting water and liquefied gases. Hosts a Yaru creche.

**Rule:** *When you explore the ice palaces of Lithios, you must make a Resolve resist if you don't want to heed the echoes urging you to wander into the frozen wastes alone.*

**Scene:** A purple and green aurora shining over the freezing cold sky. Ice explorers whispering about the Yaru creche. Heated vapors escaping around Solitude Colony. Colonists in full parkas, riding large, many-eyed canids. Farmers pulling gas-eels and ice-mushroom wine crates in sail-sporting snow skimmers.

## Notables

- **Asha Munzen** — Ex-lover of the Governor, ice climber, mystic, and explorer of the ice palaces and gas caves. Only returns with visions, never artifacts. Attempting to find the "First Message." (*mystic, ambitious, fit*)
- **Ren Larana** — Xenobiologist attempting to revive an ancient xeno found frozen but alive in the ice, despite Hegemonic law forbidding it. Currently trying to sneak the xeno off-world. (*bold, brilliant, confident*)
- **Raf Urich** — Ice pirate, currently stranded on planet. Used his ship weapons to cut a berth in the ice. Has been hiding out, stealing parts to repair his ship. (*experienced, cautious, shrewd*)
""",
    },

    {
        'title': 'System: Brekk',
        'category': 'locations',
        'status': 'active',
        'body': """\
# System: Brekk

**Gates:** 1 — Brekk–Iota.

**Planets:** Aketi (massive jungle planet), Nightfall (civilized, mostly covered in cities), Shimaya (desert world).

**Major Ports:** Ersia City (Shimaya), Yaw Port (Nightfall), Base Camp One (Aketi).

## System Overview

Considered by many to be more civilized than the rest of Procyon, Brekk is home to many finer aspects of the Hegemony — education, art, and culture. Wealth and culture means the Legion presence is strong in the sector. However, there are many odd, non-Starsmith-maintained hyperspace lanes that bend strangely, making long loops perpendicular to planetary orbits. Pilots map these so-called "dark lanes," making it easy to hide and dodge patrols if one is willing to take one's time.

## Notable Places

**Blackstarr** — The vast and largely empty Nightspeaker ship where initiates train for their first year. The ship is unlit and moves routinely to prevent discovery. Exceptions are made for those who have a favorable relationship to the Cult.

**Dendara** — An ancient temple on Nightfall's fifth moon, Todav. Some say it's a Ur temple; others say it's the remains of a forgotten mystic Cult. Its derelict corridors are tough to tour due to the moon's lack of atmosphere and the glitching effect it has on drives and electronics.

**Bright Wind** — A large gas cloud ejected by the star, now used as racing grounds by the **Echo Wave Riders**. Despite being both lethal and illegal, racers from all over the sector compete for cred and fame. Invitations to the races are exclusive and require qualifying in equally hazardous conditions.

**Isotropa Max Secure** — Orbiting near the star, Isotropa is the most notorious prison in Procyon. Wardens broker audiences with prisoners and grant commutations for the powerful and wealthy. They report to Malklaith but the prison largely runs itself.
""",
    },

    {
        'title': 'Nightfall',
        'category': 'locations',
        'status': 'active',
        'body': """\
# Nightfall (Brekk System)

Named for frequent eclipses caused by the planet's 13 moons. Their erratic movements make night only predictable by computer. The city of Yaw is nestled where night and day last between 2 and 12 hours each. It bustles with economic activity and is a frequent destination for tourists and traders. Known for its haute cuisine and theater.

**Moons:** 13. **Space Station:** Obelisk. Controlled by 51st Legion.

**Rule:** *Nightfall is the center of culture in the system, and everything is mostly about who you know. When you acquire assets, roll with Consort instead of crew quality.*

**Scene:** High-rises lighting up block by block as the city goes from day to night in the span of minutes. A rowdy night club spilling dancers clad in black, glow-accented outfits onto a sun-lit street. The blue glow of a public data kiosk projecting tomorrow's night schedule and market changes.

## Notables

- **Saren Galia** — Data broker and bookie. When you can't pay your debts, you become her informant. (*paranoid, fast, connected*)
- **Lotus** — Fashionista and taste-maker, dressed in elaborate costumes. Secretly a high-powered fixer. Has been known to take charity cases when the cause appeals to her. (*popular, passionate, meticulous*)
- **Jet Wolffe** — Scarlet Wolf Assassin. Can be hired at a price, but only takes off-world jobs. Travels with a large, blue-skinned alien animal of unknown origin. (*aloof, confident, unforgiving*)
- **Sol Brighton** — Best lawyer in the sector. (*cunning, connected, expensive*)
""",
    },

    {
        'title': 'Aketi',
        'category': 'locations',
        'status': 'active',
        'body': """\
# Aketi (Brekk System)

This verdant jungle world would be more settled, were it not for the incredibly hostile natural life. Between rapidly spreading carnivorous plants, seasonally rampaging beasts, and hyper-aggressive fish, only a few distinct types visit Aketi — researchers, poachers, and criminals hiding from the law. The planet is labeled a Malklaith "nature preserve."

**Moons:** Suhk, Enro, Awk — none with atmosphere.

**Rule:** *Nobody comes here who doesn't have to. The planet hates you, and jobs are hard to find. Even bounty hunters pass it by. When you lay low on Aketi, take +1d.*

**Scene:** Heavily armed guards patrolling the tall walls of Base Camp One, nervously eyeing the jungle. Research crews packing for their next expedition across from poachers doing the same. A smuggler discussing arrangements with a client in a tent while a personal barista makes them drinks.

## Notables

- **Razor** — A hunter mounting an expedition to catch the deadly Grand Phereniki for a rich client. (*callous, experienced, gambler*)
- **Zokar Pava** — Lost Legionnaire dealing in military-grade weapons. (*cautious, meticulous, dissident*)
- **Intal Brel** — Psy-blade-wielding Concordiat Knight. Travels with a nine-foot-tall xeno, an ex-priest, and an Urbot. Recently lost a party member and hopes to replace them. (*religious, vigilant, honorable*)
- **Asha Ravann** — Base Camp One commander. Instituted a wall-mounted flamethrower measure that's kept the jungle at bay. (*tired, jaded, relentless*)
""",
    },

    {
        'title': 'Shimaya',
        'category': 'locations',
        'status': 'active',
        'body': """\
# Shimaya (Brekk System)

This desert planet is ravaged by electrical storms that occasionally clear colored sand off mineral deposits essential to space travel, or turn it to glass — giving a view to the ruins beneath. Teams race to capitalize on these events. There is a substantial civilian population, including the sector's preeminent educational institution, **Khalud Academy**.

**Moons:** Hawk and Mouse — none with atmosphere.

**Rule:** *Although only students and professors are technically allowed to use the Khalud Academy archives, any Study rolls while using them take +1d.*

**Scene:** Professors walking down the marble paths of the Academy. A market street with insistent vendors selling sandworm kebabs to hungry miners. Excavators packing furiously onto sand-skiffs, ready to take advantage of a storm-cleared deposit. The storm alert blaring citywide.

## Notables

- **Hondo Suzuka** — HNN reporter seeking evidence of conspiracy at Khalud Academy, where several top students have vanished. (*ambitious, vigilant, charming*)
- **Ed Ursis** — Guild Engineer that works on the orbital array and the electrostatic generators it powers to keep the storms away from the capital. Collects colored glass statues. (*dedicated, brilliant, overworked*)
- **Miranda Kasur** — Minerals trader with a load of stolen goods she needs to move. In hiding after her first deal went wrong. (*scared, cunning, proud*)
- **Sahar** — Strange-suited mystic that lives in the desert. (*odd, blue-eyed, ancient*)
""",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # FACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    {
        'title': 'Factions: Hegemony',
        'category': 'factions',
        'status': 'active',
        'body': """\
# Factions of Procyon — Hegemony

These factions represent the official power structures of the Hegemony and its approved organizations.

| Faction | Tier | Goal |
|---------|------|------|
| Guild of Engineers | V | Control of technology and resources |
| Church of Stellar Flame | IV | Root out heretics and dangerous artifacts |
| Counters Guild | IV | Control galactic currency and commerce |
| Starless Veil | IV | Undermine House Malklaith |
| 51st Legion | III | Cleanse Legion of anyone disloyal |
| House Malklaith | III | Maintain grip on the Procyon Sector |
| Isotropa Max Secure | III | (the prison runs itself) |
| Starsmiths Guild | III | Maintain jumpgates and certify all ships |
| Cult of the Seekers | II | Open the Hantu Gate |
| Hegemonic News Network | II | Control the narrative across the sector |
| Yaru (Makers Guild) | II | Expand clone labor force |
| Concordiat Knights | I | Pursue the Light of the World |

---

## Guild of Engineers *(Tier V)*
One of the Hegemonic High Guilds, responsible for resource acquisition, cybernetics, AI, tech advancement, and research. Often have the best toys. Control SB-176, the Iota Shipyards, and Vos crystal extraction.
**Allies:** Starsmiths Guild. **Enemies:** Borniko Syndicate, Acolytes of Brashkadesh, Cobalt Syndicate, Church of Stellar Flame, Yaru.

## Church of Stellar Flame *(Tier IV)*
A religious group with Hegemonic backing, believing that many Precursor artifacts and mystic practices are dangerous. Religious zealots with only a few powerful members, stretched thin. Led by High Priestess **Alaana** (Noble, *driven, ex-heretic*). HQ: the battle cruiser *Way of Light*, orbiting incredibly close to a star. Each member is branded with the "Kiss of Light."
**Allies:** Dyrinek Gang, The Maelstrom. **Enemies:** Guild of Engineers, Starsmiths, Yaru.

## 51st Legion *(Tier III)*
A faction of the Hegemonic military, preparing a coup. HQ: the dreadnought *Scorpio*; naval yards throughout the sector. Commander **Tallon "The Butcher"** (*disciplined, imposing, vicious*) uses his secretly psychic lieutenant **Liyara** to vet officers and quietly place Legionnaires loyal to him in positions of power. Oddly few xenos among the Legion.
**Allies:** House Malklaith, Starsmiths Guild. **Enemies:** Ashen Knives, Church of Stellar Flame, Lost Legion, The Maelstrom.

## House Malklaith *(Tier III)*
A powerful Noble House of the Hegemony that ostensibly owns the sector. Represented by Governor Ritam al'Malklaith, who lives on Warren. Currently dealing with the **Starless Veil** trying to undermine him.

## Starless Veil *(Tier IV)*
Hegemonic counterintelligence and spies. Currently at odds with House Malklaith; they seek to undermine the Governor to make a case for change in House control.

## Starsmiths Guild *(Tier III)*
Maintain the jumpgates and hyperspace lanes, and build ships. All ships in Hegemonic space must be certified and registered with the Starsmiths — forged papers are all too common.
**Allies:** House Malklaith, 51st Legion.

## Hegemonic News Network *(Tier II)*
Those who control the media control the mind. The HNN uses this as leverage over other factions. Spies.

## Concordiat Knights *(Tier I)*
Often accompanied by a motley crew of adventurers, these dozen or so colorful characters have the Hegemonic Churches' blessing to pursue a quest for something called the Light of the World.
""",
    },

    {
        'title': 'Factions: Criminal & Fringe',
        'category': 'factions',
        'status': 'active',
        'body': """\
# Factions of Procyon — Criminal & Fringe

These factions operate outside (or in opposition to) the law.

| Faction | Tier | Goal |
|---------|------|------|
| Lost Legion | IV | Dethrone the Hegemon |
| Scarlet Wolves | IV | Expand assassination contracts |
| Vorex | IV | Free her sister from the Counters Guild |
| Ashen Knives | III | Control major planetary crimes in Rin |
| Borniko Syndicate | III | Steal Governor Malklaith's rings |
| Draxler's Raiders | III | Raid and disable ships (Iota/Brekk) |
| The Maelstrom | III | Expand from the Ashtari Cloud |
| Echo Wave Riders | II | Run the most dangerous races |
| Janus Syndicate | II | Weapons dealing |
| Turner Society | II | Drug trade via Holt |
| Cobalt Syndicate | I | Unify the labor force |
| Dyrinek Gang | I | Grow wherever like-minded folks are |
| Wreckers | I | Pick battlefields clean |

---

## Lost Legion *(Tier IV)*
Formerly the Hegemon's personal guard, they rebelled when the current Hegemon rose to power. They seek to see the Hegemon dethroned and have been guns for hire ever since the schism.

## Scarlet Wolves *(Tier IV)*
Although they often hire themselves out as bounty hunters, the Scarlet Wolves are a renowned group of assassins. Each bears a distinctive tattoo of a wolf holding a star in its mouth.

## Vorex *(Tier IV)*
The most successful information broker to ever live. Can access any terminal in the system — though no one can explain how. Frantically seeking her sister, who the Counters Guild took hostage.

## Ashen Knives *(Tier III)*
Once lean and battle ready, the Ashen Knives are a decadent Syndicate focused on drugs, gambling, and pleasures of the flesh. Drug dens, gambling houses, and a hidden reinforced bunker on Warren (HQ). **Goal:** Control major planetary crimes in Rin.
- *Key NPCs:* **Pasha Qu'oin** (*sly, corpulent, sartorial, decadent*). **Knife Lirik** (xeno, *gambler, deadly, graceful*). **Oya** (*high ranking, greedy, well armed, natural leader*).
- *Quirk:* To join, Knives must take a life. Regional leaders are titled "Pashas."
**Allies:** The Maelstrom. **Enemies:** Cobalt Syndicate, House Malklaith.

## Borniko Syndicate *(Tier III)*
A tightly knit group of thieves who steal high-end technological supplies. Managed to erase a former Counters Guild shadow repository from the Guild ledgers. Joining requires pulling off a heist that impresses the leadership.
- *Key NPCs:* **Ria "Keycard"** (wizard-class hacker, *ambitious, daring*). **Nals E** (Urboticist, *gearhead, muscled*). **MaxiMillions** (*arrogant, expert infiltrator, gorgeous*). **Pip** (mystic, xeno, *small, unsettling*).
**Allies:** Conclave 01, Echo Wave Riders, Wreckers. **Enemies:** Counters Guild, Guild of Engineers, Starsmiths Guild.

## The Maelstrom *(Tier III)*
Rowdy space pirates living in the Ashtari Cloud nebula (Rin system), which is difficult to navigate. Often clash with the Legion. Home base: **The Cove**.

## Draxler's Raiders *(Tier III)*
Fierce individualistic pirates who specialize in disabling ships before boarding. Mostly found in Iota and Brekk.

## Echo Wave Riders *(Tier II)*
Pilots. Many organize illegal races. Many take dangerous jobs for pay, and a few test dangerous new engine/flight technologies for the Guild. They wear a pin that shows how many races they've won.

## Janus Syndicate *(Tier II)*
Weapons dealers that specialize in ship weapons, headed up by the ruthless **Viktor Bax**, who insists on doing the first deal with every client in person.

## Turner Society *(Tier II)*
A Holt-based Syndicate running drug dens masquerading as society houses. Their drugs are cooked with rare Aketi animal parts and Vosian crystals — which they sometimes have trouble sourcing.

## Cobalt Syndicate *(Tier I)*
Once a labor union, now turned to smuggling and extortion to carve out shipping lanes and have a real say. Every member wears a solid blue stripe somewhere on their clothing.
- *Key NPCs:* **Jax** (leader, *cold, killer, arrogant*). **Keve** (captain, *augmented, defiant, enterprising*). **Sephua** (Jax's sibling, thug, *daring, envious, gambler*).
**Allies:** Dyrinek Gang, The Maelstrom. **Enemies:** Ashen Knives, Guild of Engineers, Starsmiths, Yaru.

## Dyrinek Gang *(Tier I)*
Mostly young, disenfranchised xenos who have turned to crime and found strength and solidarity with each other. Based on Warren but looking to expand wherever there are other like-minded folks.

## Wreckers *(Tier I)*
Scavengers and thieves with a few brilliant hackers. They incite factions to fight so that they may pick the battlefields clean later.
""",
    },

    {
        'title': 'Factions: Weirdness',
        'category': 'factions',
        'status': 'active',
        'body': """\
# Factions of Procyon — Weirdness

These factions operate in the realm of mysticism, the Way, and strange Precursor secrets.

| Faction | Tier | Goal |
|---------|------|------|
| Sah'iir | IV | Maintain merchant family dominance |
| Suneaters | IV | Extinguish a star to recreate jump gate tech |
| The Agony | III | Move Planet Omega toward Mem |
| Ashtari Cult | III | Align the moons of Nightfall |
| Vignerons | III | Immortality via artifact tech |
| Ghosts | II | Find their ship the Skeleton Key |
| Mendicants | II | Heal and wander the stars |
| Nightspeakers | II | Find a set of dangerous Precursor artifacts |
| Acolytes of Brashkadesh | I | Convert an entire factory to their religion |
| Conclave 01 | I | Control mining sites and Precursor AI |
| Vigilance | I | Enforce ancient code of justice |

---

## Sah'iir *(Tier IV)*
Tall, ebon-skinned xenos who travel with blindfolded servants that speak for them. They gave the Hegemony their ansible network. Have creepy black-metal ships. Very rich and work as merchant families.

## Suneaters *(Tier IV)*
Ur-archaeologists and scientists obsessed with recreating jumpgate technology. Looking to extinguish a star in pursuit of their goals.

## The Agony *(Tier III)*
Human Cultists who infect themselves with Way creatures to access the universe in unsettling ways. Named for the pain most endure for their usual abilities. HQ: a platform orbiting Planet Omega (Holt system). **Goal:** Move Planet Omega toward Mem to "feed the oceans."
- *Key NPCs:* **Lexal** (mystic, *addicted, power-hungry, winged*). **Iritha** (mystic, *many-limbed, glowing, powerful, potent*). **Noro** (mystic, *calculating, enrapturing, elongated*).
- *Quirk:* Each member is changed in some highly visible way — extra limbs, semi-spectral forms, or many new mouths and eyes.
**Allies:** Dyrinek Gang, The Maelstrom. **Enemies:** Church of Stellar Flame, House Malklaith.

## Ashtari Cult *(Tier III)*
Precursor worshipers claiming Ur descent. They carry vials of gases from the Ashtari Cloud, which they inhale to connect to their presumed ancestors. Visions suggest Ur sites on Nightfall's moons can control the planetoids. **Goal:** Align the moons of Nightfall.
- *Key NPCs:* **Urmak Theon** (*compassionate, educated, well spoken*). **Urmak Lesh** (artificer, ex-Guilder, researcher). **Urley Fean** (Noble, *cautious, hidden, influential*). **Rokono Maex** (captain, *scavenger, coarse, nonbeliever, stoic*).
- *Quirk:* Each member wears a small vial of Ashtari gas to "commune" with their "Ur past."
**Allies:** Ghosts, Mendicants. **Enemies:** Church of Stellar Flame.

## Vignerons *(Tier III)*
A small handful of immortality seekers using artifact-tech implants and chemicals distilled from the living. Several of them have been around for hundreds of years. Most were powerful before their transformation, though they now conceal their true identities.

## Ghosts *(Tier II)*
Scientists who, due to a mishap, live exo-suited in a half-phased state. The Church of Stellar Flame offers a significant bounty on them and their ghost ship, the *Skeleton Key* — dead or destroyed (but certainly not alive).
**Allies:** Ashtari Cult, Mendicants.

## Mendicants *(Tier II)*
Originally the Church of the Emerald Heart, their organization was politically destroyed. Now they wander the stars as traveling physicians and healers. They will tend to anyone who requests aid.
**Allies:** Ashtari Cult, Ghosts.

## Nightspeakers *(Tier II)*
Mystics with dark proclivities bent on finding a set of dangerous Precursor artifacts. Initiates train aboard the vast, unlit ship *Blackstarr* (Brekk system).

## Acolytes of Brashkadesh *(Tier I)*
A collective that eschews individuality. Initiates adopt the same garb and the name "Ashkad," in the pursuit of perfection at any cost. They have an Ur artifact called the **Pillar of Truth** — attuning to it allows Acolytes to communicate with each other and invoke the skills and memories of other Acolytes, who can act through them. Many meditation rooms throughout Indri.
**Allies:** Mendicants. **Enemies:** Ashen Knives, Guild of Engineers.

## Conclave 01 *(Tier I)*
Independent, sentient Urbots led by an ancient Urbot known as the Prime. Working to control the mining sites and gain control over Precursor AI modules required to generate true sentient machines.
**Allies:** Borniko Syndicate, Echo Wave Riders, Wreckers.

## Vigilance *(Tier I)*
Warrior mystics bearing artifact blades, who seek to enforce an ancient code of justice on any they find wanting.
""",
    },
]


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not _token:
        print('ERROR: TURSO_AUTH_TOKEN not set')
        sys.exit(1)

    print('Connecting to Turso…')
    row = fetchone("SELECT id FROM campaigns WHERE slug='gotw'")
    if not row:
        print('ERROR: gotw campaign not found in DB')
        sys.exit(1)
    campaign_id = int(row[0])
    print(f'GotW campaign_id = {campaign_id}')
    print(f'Importing {len(PAGES)} pages (lore / locations / factions)…\n')

    created = skipped = 0
    for page in PAGES:
        title    = page['title']
        category = page['category']
        status   = page['status']
        body     = page['body'].strip()
        base_slug = slugify(title)
        summary  = first_paragraph(body)

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
    print()
    print('Next steps:')
    print('  • All pages are active (visible to players) — these are setting reference pages.')
    print('  • If GotW jobs pages are still categorized as "lore", click the admin')
    print('    "Fix Keys/Vecna Categories" button and re-sync GotW to reclassify them.')


if __name__ == '__main__':
    main()
