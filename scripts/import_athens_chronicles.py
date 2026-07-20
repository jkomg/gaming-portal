#!/usr/bin/env python3
"""One-time import: seed the Athens Chronicles campaign + Book One public-lore wiki pages.

Source: Athens Chronicles Book One - Titanomachy (V5), 1242-1458 CE.
Only player-facing lore is imported here — Story/Scene plot content and
Storyteller-only material lives in the Notion campaign guide instead.

Usage:
    export DATABASE_URL=$(gcloud secrets versions access latest --secret=DATABASE_URL --project=jkomg-gaming)
    export TURSO_AUTH_TOKEN=$(gcloud secrets versions access latest --secret=TURSO_AUTH_TOKEN --project=jkomg-gaming)
    python scripts/import_athens_chronicles.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

CAMPAIGN_SLUG = 'athens-chronicles'
CAMPAIGN_NAME = 'Athens Chronicles'
CAMPAIGN_SYSTEM = 'Vampire: The Masquerade 5th Edition'
CAMPAIGN_DESCRIPTION = (
    "A multi-book Chronicle following a coterie of Athenian Cainites from 1242 CE "
    "to the modern nights, beginning with Book One: Titanomachy (1242-1458 CE). "
    "Player Campaign Guide (Notion): "
    "https://app.notion.com/p/3a33a3e5cab181809536d87e4a9ee2f1"
)

WIKI_CATEGORIES = [
    {'slug': 'lore',       'name': 'Lore',        'icon': 'bi-book-fill'},
    {'slug': 'locations',  'name': 'Locations',   'icon': 'bi-geo-alt-fill'},
    {'slug': 'factions',   'name': 'Factions',    'icon': 'bi-shield-fill'},
    {'slug': 'clans',      'name': 'Clans & Bloodlines', 'icon': 'bi-droplet-fill'},
    {'slug': 'characters', 'name': 'Characters',  'icon': 'bi-person-fill'},
]

# ── Page content ────────────────────────────────────────────────────────────────
# (slug, title, summary, category, body_markdown)

PAGES = [
(
    'setting-overview',
    'Titanomachy: Setting Overview',
    'What the Athens Chronicles are, and the Greek vampire terminology every Cainite in the region uses.',
    'lore',
    """Book One of the Athens Chronicles, **Titanomachy**, begins a multi-part series set in
Athens starting in **1242 CE** and spanning more than two centuries across three Stories,
each separated by roughly a century. As the Chronicle unfolds, Cainite history moves
forward around the coterie: clans rise and fall, the Anarch Movement is born, and the
seeds of both the Camarilla and the Sabbat are planted. Finally, the [Ashirra](the-ashirra)
arrive from the east — the first public alliance of vampire clans the Cainites of Europe
have ever encountered.

Athens in 1242 CE is the capital of the Duchy of Athens, a crusader state of the Latin
Empire that replaced Byzantium after the Fourth Crusade sacked nearby Constantinople in
1204 CE. It is ruled by the Burgundian De La Roche family, and the city has acquired a
Frankish chivalric-style court under Latin rule.

## Greek Terminology

Greek vampires use a distinct vocabulary, much of it drawn from Greek mythology, history,
and culture. It isn't necessary to know these terms to play, but they come up constantly
in play among Storyteller Characters.

**Titanomachy.** What the Greek vampires call the Jyhad — a reference to the mythic clash
between the gods and the titans. Not the same concept as "religious war" or "eternal
struggle," as the term Jyhad is used elsewhere.

**Archon.** Athens is ruled by a [Triumvirate](the-triumvirate-of-athens) of elected
archons rather than a single prince. The rebellious [Prometheans](the-prometheans) use the
term more generally to mean any agent of the elders.

**Cecropia.** The vampires' name for the Acropolis, used as [Elysium](athens-cecropia). A
reference to Cecrops, the mythological snake-man first ruler of Athens — some suspect an
early Ministry (Setite) influence behind the legend.

