#!/usr/bin/env python3
"""Read-only by default Notion -> gaming-portal wiki reconciliation.

Run inside gaming-portal with configured database and NOTION_TOKEN:
  python scripts/sync_notion_wiki.py
  python scripts/sync_notion_wiki.py --apply

Only explicitly public, approved Factions and Lore are imported. Other entries
are withheld; previously imported ones are hidden. Manual pages are preserved.
"""
import argparse
import os
import re
import unicodedata

import requests

from app import create_app
from app.db import Campaign, WikiPage, db

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
CATEGORIES = ("factions", "lore")
PUBLIC_VISIBILITY = {"players", "public"}
TRUE = {True, "__YES__", "true", "yes", "1"}
PUBLIC_STATUSES = {"active"}
TITLE_FIELDS = ("Name", "Scene Name", "Title")


def notion_request(method, path, **kwargs):
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN is required")
    response = requests.request(method, NOTION_API + path, timeout=30,
                                headers={"Authorization": "Bearer " + token,
                                         "Notion-Version": NOTION_VERSION},
                                **kwargs)
    response.raise_for_status()
    return response.json()


def all_rows(database_id):
    cursor = None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        response = notion_request("POST", "/databases/" + database_id + "/query",
                                  json=payload)
        yield from response.get("results", [])
        if not response.get("has_more"):
            break
        cursor = response["next_cursor"]


def property_text(prop):
    if not prop:
        return ""
    kind = prop.get("type")
    value = prop.get(kind) if kind else None
    if kind in ("title", "rich_text"):
        return "".join(part.get("plain_text", "") for part in (value or []))
    if kind in ("select", "status"):
        return (value or {}).get("name", "")
    if kind == "checkbox":
        return value
    if kind == "formula" and isinstance(value, dict):
        return value.get(value.get("type"))
    return ""


def public_approval(properties):
    visibility = str(property_text(properties.get("Visibility"))).strip().lower()
    visible = property_text(properties.get("Visible"))
    status = str(property_text(properties.get("Status"))).strip().lower()
    return (visibility in PUBLIC_VISIBILITY
            and visible in TRUE
            and status in PUBLIC_STATUSES)


def title_for(properties):
    for name in TITLE_FIELDS:
        title = property_text(properties.get(name))
        if title:
            return title
    return ""


def slugify(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")[:190]


def rich_text(items):
    return "".join(part.get("plain_text", "") for part in items or [])


def list_blocks(block_id):
    cursor = None
    while True:
        path = "/blocks/" + block_id + "/children?page_size=100"
        if cursor:
            path += "&start_cursor=" + cursor
        result = notion_request("GET", path)
        yield from result.get("results", [])
        if not result.get("has_more"):
            break
        cursor = result["next_cursor"]


def markdown_blocks(block_id):
    lines = []
    for block in list_blocks(block_id):
        kind = block.get("type")
        data = block.get(kind, {})
        if kind in {"child_page", "child_database", "link_to_page", "synced_block",
                    "embed", "bookmark", "file", "pdf", "video", "audio"}:
            # No traversing links to private pages, unknown embeds, or synced blocks.
            continue
        if kind == "image":
            image = data.get(data.get("type"), {})
            url = image.get("url", "")
            # Signed Notion file URLs expire, so never copy them into public pages.
            if data.get("type") == "external" and url.startswith("https://"):
                lines.append("![](" + url + ")")
            continue
        content = rich_text(data.get("rich_text", []))
        if kind in {"heading_1", "heading_2", "heading_3"}:
            lines.append("#" * int(kind[-1]) + " " + content)
        elif kind == "bulleted_list_item":
            lines.append("- " + content)
        elif kind == "numbered_list_item":
            lines.append("1. " + content)
        elif kind == "quote":
            lines.append("> " + content)
        elif kind in {"paragraph", "callout", "toggle"} and content:
            lines.append(content)
        elif kind == "divider":
            lines.append("---")
        elif kind == "code":
            language = data.get("language", "")
            lines.append("```" + language + "\n" + content + "\n```")
        if block.get("has_children") and kind in {"bulleted_list_item",
                                                   "numbered_list_item", "quote"}:
            lines.extend(markdown_blocks(block["id"]).splitlines())
    return "\n\n".join(lines).strip()


def plan(session, campaign, records):
    """Return deterministic actions without mutating any records."""
    existing = WikiPage.query.filter_by(campaign_id=campaign.id).all()
    by_id = {str(p.notion_page_id).replace("-", ""): p for p in existing
             if p.notion_page_id}
    by_slug = {p.slug: p for p in existing}
    actions = []
    observed = set()
    for category, row in sorted(records, key=lambda item: item[1]["id"]):
        notion_id = row["id"].replace("-", "")
        observed.add(notion_id)
        props = row.get("properties", {})
        approved = public_approval(props) and not row.get("archived") and not row.get("in_trash")
        match = by_id.get(notion_id)
        if not approved:
            if match and match.source == "notion" and match.status != "draft":
                actions.append(("hide", category, row, match))
            else:
                actions.append(("withheld", category, row, match))
            continue
        title = title_for(props)
        if not title:
            actions.append(("invalid-title", category, row, match))
            continue
        slug = slugify(title)
        if not match and slug in by_slug:
            candidate = by_slug[slug]
            # Only adopt *empty* automatically seeded placeholders.
            if candidate.source == "manual" and not (candidate.body_markdown or "").strip() and candidate.status == "upcoming":
                match = candidate
            else:
                actions.append(("collision", category, row, candidate))
                continue
        actions.append(("upsert", category, row, match))
    # An absent API record is not proof of deletion. Do not hide it automatically.
    return actions


def run(apply=False):
    app = create_app()
    with app.app_context():
        campaign = Campaign.query.filter_by(slug="dcbn").first()
        if not campaign:
            raise RuntimeError("DC by Night campaign does not exist")
        databases = campaign.notion_databases
        for cat in CATEGORIES:
            if not databases.get(cat):
                raise RuntimeError("Missing Notion mapping for " + cat)
        records = [(cat, row) for cat in CATEGORIES
                   for row in all_rows(databases[cat])]
        actions = plan(db.session, campaign, records)
        changed = 0
        for action, category, row, match in actions:
            notion_id = row["id"]
            if action != "upsert":
                print(action.upper(), category, notion_id)
                if apply and action == "hide":
                    match.status = "draft"
                    changed += 1
                continue
            title = title_for(row["properties"])
            body = markdown_blocks(notion_id) if apply else ""
            if not apply:
                print("UPSERT (dry run)", category, title, notion_id)
                continue
            if match is None:
                match = WikiPage(campaign_id=campaign.id,
                                 slug=slugify(title), category=category)
                db.session.add(match)
            if (match.source not in ("notion", "manual")) or (
                match.source == "manual" and (match.body_markdown or "").strip()):
                print("SKIP OWNED", title)
                continue
            match.title = title
            match.summary = str(property_text(row["properties"].get("Summary")))[:500]
            match.body_markdown = body
            match.status = "active"
            match.source = "notion"
            match.notion_page_id = notion_id
            match.updated_by = "notion-safe-sync"
            changed += 1
        if apply:
            db.session.commit()
        print("Done:", len(actions), "decisions,", changed, "writes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Write eligible changes (default: read-only)")
    run(parser.parse_args().apply)
