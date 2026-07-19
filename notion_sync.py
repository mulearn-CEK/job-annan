"""
Notion Sync
-----------
Reads jobs.json (produced by main.py) and upserts each job into a Notion
database, skipping jobs that are already there (matched by the hidden
"Job ID" property) so daily runs don't create duplicates.

Existing Job IDs are fetched up front with one paginated query (100 rows per
request) instead of one query per job — far fewer API calls and no per-job
rate-limit pressure. All requests have timeouts and retry on 429/5xx with
backoff, and the script exits non-zero if any page failed to create, so the
GitHub Action shows red instead of silently succeeding.

Required environment variables:
    NOTION_TOKEN       - the "Internal Integration Secret" from your integration
    NOTION_DATABASE_ID - the 32-char database ID from your database's URL

Usage:
    python notion_sync.py
"""

import os
import json
import sys
import time
from pathlib import Path
import requests

from scrapers.details import fetch_details

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
NOTION_VERSION = "2022-06-28"
JOBS_FILE = Path(__file__).parent / "jobs.json"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 5

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


def check_env():
    missing = [k for k in ("NOTION_TOKEN", "NOTION_DATABASE_ID") if not os.environ.get(k)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)


def notion_post(url: str, payload: dict) -> requests.Response:
    """POST with timeout, retrying on 429 (honoring Retry-After), 5xx, and
    network errors (timeouts, connection resets)."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, headers=HEADERS, json=payload, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                raise
            print(f"Network error talking to Notion ({e}), retrying...")
            time.sleep(2 ** attempt)
            continue
        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After", 2 ** attempt))
            print(f"Rate limited by Notion, waiting {wait:.1f}s...")
            time.sleep(wait)
            continue
        if resp.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        return resp
    return resp  # last attempt's response, let the caller report it


def fetch_existing_job_ids() -> set[str]:
    """One paginated query over the whole database → set of known Job IDs."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    job_ids = set()
    payload = {"page_size": 100}
    while True:
        resp = notion_post(url, payload)
        resp.raise_for_status()
        data = resp.json()
        for page in data.get("results", []):
            rich = page.get("properties", {}).get("Job ID", {}).get("rich_text", [])
            if rich:
                job_ids.add(rich[0].get("plain_text", ""))
        if not data.get("has_more"):
            return job_ids
        payload["start_cursor"] = data["next_cursor"]


def sections_to_blocks(sections: list) -> list[dict]:
    """Convert (kind, text) tuples from fetch_details into Notion blocks.
    Notion caps: 100 blocks per request, 2000 chars per rich_text."""
    blocks = []
    for kind, text in sections:
        block_type = "heading_2" if kind == "heading" else "paragraph"
        for i in range(0, len(text), 2000):
            blocks.append({
                "object": "block",
                "type": block_type,
                block_type: {"rich_text": [{"text": {"content": text[i:i + 2000]}}]},
            })
        if len(blocks) >= 95:
            break
    return blocks[:95]


def create_page(job: dict) -> bool:
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Job Title": {"title": [{"text": {"content": job["title"][:2000]}}]},
            "Company": {"rich_text": [{"text": {"content": job.get("company", "")[:2000]}}]},
            "Location": {"rich_text": [{"text": {"content": job.get("location", "")[:2000]}}]},
            "Posted Date": {"rich_text": [{"text": {"content": job.get("posted_date", "")[:2000]}}]},
            "Deadline": {"rich_text": [{"text": {"content": job.get("deadline", "")[:2000]}}]},
            "Description": {"rich_text": [{"text": {"content": job.get("description", "")[:2000]}}]},
            "Job ID": {"rich_text": [{"text": {"content": job["job_id"]}}]},
            "IT Park": {"select": {"name": job.get("it_park", "Other")}},
            "Role Type": {"select": {"name": job.get("role_type", "Other")}},
            "Status": {"select": {"name": "New"}},
        },
    }
    if job.get("apply_link"):
        payload["properties"]["Apply Link"] = {"url": job["apply_link"]}

    # Deep-fetch the full posting from the job's detail page → page body.
    blocks = sections_to_blocks(fetch_details(job))
    if blocks:
        payload["children"] = blocks

    resp = notion_post(url, payload)
    if resp.status_code >= 300:
        print(f"Failed to create page for '{job['title']}': {resp.status_code} {resp.text}")
        return False
    return True


def main():
    check_env()

    if not JOBS_FILE.exists():
        print(f"{JOBS_FILE} not found. Run main.py first.")
        sys.exit(1)

    jobs = json.loads(JOBS_FILE.read_text())
    print(f"Loaded {len(jobs)} jobs from {JOBS_FILE}")

    try:
        existing = fetch_existing_job_ids()
    except requests.RequestException as e:
        print(f"Could not fetch existing Job IDs from Notion: {e}")
        sys.exit(1)
    print(f"Found {len(existing)} jobs already in Notion")

    added, skipped, failed = 0, 0, 0

    for job in jobs:
        if job["job_id"] in existing:
            skipped += 1
            continue
        try:
            if create_page(job):
                added += 1
            else:
                failed += 1
        except requests.RequestException as e:
            print(f"Request error for '{job.get('title')}': {e}")
            failed += 1
        time.sleep(0.35)  # stay comfortably under Notion's ~3 req/s limit

    print(f"\nDone. Added: {added}, Skipped (already in Notion): {skipped}, Failed: {failed}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