**Eleusinian Mysteries.** Ancient fertility-cult mystery religions, still practiced in
secret by Malkavian mystics, Cappadocian death cultists, and Ministers.

**Hellene.** Among mortals, a person from ancient Greece. Among vampires, a Greek
descendant of Helena — a methuselah of clan Toreador said to have been Helen of Troy. More
recent descendants are called "harpies" for their tendency toward catty Elysium socializing.

**Laodice.** The Greek name for the Cappadocian antediluvian — feminine, despite the
clan's claim that their ancestor is male.

**Megaskyr.** "Great lord" — a title for a prince who rules over other princes, a rare
and viewed-with-suspicion arrangement among Greek Cainites, who tend to think of cities as
sovereign.

**Prínkipas.** The prince of a city. Some Greek elders prefer the word "tyrant." Athens
itself rejects sole rulers who hold power through threat, electing archons instead.

**Prometheans.** A conspiracy that seeks to restore Carthage, tear down Ventrue and
Toreador tyranny in Europe, and ultimately end elder rule. See [The Prometheans](the-prometheans).

**Titanomachy.** See above — this term names both the Chronicle and the Jyhad itself.
""",
),
(
    'chronicle-timeline',
    'Chronicle Timeline (1242-1458 CE)',
    'The wider history of the region across the three Stories of Book One.',
    'lore',
    """A history of the events mortal and Cainite alike live through across Book One's three
Stories. Storytellers may reveal more of this as the Chronicle progresses.

## Story One: The Apple of Eris (1242 CE)

- **1242 CE** — The "present" at the start of the Chronicle.
- **1252 CE** — The Inquisition begins using torture.
- **1261 CE** — The Latin Empire is conquered by the Nicaean Empire, which reclaims the
  name Byzantine Empire. The Greeks see this as reclaiming their own empire.
- **1274 CE** — Alfonzo of Venice, Lasombra Prince of [Constantinople](constantinople), is
  killed in conflict with his broodmate Guilelmo Aliprando. The Ventrue Anna Comnena
  returns to the city and claims it as hers.
- **1291 CE** — The Mamelukes conquer Acre, ending the Crusades. The Holy Land is lost.
- **1311 CE** — Athens comes under the rule of the Catalan Company after the Duke of
  Athens fails to pay them for defeating his enemies. They join the Crown of Aragon,
  ruling the duchy from nearby [Thebes](thebes).

## Story Two: The Slaying of Python (1342 CE)

- **1342-1350 CE** — The Zealot uprising occurs in [Thessaloniki](thessaloniki), involving
  Tzimisce and Malkavian Anarchs. The mortals overthrow the aristocracy and redistribute
  their wealth; most Cainite elders there are slain.
- **1388 CE** — Florentine soldiers take Athens, conquering the duchy for themselves and
  vying with Venice for ultimate control. The Black Death spreads throughout the duchy.
- **1394 CE** — The elders who will become the Founders of the Camarilla meet for the
  first time to discuss an alliance of clans against the Anarchs.
- **1395 CE** — Anarchs attack the castle of the Ventrue elder Hardestadt in Spain and
  supposedly slay him. He is seen again later that year, and begins to suggest an
  alliance of Cainite clans against the Anarchs and the Inquisition.
- **1397 CE** — The Ottoman Turks invade Athens and take the Acropolis, but are thwarted
  by the Venetians.
- **1402 CE** — The Venetians are overthrown by the Florentines in Athens, who will rule
  until the Ottomans invade in 1458 CE.
- **1405 CE** — The Lasombra antediluvian is supposedly slain in his haven in the Castle
  of Shadows by Anarchs, Lasombra clan members, and Assamites. The attackers' leader, his
  childe Gratiano de Veronese, declines to rule the clan.
- **1413 CE** — The Tzimisce antediluvian is supposedly slain and diablerized by its own
  clan, under the leadership of Dragomir Basarab, Myca Vykos, and Lugoj — who is called
  "bloodbreaker" from then on. Lugoj declines to rule the clan and soon falls into torpor.
