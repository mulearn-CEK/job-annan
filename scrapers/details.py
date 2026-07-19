"""
Job detail fetchers — one per IT Park.

Given a job dict (as produced by the scrapers), fetch_details() returns the
full posting as a list of (kind, text) tuples, where kind is "heading" or
"paragraph". notion_sync.py converts these into Notion blocks for the job's
page body. All three sites serve details without JavaScript:

- Technopark: the job-details page is Inertia.js — the full posting (HTML
  description, skills, contact email) is embedded as JSON in #app[data-page].
- Infopark: server-rendered page; content lives in div.deatil-box (their typo).
- Cyberpark: normal WordPress post; content lives in div.job_description.

Failures return [] — the job page is still created, just without a body.
"""

import re
import json
import html as html_mod
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
}
TIMEOUT = 30

_session = requests.Session()
_session.headers.update(HEADERS)


def _html_to_sections(html: str) -> list[tuple[str, str]]:
    """Flatten an HTML fragment into (kind, text) tuples, keeping list items."""
    out = []
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            out.append(("heading", text))
        elif el.name == "li":
            out.append(("paragraph", f"• {text}"))
        else:
            out.append(("paragraph", text))
    if not out:  # fragment had no block tags, just text
        text = soup.get_text(" ", strip=True)
        if text:
            out.append(("paragraph", text))
    return out


def _technopark(job: dict) -> list[tuple[str, str]]:
    resp = _session.get(job["apply_link"], timeout=TIMEOUT)
    resp.raise_for_status()
    m = re.search(r'data-page="([^"]*)"', resp.text)
    if not m:
        return []
    props = json.loads(html_mod.unescape(m.group(1))).get("props", {})
    listing = props.get("jobListing") or {}
    sections = []
    if listing.get("job_description"):
        sections.append(("heading", "Job Description"))
        sections += _html_to_sections(listing["job_description"])
    if listing.get("preferred_skills"):
        sections.append(("heading", "Preferred Skills"))
        sections += _html_to_sections(listing["preferred_skills"])
    if listing.get("contact_email"):
        sections.append(("heading", "Contact"))
        sections.append(("paragraph", f"Apply to: {listing['contact_email']}"))
    return sections


def _infopark(job: dict) -> list[tuple[str, str]]:
    resp = _session.get(job["apply_link"], timeout=TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    box = soup.select_one("div.deatil-box") or soup.select_one("div.comp-job-deatiil")
    if not box:
        return []
    sections = []
    for el in box.find_all(["h1", "h2", "h3", "h4", "h5", "p", "li"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        kind = "heading" if el.name.startswith("h") else "paragraph"
        sections.append((kind, f"• {text}" if el.name == "li" else text))
    if len(sections) < 3:
        # Some postings keep their fields in bare <div>s — fall back to the
        # container's line-by-line text.
        sections = [("paragraph", line)
                    for line in box.get_text("\n", strip=True).splitlines()
                    if line.strip()]
    return sections


def _cyberpark(job: dict) -> list[tuple[str, str]]:
    resp = _session.get(job["apply_link"], timeout=TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    box = soup.select_one("div.job_description") or soup.select_one(".entry-content")
    if not box:
        return []
    return _html_to_sections(str(box))


_FETCHERS = {
    "Technopark": _technopark,
    "Infopark": _infopark,
    "Cyberpark": _cyberpark,
}


def fetch_details(job: dict) -> list[tuple[str, str]]:
    fetcher = _FETCHERS.get(job.get("it_park"))
    link = job.get("apply_link", "")
    if not fetcher or not link.startswith("http"):
        return []
    try:
        return fetcher(job)
    except Exception as e:
        print(f"  details fetch failed for '{job.get('title')}': {e}")
        return []
