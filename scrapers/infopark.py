"""
Infopark Scraper
----------------
https://infopark.in/companies-job is plain server-rendered HTML — a real
<table> paginated with ?page=N. No browser needed. I fetched this page
directly and confirmed the structure below (columns: Date of Posting, Job
Title, Company Name, Last Date to Apply, Details link), so these selectors
are NOT guesses like the Technopark ones.

Pagination: ?page=1, ?page=2, ... up to a "last page" number shown in the
pager. We detect the last page number from the pager links on page 1 and
stop there (with a hard safety cap).
"""

import re
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://infopark.in/companies-job"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
}
MAX_PAGES_SAFETY_CAP = 40  # ~20 rows/page; adjust if Infopark's listing volume grows a lot


def _parse_table(soup: BeautifulSoup) -> list[dict]:
    rows = []
    table = soup.find("table")
    if not table:
        return rows

    for tr in table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")[1:]:
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue

        posted_date = cells[0].get_text(strip=True)
        title = cells[1].get_text(strip=True)
        company = cells[2].get_text(strip=True)
        deadline = cells[3].get_text(strip=True)

        link = ""
        detail_link_el = tr.find("a", href=True)
        if detail_link_el:
            link = detail_link_el["href"]
            if link.startswith("/"):
                link = f"https://infopark.in{link}"

        if not title or not company:
            continue

        rows.append({
            "title": title,
            "company": company,
            "location": "Infopark",  # refined below if a specific campus page is used
            "posted_date": posted_date,
            "deadline": deadline,
            "apply_link": link,
            "description": "",  # left blank; fetching every detail page is expensive — add on request
            "it_park": "Infopark",
        })

    return rows


def _find_last_page(soup: BeautifulSoup) -> int:
    """Look at pager links like ?page=21 and return the highest page number found."""
    max_page = 1
    for a in soup.find_all("a", href=True):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            max_page = max(max_page, int(m.group(1)))
    return max_page


def scrape() -> list[dict]:
    session = requests.Session()
    session.headers.update(HEADERS)

    first_resp = session.get(BASE_URL, timeout=30)
    first_resp.raise_for_status()
    first_soup = BeautifulSoup(first_resp.text, "html.parser")

    jobs = _parse_table(first_soup)
    last_page = min(_find_last_page(first_soup), MAX_PAGES_SAFETY_CAP)
    print(f"Infopark: detected {last_page} page(s)")

    for page_num in range(2, last_page + 1):
        resp = session.get(BASE_URL, params={"page": page_num}, timeout=30)
        if resp.status_code != 200:
            print(f"Infopark: page {page_num} returned {resp.status_code}, stopping pagination")
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        page_jobs = _parse_table(soup)
        if not page_jobs:
            break
        jobs.extend(page_jobs)
        time.sleep(0.5)  # be polite to their server

    print(f"Infopark: scraped {len(jobs)} jobs total")
    return jobs


if __name__ == "__main__":
    results = scrape()
    for j in results[:5]:
        print(j)
