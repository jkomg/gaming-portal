# Quiet Orbit starter

Standalone Scum and Villainy campaign at `/sav/wiki/`, alongside the existing Ghosts of the Wayline entry. The startup seed creates missing pages and preserves existing edits. Three GM pages are drafts, visible only to staff. Published rulebooks and sheet PDFs are not distributed by this repository.

Start with [the overview](campaign/start-here.md), [the job](campaign/a-breathing-cargo.md), [GM preparation](campaign/gm-a-breathing-cargo.md), and [Deep Cuts compatibility](campaign/deep-cuts-compatibility.md). The six pregens include the unique starting ability plus a special ability. Core S&V remains the first-session ruleset; playtest modules are inactive proposals.

Author Markdown in `content/sav/campaign/`; `scripts/fixtures/sav_campaign.json` is the runtime fixture. Regenerate it with `python scripts/export_sav.py`. The optional `python scripts/build_sav_pregens.py` regenerates pregen Markdown and structured `pregens.json`; edit that generator before regenerating characters.

`python scripts/import_sav.py` previews without opening a database. `--apply` seeds the configured database. `--apply --refresh` explicitly replaces importer-owned pages, rejecting manual slug collisions transactionally. App startup seeds missing content only; it does not overwrite edited wiki bodies. No migrations or deployment are required just to preview the fixture.

The atlas at `/sav/atlas/` is an original interactive route schematic backed by player-safe `app/static/sav/sites.json`. It is not a canonical sector map. Image provenance and hashes are in `app/static/sav/manifest.json`; full credit is in the wiki and the atlas footer. Asset ownership and license differ between the Webb image and the supplied sketch portraits.

Core references: supplied S&V book and sheets; Deep Cuts v1.1 pp. 73–107 and design notes pp. 116–118. See `art-and-credits.md` for source filenames and pagination. No table trial of the conversion has been run. Any numerical prices/rulings added for the adaptation are identified as proposals.
