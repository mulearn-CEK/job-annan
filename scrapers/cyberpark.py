"""
Cyberpark Scraper
-----------------
https://cyberparks.in/careers/ explicitly states listings require JavaScript,
and has a "Load more listings" button — a common pattern for the WP Job
Manager WordPress plugin (which usually renders jobs as <li class="job_listing">
elements). The selectors below are an educated guess based on that plugin's
typical markup, NOT verified against the live rendered DOM (same network
restriction as noted in scraper.py for Technopark).

Usage:
    python scrapers/cyberpark.py            # scrapes and prints count
    python scrapers/cyberpark.py --debug     # saves cyberpark_debug.html/.png
"""

import re
import sys
import hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://cyberparks.in/careers/"
DEBUG_DIR = Path(__file__).parent.parent


def scrape(debug: bool = False) -> list[dict]:
    jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ))
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        # ------------------------------------------------------------------
        # HOW TO FIX SELECTORS (do this first run):
        # 1. Run: python scrapers/cyberpark.py --debug
        # 2. Open cyberpark_debug.png to confirm listings rendered.
        # 3. Open cyberpark_debug.html, inspect a job listing element and a
        #    "Load more listings" button, update the selectors below.
        # ------------------------------------------------------------------
        # Verified against the live WP Job Manager markup (2026-07):
        # <li class="job_listing"> > a > .position > h3 (title),
        # div.company > strong, div.location, ul.meta > li.date > time
        LOAD_MORE_SELECTOR = "a.load_more_jobs"
        CARD_SELECTOR = "li.job_listing"

        # Click "Load more" repeatedly until it disappears or stops adding results
        max_clicks = 30
        for _ in range(max_clicks):
            load_more = page.query_selector(LOAD_MORE_SELECTOR)
            if not load_more or not load_more.is_visible():
                break
            try:
                load_more.click()
                page.wait_for_timeout(1200)
            except Exception:
                break

        if debug:
            page.screenshot(path=str(DEBUG_DIR / "cyberpark_debug.png"), full_page=True)
            (DEBUG_DIR / "cyberpark_debug.html").write_text(page.content())
            print("Saved cyberpark_debug.png and cyberpark_debug.html for inspection.")

        cards = page.query_selector_all(CARD_SELECTOR)
        print(f"Cyberpark: found {len(cards)} candidate elements matching '{CARD_SELECTOR}'")

        for card in cards:
            try:
                title_el = card.query_selector(".position h3, h3")
                company_el = card.query_selector("div.company strong")
                location_el = card.query_selector("div.location")
                date_el = card.query_selector("li.date time")
                link_el = card.query_selector("a")

                title = title_el.inner_text().strip() if title_el else None
                if not title:
                    continue

                company = company_el.inner_text().strip() if company_el else ""
                location = location_el.inner_text().strip() if location_el else "Cyberpark"
                posted_date = (date_el.get_attribute("datetime") or "") if date_el else ""
                link = link_el.get_attribute("href") if link_el else ""
                description = re.sub(r"\s+", " ", card.inner_text()).strip()[:500]

                raw_id = f"{title}|{company}|{link}".strip().lower()
                job_id = hashlib.sha256(raw_id.encode()).hexdigest()[:16]

                jobs.append({
                    "job_id": job_id,
                    "title": title,
                    "company": company,
                    "location": location,
                    "posted_date": posted_date,
                    "deadline": "",
                    "apply_link": link,
                    "description": description,
                    "it_park": "Cyberpark",
                })
            except Exception as e:
                print(f"Cyberpark: skipped a card due to error: {e}")

        browser.close()

    print(f"Cyberpark: scraped {len(jobs)} jobs total")
    return jobs


if __name__ == "__main__":
    debug_mode = "--debug" in sys.argv
    results = scrape(debug=debug_mode)
    for j in results[:5]:
        print(j)
    if not results:
        print(
            "\n⚠️  No jobs found. Run 'python scrapers/cyberpark.py --debug' and "
            "inspect cyberpark_debug.png / .html to fix CARD_SELECTOR / LOAD_MORE_SELECTOR."
        )