- **1420 CE** — The Anarchs begin to organize. In Eastern Europe they regularly perform
  the Vaulderie using a "fire flower" discovered in the Tzimisce founder's ruined castle.
- **1444 CE** — The Cappadocian antediluvian is slain and diablerized by Augustus Giovani.
  The Giovani clan begins hunting down and killing Cappadocians everywhere.
- **1453 CE** — Peasants revolt in Morea against rulers Thomas and Demetrius Palaiologos —
  one of many peasant movements across Europe in this period.

## Story Three: The Trojan Horse (1456-1458 CE)

- **1458 CE** — The Ottoman Turks invade and take control of the entire region. The
  [Ashirra](the-ashirra) arrive with them. The Parthenon Elysium is turned into a mosque,
  infuriating the native Greek Cainites.
""",
),
(
    'athens-cecropia',
    'Athens (Cecropia)',
    'Capital of the Duchy of Athens and seat of the Triumvirate — the vampires\' Elysium, "Cecropia," sits atop the Acropolis.',
    'locations',
    """Athens (modern Greek: *Athínai*, ancient Greek: *Athēnai*) is the capital of the Duchy
of Athens, a crusader state of the Latin Empire that replaced Byzantium after the Fourth
Crusade sacked nearby [Constantinople](constantinople) in 1204 CE. It sits under the
control of the Burgundian De La Roche family, whose official language is French. Under
Latin rule, several changes are made to the Orthodox church and the Parthenon becomes
the "Catholic Church of Saint Mary of Athens."

Athens sits atop a hill, giving it a wide view of the surrounding land — it has been
inhabited since before 3000 BCE, and some say antediluvians once walked its streets. The
founding legend of Athens, in which Poseidon and Athena compete to become the city's
patron, is read by some Cainites as an allegory for a political conflict between the
Tzimisce antediluvian and the Brujah founder. The Toreador, for their part, insist their
founder Arikel was the goddess Aphrodite and once dwelled in the city.

## Cecropia (the Acropolis)

The Cainites of Athens hold court at the Acropolis, which the vampires still call
**Cecropia**, as the ancient Athenians did — a reference to Cecrops, the mythological
snake-man first ruler of the city. By day the Acropolis is the mortal city's
administrative center; by night, holding court there puts the vampires in direct touch
with mortals in positions of power.

Elysium centers on the temple called **Erechtheion**, site of relics from Greek mythology
including the olive tree of Athena and the marks of Poseidon's trident. Like the Parthenon,
it is currently a Church dedicated to the mother of Jesus, though the elders remember the
gods and goddesses originally revered there.

Athenian Cainites take Elysium religiously — the Elysian Fields are a Greek concept akin
to the Christian Heaven. Attendance is usually reserved for domain-holders, recognized
ambassadors of other cities, and specially invited guests. Violence at Elysium is
considered blasphemous, not merely forbidden.

## The Agora

Below the Acropolis, the Brujah and members of less powerful clans who hold no domain
gather by night in the Agora to debate and discuss the city's politics. Previous attempts
to rabble-rouse here have made Elysium's regulars wary of these gatherings, but the
[Triumvirate](the-triumvirate-of-athens) sees them as a useful outlet for the frustrations
of the disaffected. Mortal law makes carrying a weapon in the Agora a major crime, which
helps keep the peace.
""",
),
(
    'delphi',
    'Delphi (Pytho)',
    'Site of the holiest oracle in Greece, contested by mystics, death cultists, and serpent-worshippers alike.',
    'locations',
    """Seventy-five miles northwest of Athens lies Delphi, called **Pytho** in ancient times
and by ancient Cainites still. It is the site of the holiest oracle in Greece, considered
sacred by nearly all supernatural groups in the region. The Malkavians, Cappadocians, and
Followers of Set are known to vie for power there, their respective mystery cults all
maintaining a presence. Those who have heard of the time-bound True Brujah say they meet
at the Oracle every few decades to receive prophecies.
""",
),
(
    'thessaloniki',
    'Thessaloniki',
    'The "second city" of Byzantium, mystically inclined and chafing under elder rule.',
    'locations',
    """Along the Aegean Sea to the north of Athens lies Thessaloniki, long considered the
