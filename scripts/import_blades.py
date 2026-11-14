#!/usr/bin/env python3
"""Seed the Blades campaign. Default is an offline, write-free fixture preview.

    python scripts/import_blades.py
    python scripts/import_blades.py --apply

--apply uses the portal's normal DATABASE_URL (local SQLite when unset).
Existing pages and campaign settings are preserved. --refresh explicitly replaces
only pages previously owned by this importer; hand-created slug collisions fail.
Use the same flag to update imported content after re-exporting its source.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.blades_campaign import load_payload, seed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    payload = load_payload()
    print(f'{payload["campaign"]["name"]}: {len(payload["pages"])} pages')
    for page in payload['pages']:
        print(f'  {page["status"]:6} {page["slug"]}')
    if not args.apply:
        print('Preview only; no database opened. Use --apply to seed the configured database.')
        return
    from app import create_app
    app = create_app()
    with app.app_context():
        seed(payload, refresh=args.refresh)
    print('Campaign available at /blades/wiki/; atlas at /blades/atlas/.')


if __name__ == '__main__':
    main()
