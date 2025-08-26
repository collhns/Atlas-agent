""" Atlas Notion Read/Write Bootstrap — Python

Goal: Guarantee reliable READ/WRITE to your Notion HQ first, then layer full Agent capabilities.

What this script does (scalable foundation):

1. Connects to Notion via an Internal Integration token (env-driven; no secrets in code).


2. Resolves/creates the core pages you specified:

ATLAS NOTION

RUBY NOTION

HOC Access



3. Ensures the Change Log database exists under HOC Access / Change Log with the exact schema.


4. Upserts a v3.1 entry into Change Log (idempotent by Version).


5. Ensures an “Atlas Persistent Memory” database exists and appends a log of this bootstrap run.



Extendable: Add tools/steps as functions without breaking the public interface.

Usage

1. pip install -U notion-client python-dotenv rich


2. Create a Notion Internal Integration: https://www.notion.so/my-integrations

Name: Atlas Write Agent (recommended)

Copy the Internal Integration Token



3. In Notion, Share the following pages with your integration (Full access):

ATLAS NOTION

RUBY NOTION

HOC Access



4. Create a .env file next to this script with: NOTION_TOKEN=secret_xxx_from_integrations ROOT_TEAMSPACE="Kola Adeola’s Notion HQ"  # optional hint used in search OWNER_NAME=Collins


5. Run bootstrap: python atlas_notion_bootstrap.py bootstrap --v 3.1 --date 2025-08-26 --author "Ruby + Collins" 
--summary "Added Atlas Identity Core and Atlas Instruction under ATLAS NOTION. Formalized Atlas’ role in HOC Team (2.3) as Archivist & Auditor + Backup Commander. Established Atlas as a triad peer." 
--linked "Section 2.3; Section 8.4; ATLAS NOTION" --status Active



NOTE: The script uses safe idempotent upserts and writes a rich audit trail to Atlas Persistent Memory. """ from future import annotations import os import sys import time import argparse from dataclasses import dataclass from typing import Any, Dict, List, Optional

from dotenv import load_dotenv from rich import print from rich.console import Console from rich.table import Table

try: from notion_client import Client from notion_client.helpers import iterate_paginated_api except Exception as e: print("[red]Missing dependency:[/red] notion-client. Install with pip install notion-client.\n", e) sys.exit(1)

console = Console()

------------------------- Config & Constants -------------------------

CHANGE_LOG_NAME = "Change Log" PERSISTENT_MEMORY_NAME = "Atlas Persistent Memory" ATLAS_NOTION = "ATLAS NOTION" RUBY_NOTION = "RUBY NOTION" HOC_ACCESS = "HOC Access"

CHANGE_LOG_SCHEMA = { "Version": {"name": "Version", "type": "title"}, "Date": {"name": "Date", "type": "date"}, "Author": {"name": "Author", "type": "rich_text"}, "Change Summary": {"name": "Change Summary", "type": "rich_text"}, "Linked Sections": {"name": "Linked Sections", "type": "rich_text"}, "Status": { "name": "Status", "type": "select", "select": {"options": [ {"name": "Proposed", "color": "yellow"}, {"name": "Active", "color": "green"}, {"name": "Archived", "color": "gray"}, ]}, }, }

MEMORY_SCHEMA = { "Timestamp": {"name": "Timestamp", "type": "date"}, "Actor": {"name": "Actor", "type": "rich_text"}, "Event": {"name": "Event", "type": "title"}, "Details": {"name": "Details", "type": "rich_text"}, "Tags": {"name": "Tags", "type": "multi_select"}, }

------------------------- Helpers -------------------------

def env(name: str, default: Optional[str] = None) -> str: val = os.getenv(name, default) if val is None: raise RuntimeError(f"Missing required env var: {name}") return val

def notion_client() -> Client: token = env("NOTION_TOKEN") return Client(auth=token)

def search_one_page_by_title(notion: Client, title: str) -> Optional[Dict[str, Any]]: query = title results = notion.search(query=query, filter={"value": "page", "property": "object"}).get("results", []) for r in results: # Strong title match check try: rich_title = r["properties"]["title"]["title"][0]["plain_text"].strip() if rich_title.lower() == title.lower(): return r except Exception: pass return None

def ensure_page(notion: Client, title: str, parent_page_id: Optional[str] = None) -> Dict[str, Any]: existing = search_one_page_by_title(notion, title) if existing: return existing parent = {"type": "page_id", "page_id": parent_page_id} if parent_page_id else {"type": "workspace"} created = notion.pages.create( parent=parent, properties={"title": {"title": [{"type": "text", "text": {"content": title}}]}}, ) return created

def ensure_database(notion: Client, db_name: str, parent_page_id: str, schema: Dict[str, Any]) -> Dict[str, Any]: # Try to find by search (Notion doesn't have strict lookups by title) results = notion.search(query=db_name, filter={"value": "database", "property": "object"}).get("results", []) for r in results: try: rich_title = r["title"][0]["plain_text"].strip() if rich_title.lower() == db_name.lower(): return r except Exception: pass # Create if not found db = notion.databases.create( parent={"type": "page_id", "page_id": parent_page_id}, title=[{"type": "text", "text": {"content": db_name}}], properties=schema, ) return db

def get_page_title(page: Dict[str, Any]) -> str: try: return page["properties"]["title"]["title"][0]["plain_text"] except Exception: return "(untitled)"

------------------------- Change Log Upsert -------------------------