"second city" of Byzantium. As of 1242 CE it is the capital of the short-lived Empire of
Thessalonica, a bustling city of over 150,000 people. At times in its history it will be
run more or less independently of whichever empire technically rules it.

The vampires here are mostly mystical Malkavians and Obertus Tzimisce, seeking
independence to study and meditate in peace under the oppressive rule of elder Toreador
and Ventrue. During the Anarch Revolt, those Malkavians and Tzimisce unite to overthrow
their rulers under cover of the violent mortal Zealot movement.
""",
),
(
    'thebes',
    'Thebes',
    'Silk-producing rival capital of the duchy with a long-standing Assamite presence.',
    'locations',
    """Northwest of Athens, the city of Thebes serves at different times as the capital of
the duchy. Thebes sided with Persia in 430 BCE and has had a significant Assamite
presence ever since. It has been a major producer of silk since the days of the Byzantine
Empire — at one point outproducing Constantinople itself — and several merchant Ventrue
call it home, doing quite well by evading politics wherever they can.
""",
),
(
    'constantinople',
    'Constantinople',
    'Seat of Lasombra power in the Latin Empire, ruled by Prince Alfonzo under the watch of the Inconnu.',
    'locations',
    """Far to the east, Constantinople is ruled by the Latins and the Lasombra Prince
**Alfonzo**, placed in power through the events of the Fourth Crusade and the
manipulations of the Inconnu — ancient vampires who now regret their part in it and seek
to correct their mistake. Alfonzo will not rule for long by Cainite standards. In the
meantime, the Lasombra as a clan enjoy their dominance of the region, with Alfonzo's
emissaries sent to the major cities of the Latin Empire to keep tabs on politics and tip
things in the clan of shadows' favor.
""",
),
(
    'the-triumvirate-of-athens',
    'The Triumvirate of Athens',
    'Three elected archons rule Athens in place of a single prince: Dionysius, Democritus, and Olympias.',
    'factions',
    """Rather than a single prince, Athens is ruled by a **Triumvirate** of elected archons,
voted upon by the domain-holding Cainites of the city — a practice that echoes the
Athenian overthrow of tyranny in the classical period.

The three current archons:

- **[Dionysius](dionysius)** — a Cappadocian ancient who stepped down from ruling as sole
  Tyrant some decades ago, now serving as the moderating swing vote between the other two.
- **[Democritus](democritus)** — a logic-bound Ventrue philosopher.
- **[Olympias](olympias)** — a mystical Malkavian who stands apart from her clan's
  internal factionalism.

The Triumvirate's decisions are made by majority, with Dionysius most often serving as
the deciding vote between Democritus's rationalism and Olympias's mysticism.
""",
),
(
    'the-ashirra',
    'The Ashirra',
    'A Muslim-oriented, democratically organized sect of vampires that arrives with the Ottoman conquest.',
    'factions',
    """The Ashirra is a Muslim-oriented sect of vampires, primarily led by a coalition of
pious Islamic Cainites, that arrives in Europe alongside the Ottoman Turks. At this point
in history, neither the Camarilla nor the Sabbat yet exist — the Ashirra is the first
public alliance of vampire clans the European Cainites have ever encountered, and it may
not be a coincidence that soon after its arrival, the Founders of the Camarilla begin
forming their own alliance.

The Ottoman Empire itself emerged as an Islamic state in late-13th-century Anatolia,
expanding through the Middle and Near East. After 1354 CE the Ottoman Turks cross into
Europe and conquer the Balkans, making their capital Adrianople in 1363 CE. During this
Chronicle they attack Constantinople several times before eventually taking and renaming
the city Istanbul.

