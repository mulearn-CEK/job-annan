"""
Technopark Job Scraper
-----------------------
technopark.in/job-search is a JS-rendered app, but the underlying data comes
from a public JSON API which we call directly — no headless browser needed:

    https://technopark.in/api/paginated-jobs?page=N

Verified live: returns paginated JSON with job_title, company, posted_date,
closing_date, walk-in info, and a stable job_listing_id (e.g. "JOB-72-31542")
which we use as the dedup key instead of hashing title/company/link.

Usage:
    python scrapers/technopark.py    # scrapes and prints first 5 jobs
"""

import sys
import time
import requests

API_URL = "https://technopark.in/api/paginated-jobs"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json",
}
MAX_PAGES_SAFETY_CAP = 60  # 20 jobs/page; currently ~19 pages


def _to_job(item: dict) -> dict:
    company = (item.get("company") or {}).get("company", "")
    title = (item.get("job_title") or "").strip()

    description = ""
    if item.get("is_walk_in"):
        start = item.get("walk_in_start_date") or ""
        end = item.get("closing_date") or ""
        description = f"Walk-In interview: {start} to {end}".strip()

    return {
        "job_id": (item.get("job_listing_id") or "").lower() or None,
        "title": title,
        "company": company,
        "location": "Technopark",
        "posted_date": item.get("posted_date") or "",
        "deadline": item.get("closing_date") or "",
        "apply_link": f"https://technopark.in/job-details/{item['id']}",
        "description": description,
        "it_park": "Technopark",
    }


def scrape(debug: bool = False) -> list[dict]:
    session = requests.Session()
    session.headers.update(HEADERS)

    jobs = []
    page = 1
    last_page = 1

    while page <= min(last_page, MAX_PAGES_SAFETY_CAP):
        resp = session.get(API_URL, params={"page": page}, timeout=30)
        if page > 1 and resp.status_code != 200:
            print(f"Technopark: page {page} returned {resp.status_code}, stopping pagination")
            break
        resp.raise_for_status()
        payload = resp.json()

        last_page = payload.get("last_page", 1)
        data = payload.get("data", [])
        if not data:
            break

        for item in data:
            job = _to_job(item)
            if job["title"]:
                jobs.append(job)

        page += 1
        time.sleep(0.4)  # be polite to their server

    print(f"Technopark: scraped {len(jobs)} jobs across {page - 1} page(s)")
    return jobs


if __name__ == "__main__":
    results = scrape(debug="--debug" in sys.argv)
    for j in results[:5]:
        print(j)
    if not results:
        print("\n⚠️  No jobs found — check if the API shape at "
              f"{API_URL} has changed.")