def find_db_by_exact_title(notion: Client, title: str) -> Optional[Dict[str, Any]]: res = notion.search(query=title, filter={"value": "database", "property": "object"}).get("results", []) for db in res: try: t = db["title"][0]["plain_text"].strip() if t.lower() == title.lower(): return db except Exception: pass return None

def ensure_change_log(notion: Client, hoc_access_page_id: str) -> Dict[str, Any]: db = find_db_by_exact_title(notion, CHANGE_LOG_NAME) if db: return db return ensure_database(notion, CHANGE_LOG_NAME, hoc_access_page_id, CHANGE_LOG_SCHEMA)

def rich_text(text: str) -> List[Dict[str, Any]]: return [{"type": "text", "text": {"content": text}}]

def select_value(name: str) -> Dict[str, Any]: return {"name": name}

def upsert_change_entry( notion: Client, db_id: str, version: str, date_iso: str, author: str, summary: str, linked_sections: str, status: str = "Active", ) -> Dict[str, Any]: # Search existing by Version query = { "filter": { "and": [ {"property": "Version", "title": {"equals": version}}, ] } } pages = notion.databases.query(database_id=db_id, **query).get("results", []) props = { "Version": {"title": [{"type": "text", "text": {"content": version}}]}, "Date": {"date": {"start": date_iso}}, "Author": {"rich_text": rich_text(author)}, "Change Summary": {"rich_text": rich_text(summary)}, "Linked Sections": {"rich_text": rich_text(linked_sections)}, "Status": {"select": select_value(status)}, } if pages: page_id = pages[0]["id"] return notion.pages.update(page_id=page_id, properties=props) else: return notion.pages.create(parent={"type": "database_id", "database_id": db_id}, properties=props)

------------------------- Persistent Memory -------------------------

def ensure_persistent_memory(notion: Client, atlas_page_id: str) -> Dict[str, Any]: db = find_db_by_exact_title(notion, PERSISTENT_MEMORY_NAME) if db: return db return ensure_database(notion, PERSISTENT_MEMORY_NAME, atlas_page_id, MEMORY_SCHEMA)

def append_memory(notion: Client, db_id: str, actor: str, event: str, details: str, tags: List[str]) -> Dict[str, Any]: props = { "Timestamp": {"date": {"start": time.strftime("%Y-%m-%dT%H:%M:%S")}}, "Actor": {"rich_text": rich_text(actor)}, "Event": {"title": [{"type": "text", "text": {"content": event}}]}, "Details": {"rich_text": rich_text(details)}, "Tags": {"multi_select": [{"name": t} for t in tags]}, } return notion.pages.create(parent={"type": "database_id", "database_id": db_id}, properties=props)

------------------------- Bootstrap Flow -------------------------

def bootstrap(args) -> None: notion = notion_client()

# 1) Ensure core top-level pages exist (idempotent)
atlas_page = ensure_page(notion, ATLAS_NOTION)
ruby_page = ensure_page(notion, RUBY_NOTION)
hoc_page = ensure_page(notion, HOC_ACCESS)

atlas_id = atlas_page["id"]
hoc_id = hoc_page["id"]

# 2) Ensure Change Log DB under HOC Access
change_log_db = ensure_change_log(notion, hoc_id)

# 3) Upsert v3.1 entry
if args.version:
    upsert_change_entry(
        notion,
        change_log_db["id"],
        version=args.version,
        date_iso=args.date,
        author=args.author,
        summary=args.summary,
        linked_sections=args.linked,
        status=args.status,
    )

# 4) Ensure Persistent Memory DB under ATLAS NOTION and append log
memory_db = ensure_persistent_memory(notion, atlas_id)
owner = os.getenv("OWNER_NAME", "Owner")
append_memory(
    notion,
    memory_db["id"],
    actor="Atlas",
    event="Bootstrap Completed",
    details=f"Initialized RW foundation; ensured Change Log and Persistent Memory; upserted v{args.version}.",
    tags=["bootstrap", "change-log", "atlas"],
)

# 5) Pretty print summary
table = Table(title="Atlas Notion RW Bootstrap — Summary")
table.add_column("Item", style="cyan", no_wrap=True)
table.add_column("Value", style="white")

table.add_row("ATLAS NOTION Page", get_page_title(atlas_page))
table.add_row("RUBY NOTION Page", get_page_title(ruby_page))
table.add_row("HOC Access Page", get_page_title(hoc_page))
table.add_row("Change Log DB", change_log_db["id"]) 
table.add_row("Persistent Memory DB", memory_db["id"]) 
console.print(table)

------------------------- CLI -------------------------

def build_parser() -> argparse.ArgumentParser: p = argparse.ArgumentParser(description="Atlas Notion Read/Write Bootstrap") sub = p.add_subparsers(dest="command", required=True)

b = sub.add_parser("bootstrap", help="Ensure pages, Change Log DB, Persistent Memory DB, and upsert a change entry")
b.add_argument("--version", "--v", dest="version", required=True, help="Change Log version tag, e.g., 3.1")
b.add_argument("--date", dest="date", required=True, help="ISO date, e.g., 2025-08-26")
b.add_argument("--author", dest="author", required=True, help="Author text, e.g., 'Ruby + Collins'")
b.add_argument("--summary", dest="summary", required=True, help="Short change description")
b.add_argument("--linked", dest="linked", required=True, help="Linked sections text")
b.add_argument("--status", dest="status", default="Active", choices=["Proposed", "Active", "Archived"], help="Change status")
b.set_defaults(func=bootstrap)

return p

def main(): load_dotenv() parser = build_parser() args = parser.parse_args() args.func(args)

if name == "main": main()