The Ottomans conquer Athens in 1458 CE, at the very end of Book One. The Sultan himself is
said to have been struck by the beauty of the city's monuments and forbade their looting
and destruction under penalty of death — some vampires credit the spirit of Arikel, the
Toreador progenitor, with influencing that decision.

The saving grace for the Ashirra in Athens may be that they are a fundamentally democratic
sect, electing leaders and deciding major questions by vote — a practice the Athenian
Cainites already share, having overthrown tyranny of their own and taken to electing
archons instead.
""",
),
(
    'the-prometheans',
    'The Prometheans',
    'A conspiracy of Brujah revolutionaries who dream of restoring Carthage and ending elder rule.',
    'factions',
    """The Prometheans are a conspiracy of vampires who seek to restore Carthage, tear down
the tyranny of the Ventrue and Toreador across Europe, and ultimately end elder rule
altogether. They accumulate influence among mortal outsiders and criminals, and their
leadership is largely drawn from Greek and North African Brujah of significant age — the
rank and file, however, tend to be neonates.

Athenian Cainites who use the term "Archon" to describe an agent of the elders are echoing
Promethean usage — a slip of the tongue during the Convention of Thorns will one day cause
the nascent Camarilla to adopt the word as an official title.
""",
),
(
    'clans-and-bloodlines-of-greece',
    'Clans & Bloodlines of Greece',
    'Every clan present in Athens and the surrounding region, and the local "house" name Cainites use for each.',
    'clans',
    """Greek Cainites refer to each clan by a "House," tied to the Olympian god or myth
they most associate with its founder. What follows is what is generally known about each
clan's presence in the region.

## The Great Houses

### Assamites (Banu Haqim), the House of Ares

Many Assamites journeyed to Athens during Classical Greece — it is said Haqim himself
debated philosophy with Socrates and Aristotle, and a number of Vizier caste members were
embraced there and made the city their home. The clan's ties to the Ashirra sect connect
them to the Islamic states throughout history; in about two hundred years, when Greece
falls to the Ottoman Turks, the Banu Haqim will come with them. For now, the few members
in the region are Vizier caste poets and artisans, who find it wryly funny that others
call them the House of Ares — they are quite peaceful in this era.

### Brujah, the House of Athena

The clan of rebels has deep roots in Athens dating nearly to prehistory. Their original
clan founder is said to have been a philosopher, and the "philosopher kings" of the Brujah
take debate seriously. Split between the iconoclastic Furores and the conspiratorial
[Promethean](the-prometheans) faction, the clan will eventually become a major supporter
of the coming Anarch Movement. For many decades the most prominent local Brujah was the
philosopher Critias, until his sire Meneleus called him away — the clan has yet to find a
replacement leader.

### Cappadocians, the House of Dionysus

Led by the ancient cult figure [Dionysius](dionysius), the clan of death — later known as
the Hecata — is also the clan most associated with the Road of Humanity, making Athens a
center of human understanding among Cainites. Dionysius also serves on the
[Triumvirate](the-triumvirate-of-athens) after ruling alone as Tyrant for over a century.
The clan follows his lead, engaging with death cults while contemplating the nature of Man
and Beast.

### Gangrel, the House of Artemis

The Gangrel of Greece are known to outsiders as "Greek Gangrel," a bloodline that began in
Constantinople, replacing Fortitude with Obfuscate as an in-Clan Discipline for survival in
cities — the forebears of the future City Gangrel. They take Artemis as their patron and
are known to manifest bestial traits more mythical than animal, such as snakes for hair or
unicorn horns. Some say the Gangrel founder is one called Ennoia, who came to the region
hunting her rival Arikel after the fall of the Second City. The eldest Gangrel in Athens is
a huntress named Empusa, who has grown massive bat wings and holds a tentative
non-aggression pact with a tribe of werewolves with similarly anti-patriarchal interests.

### Lasombra, the House of Hades

