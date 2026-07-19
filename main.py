"""
Main orchestrator: runs all three IT Park scrapers, adds Role Type
classification, de-dupes, and writes a single jobs.json for notion_sync.py.

Usage:
    python main.py
"""

import json
import hashlib
import sys
from pathlib import Path

from scrapers import technopark, infopark, cyberpark
from scrapers.role_classifier import classify_role

OUTPUT_FILE = Path(__file__).parent / "jobs.json"


def ensure_job_id(job: dict) -> str:
    if job.get("job_id"):
        return job["job_id"]
    raw = f"{job.get('title','')}|{job.get('company','')}|{job.get('apply_link','')}".strip().lower()
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def run_scraper_safely(name: str, fn):
    """Never let one broken scraper take down the other two."""
    try:
        results = fn()
        if not results:
            # These sites always have listings — an empty result means the
            # scraper is broken (bad selectors / changed API), not "no jobs".
            print(f"⚠️  {name} scraper returned 0 jobs — it is probably broken.")
        return results
    except Exception as e:
        print(f"⚠️  {name} scraper failed: {e}")
        return []


def main():
    all_jobs = []
    all_jobs += run_scraper_safely("Technopark", technopark.scrape)
    all_jobs += run_scraper_safely("Infopark", infopark.scrape)
    all_jobs += run_scraper_safely("Cyberpark", cyberpark.scrape)

    seen = {}
    for job in all_jobs:
        job["job_id"] = ensure_job_id(job)
        job["role_type"] = classify_role(job.get("title", ""))
        seen[job["job_id"]] = job  # de-dupe across all sources by job_id

    jobs = list(seen.values())
    OUTPUT_FILE.write_text(json.dumps(jobs, indent=2, ensure_ascii=False))

    by_park = {}
    for j in jobs:
        by_park[j["it_park"]] = by_park.get(j["it_park"], 0) + 1

    print(f"\nTotal unique jobs: {len(jobs)}")
    for park, count in by_park.items():
        print(f"  {park}: {count}")
    print(f"Wrote {OUTPUT_FILE}")

    if not jobs:
        # Fail the run (and the GitHub Action) instead of silently syncing nothing.
        print("❌ All scrapers returned 0 jobs — failing the run so it doesn't go unnoticed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
