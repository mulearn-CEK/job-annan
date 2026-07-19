# Kerala IT Park Job Scraper → Notion (Placement Cell Portal)

Scrapes job listings daily from **Technopark**, **Infopark**, and **Cyberpark**, and syncs them into a single Notion database — set up as one landing page with 3 filtered sub-pages, one per IT Park, plus role-based filtering for students.

## How each site is scraped

| Site | Method | Why |
|---|---|---|
| Technopark (`technopark.in/job-search`) | `requests` → public JSON API (`/api/paginated-jobs`) | The page is JS-rendered, but its data comes from a public paginated JSON API — verified live, no browser needed. |
| Infopark (`infopark.in/companies-job`) | `requests` + `BeautifulSoup` | Plain server-rendered HTML `<table>`, paginated with `?page=N`. Verified structure directly — no guessing needed here. |
| Cyberpark (`cyberparks.in/careers/`) | Playwright, clicks "Load more listings" | Site explicitly requires JS; likely a WP Job Manager plugin pattern. |

## Verification status

- **Technopark** — ✅ verified live: scrapes the public JSON API directly (373 jobs / 19 pages at last check). No selectors to maintain.
- **Infopark** — ✅ verified live: table structure and pagination confirmed against the real page.
- **Cyberpark** — ⚠️ selectors spot-checked against the live page's raw HTML (`li.job_listing` / "Load more listings" are correct WP Job Manager markup), but the full Playwright flow hasn't been run end-to-end yet:

```bash
pip install -r requirements.txt
playwright install chromium

python scrapers/technopark.py           # prints first 5 jobs to check
python scrapers/infopark.py             # prints first 5 jobs to check
python scrapers/cyberpark.py --debug    # saves cyberpark_debug.png + .html if it finds nothing
```

## Notion structure (recommended)

**Don't create separate databases per IT Park or per company** — one database with filtered *views* is far easier to maintain and keeps automation simple (the scraper only ever writes to one place).

### 1. One database: `Job Listings`
Properties:
- `Job Title` (Title)
- `Company` (Text)
- `Location` (Text)
- `Posted Date` (Text)
- `Deadline` (Text)
- `Apply Link` (URL)
- `Description` (Text)
- `IT Park` (Select: Technopark / Infopark / Cyberpark)
- `Role Type` (Select — option names must match `scrapers/role_classifier.py` exactly, or Notion will auto-create duplicate options: `Software Development`, `QA / Testing`, `Design / UI-UX`, `Data / AI / ML`, `DevOps / Cloud / Sysadmin`, `Technical Support`, `Business / Sales / Marketing`, `HR / Admin / Finance`, `Internship / Trainee`, `Project / Product Management`, `Other`)
- `Status` (Select: New / Reviewed / Shared with students)
- `Job ID` (Text — hidden dedup key, don't edit manually)

### 2. Landing page → 3 sub-pages
Create a landing page, and inside it 3 **linked views** of the same database (Notion: "+ Add a page inside" → "Existing database" or embed a **Linked view of `Job Listings`**), one per IT Park:
- `Technopark` sub-page → filter `IT Park = Technopark`
- `Infopark` sub-page → filter `IT Park = Infopark`
- `Cyberpark` sub-page → filter `IT Park = Cyberpark`

### 3. Inside each IT Park sub-page, add more views instead of nesting company pages
- **Board view** grouped by `Company` — behaves like company folders, updates itself automatically as new companies post jobs.
- **Board view** grouped by `Role Type` — the filter students actually need ("show me only Dev roles" / "only Internships").
- **Table view** with visible filter/sort controls (Location, Deadline, Status) for students to adjust live.

This way, adding new IT Parks later (say a 4th park) is just: add one more Select option + one more filtered view — no schema changes, no new databases.

## Setup steps

1. **Notion integration**: https://www.notion.so/my-integrations → New integration → copy the secret.
2. **Create the database** as above, share it with your integration (`...` menu → Connections).
3. **Local test**:
   ```bash
   export NOTION_TOKEN="your_integration_secret"
   export NOTION_DATABASE_ID="your_database_id"
   python main.py          # runs all 3 scrapers → writes jobs.json
   python notion_sync.py   # pushes new jobs into Notion
   ```
4. **GitHub Actions** (daily automation):
   - Push this repo to GitHub (private repo recommended).
   - Settings → Secrets and variables → Actions → add `NOTION_TOKEN` and `NOTION_DATABASE_ID`.
   - `.github/workflows/daily-scrape.yml` runs `main.py` + `notion_sync.py` daily at 8:30 AM IST (adjust the cron if needed), and can also be triggered manually from the Actions tab.

## Deduplication

Each job gets a `job_id` (hash of title + company + link). `notion_sync.py` checks Notion for an existing page with that ID before creating a new one — so re-running daily only adds genuinely new postings, and doesn't touch `Status` on ones your team already reviewed.

## If one site's scraper breaks

`main.py` wraps each scraper in a try/except — if, say, Cyberpark changes its markup and its scraper starts failing, Technopark and Infopark still sync normally. You'll see a warning printed in the Action's log for whichever one failed.