The Lasombra have long held power in this part of the Mediterranean, where they seem to
have first arisen. A wanderer named Boukephos is said to have originated in Athens, and
most local Lasombra claim descent from him — he remains active in the world, and fear of
his wrath as a terror on the seas discourages action against Greek Lasombra. The clan also
rules the region through Prince Alfonzo of [Constantinople](constantinople). Locally, the
most powerful member is Theodora, a grandchilde of Boukephos and master socialite among
the Greek aristocracy.

### Malkavians, the House of Hera

The clan is split into factions in Greece. Its leader, the ancient [Olympias](olympias),
stands apart from the infighting. The rest belong to one of two cult-like factions
growing into bloodlines: the Jocastians, following a seer named Jocasta, and the
Mnemosyne, descended from a woman of the same name. The two groups — along with
Olympias — see themselves as motherly caretakers of Athens's Cainites, though none of
them actually dwell within the city walls.

### Nosferatu, the House of Hephaestus

The Nosferatu of Greece, like the Gangrel, are mostly members of an offshoot bloodline
called the **Larvae** — tunnel-dwellers able to eat stone and dirt, gnawing caves into
Athens's foundations. Considered monstrous elsewhere in the Balkans, the Larvae of Athens
are unusually intelligent and civilized for their bloodline. Their leader is a member of
the breed four times the size of any other, a bloated monster called Lemure.

### Ravnos, the House of Hermes

The least represented clan in Greece, though some members are known allies of
[Dionysius](dionysius). Revering Athens as the heart of the Road of Humanity, these
vagabonds follow the itinerant Path of Vigor, taking mortal tendencies toward travel,
music, and clever invention as models for their own behavior. Dionysius considers them
exemplary walkers on the Road, and the clan is welcome in Athens despite grumblings from
other clans — particularly the Ministry.

### Toreador, the House of Aphrodite

The Toreador contend their clan founder was Aphrodite herself, with extensive stories of
her arrival on Crete, where the clan became known as "bull dancers." The Athenian Toreador
descend from two lineages: the politically powerful line of Helena of Troy (through her
childe Eletria, and often called "harpies"), and the artistically obsessed line of the
painter Iontius (led in his absence by his childe Protogenes, a rival to Helena's line but
prone to torpor).

### Setite Ministry, the House of Demeter

Greece has a long history with Set, known here as **Typhon**, a many-headed snake said to
have defied Zeus (whom the Ministry claim was Ventrue). Infiltrating the region's mystery
cults, the Ministry secretly developed a Typhonic branch of their faith, drawing a direct
analogy between the twelve Olympian gods and the twelve Aeons Set is said to imprison. The
cult's leader is Nitocris, a methuselah worshipped by the Orphic cults as the goddess
Demeter — her politics are difficult, as the clan often intrudes on the cult interests of
the Cappadocians and Malkavians.

### Tremere, the House of Apollo

Conspicuously few Tremere operate in Greece given its proximity to the clan's Transylvanian
homeland — some say the Triumvirate keeps them out, though no explicit law forbids the
clan. A small chantry with three Tremere sits in [Thessaloniki](thessaloniki). Attica has
only one member, a Transylvanian sorceress named Danifa — unbeknownst even to her own
clan, she belongs to a pagan offshoot seeking to lift the Curse of Caine and return to
mortality.

### Tzimisce, the House of Poseidon

The Tzimisce clan founder embraced the dark priest Andeleon millennia ago; Andeleon went
on to join the secretive Black Hand. His descendants still haunt Greece, performing
experiments related to a discovery he called "Atlantis," making trips into the
Shadowlands on the Black Hand's behalf. Their power base is control of the Greek Orthodox
church via the Obertus revenant family — though under current Latin rule of
Constantinople, the Catholic church holds authority instead, and the Tzimisce work to
overthrow the Latins and their allied clans (the Toreador, Lasombra, and Cappadocians).
The Tzimisce leader in Athens, Ilias, was once a farmer whose brain injury left him able
to speak the language of Enoch — some say he channels a methuselah, a demon, or the
Discipline of Vicissitude itself.

### Ventrue, the House of Zeus

The Ventrue of Greece descend from Ventrue's favorite childe, Artemis Orthia. Those who
stayed in Greece rather than following her to Rome are more philosophical than political,
endlessly debating the perfect form of government — a debate that makes them strict
enemies of the Brujah, whom they see as dreamers and fools. Chief among them is
[Democritus](democritus), who currently serves as Primogen for the Ventrue of all Greece,
with seven "stratagoi" serving under him as Ventrue lords of the various Greek cities.

## The Minor Houses

### Giovani, the House of Porphyrion

A Cappadocian bloodline that benefited from Venice's role in sacking Constantinople in
1204 CE, exerting increasing control over Venetian affairs. They find themselves an
unwilling rival to the Greek Tzimisce, who resent their Latin ties and control over
necromancy, without understanding why — elsewhere the Tzimisce have no interest in
ghosts at all.

### Lamiae, the House of Lamia

A warrior bloodline that serves as protectors and keepers of Lilin wisdom for the Greek
Cappadocians, based out of an underground citadel beneath Lamia Castle in the city of
Zetounion. As fellow wise women, they maintain strong, clandestine ties to the Witches of
Echidna, trading lore of the Dark Mother even as the Cappadocians and Setite Ministry
otherwise contest control of the region's Orphic mystery cults.
""",
),
(
    'dionysius',
    'Dionysius',
    'Cappadocian ancient, former sole Tyrant of Athens, and the moderating swing vote of the Triumvirate.',
    'characters',
    """Dionysius is an ancient cult figure of clan Cappadocian who now sits as one of the
elected members of the [Triumvirate of Athens](the-triumvirate-of-athens), having stepped
down from ruling alone as Tyrant some decades ago. He acts as the moderating figure
between the logic-bound Ventrue [Democritus](democritus) and the mystical Malkavian
[Olympias](olympias), and so serves as the swing vote in many of the city's major
decisions.

Dionysius sits at the leading edge of the Road of Humanity, making Athens a center of
human understanding among Cainites. He considers the Ravnos of Athens exemplary walkers
of that Road, and some of the clan count themselves among his known allies.
""",
),
(
    'democritus',
    'Democritus',
    'Ventrue philosopher-archon whose ideas on logic and alliance will one day help inspire the Camarilla.',
    'characters',
    """Democritus is a Ventrue philosopher who has made logic and rationality the focus of
his existence, and who currently serves both on the [Triumvirate of Athens](the-triumvirate-of-athens)
and as Primogen for the Ventrue of all Greece, with seven "stratagoi" serving under him as
Ventrue lords of the region's cities.

His influence on the powerful German elder Hardestadt will eventually help lead to the
formation of the Camarilla, drawing inspiration from the ancient Delian League.
""",
),
(
    'olympias',
    'Olympias',
    'Ancient, mystically-inclined Malkavian archon who stands apart from her clan\'s internal factions.',
    'characters',
    """Olympias is an ancient Malkavian who sits on the [Triumvirate of Athens](the-triumvirate-of-athens)
as its mystically-inclined member, balanced against the cold logic of
[Democritus](democritus) and moderated by [Dionysius](dionysius).

The Malkavian clan in Greece is split between two cult-like factions growing into
bloodlines — the Jocastians and the Mnemosyne — but Olympias stands apart from their
infighting. Along with the leaders of those two factions, she is seen by many as one of
the motherly caretakers of Athens's Cainites, though, like them, she does not dwell within
the city walls itself.
""",
),
]


def main() -> None:
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('libsql://') or db_url.startswith('https://'):
        _run_turso(db_url)
    else:
        _run_sqlite()


def _get_or_create_campaign_sqlite(conn):
    row = conn.execute('SELECT id FROM campaigns WHERE slug = ?', (CAMPAIGN_SLUG,)).fetchone()
    if row:
        return row['id']
    cur = conn.execute(
        """INSERT INTO campaigns (slug, name, system, status, description, wiki_categories,
                                   wiki_enabled, sort_order, created_at, updated_at)
           VALUES (?, ?, ?, 'draft', ?, ?, 1, 0, datetime('now'), datetime('now'))""",
        (CAMPAIGN_SLUG, CAMPAIGN_NAME, CAMPAIGN_SYSTEM, CAMPAIGN_DESCRIPTION,
         json.dumps(WIKI_CATEGORIES)),
    )
    return cur.lastrowid


def _run_sqlite() -> None:
    import sqlite3

    db_path = Path(__file__).parent.parent / 'data' / 'db.sqlite'
    if not db_path.exists():
        print(f'DB not found at {db_path}')
        sys.exit(1)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        campaign_id = _get_or_create_campaign_sqlite(conn)
        _upsert_pages_sqlite(conn, campaign_id)
    print('\nDone (sqlite).')


def _upsert_pages_sqlite(conn, campaign_id) -> None:
    for slug, title, summary, category, body in PAGES:
        row = conn.execute(
            'SELECT id FROM wiki_pages WHERE campaign_id = ? AND slug = ?',
            (campaign_id, slug),
        ).fetchone()
        if row:
            conn.execute(
                """UPDATE wiki_pages SET title=?, summary=?, category=?, body_markdown=?,
                       status='active', source='manual', updated_at=datetime('now')
                   WHERE id=?""",
                (title, summary, category, body, row['id']),
            )
            print(f'  updated: {slug}')
        else:
            conn.execute(
                """INSERT INTO wiki_pages (campaign_id, slug, title, summary, body_markdown,
                       category, status, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'active', 'manual', datetime('now'), datetime('now'))""",
                (campaign_id, slug, title, summary, body, category),
            )
            print(f'  created: {slug}')


def _run_turso(db_url: str) -> None:
    token = os.environ.get('TURSO_AUTH_TOKEN', '')
    connect_url = 'https://' + db_url[len('libsql://'):] if db_url.startswith('libsql://') else db_url

    sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))
    from turso_http import connect

    conn = connect(connect_url, auth_token=token)
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM campaigns WHERE slug = ?', (CAMPAIGN_SLUG,))
    row = cursor.fetchone()
    if row:
        campaign_id = row[0]
        print(f'Campaign "{CAMPAIGN_SLUG}" already exists (id={campaign_id}); reusing it.')
    else:
        cursor.execute(
            """INSERT INTO campaigns (slug, name, system, status, description, wiki_categories,
                                       wiki_enabled, sort_order, created_at, updated_at)
               VALUES (?, ?, ?, 'draft', ?, ?, 1, 0, datetime('now'), datetime('now'))""",
            (CAMPAIGN_SLUG, CAMPAIGN_NAME, CAMPAIGN_SYSTEM, CAMPAIGN_DESCRIPTION,
             json.dumps(WIKI_CATEGORIES)),
        )
        cursor.execute('SELECT id FROM campaigns WHERE slug = ?', (CAMPAIGN_SLUG,))
        campaign_id = cursor.fetchone()[0]
        print(f'Created campaign "{CAMPAIGN_SLUG}" (id={campaign_id}).')

    for slug, title, summary, category, body in PAGES:
        cursor.execute(
            'SELECT id FROM wiki_pages WHERE campaign_id = ? AND slug = ?',
            (campaign_id, slug),
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                """UPDATE wiki_pages SET title=?, summary=?, category=?, body_markdown=?,
                       status='active', source='manual', updated_at=datetime('now')
                   WHERE id=?""",
                (title, summary, category, body, existing[0]),
            )
            print(f'  updated: {slug}')
        else:
            cursor.execute(
                """INSERT INTO wiki_pages (campaign_id, slug, title, summary, body_markdown,
                       category, status, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'active', 'manual', datetime('now'), datetime('now'))""",
                (campaign_id, slug, title, summary, body, category),
            )
            print(f'  created: {slug}')

    conn.commit()
    print(f'\nDone. {len(PAGES)} page(s) processed for campaign "{CAMPAIGN_SLUG}".')


if __name__ == '__main__':
    main()
