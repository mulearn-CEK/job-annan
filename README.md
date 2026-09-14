# Kerala IT Park Job Scraper → job-board

Scrapes job listings daily from **Technopark**, **Infopark**, and **Cyberpark**, classifies each job's role type and experience level, and writes them to `jobs.json`. That file is published straight into the [`job-board`](../job-board) site's `public/data/jobs.json` (no backend, no database) — the site reads it directly and renders filterable job cards.

> `notion_sync.py` (syncing into a Notion database) is no longer part of the
> default pipeline — it's kept in the repo as a legacy/optional path, but
> `daily-scrape.yml` no longer calls it. See "Legacy: Notion sync" below if
> you still want it.

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

## Classification

Every job in `jobs.json` gets two derived fields the job-board site filters on:
- `role_type` — `scrapers/role_classifier.py`: Software Development, QA / Testing, DevOps / Cloud / Sysadmin, Data / AI / ML, Design / UI-UX, Technical Support, Business / Sales / Marketing, HR / Admin / Finance, Project / Product Management, Internship / Trainee, Other.
- `experience_level` — `scrapers/experience_classifier.py`: Fresher, Intermediate, Senior (keyword-based off the title; defaults to Intermediate when no signal is present).

## Setup steps

1. **Local test**:
   ```bash
   python main.py          # runs all 3 scrapers → writes jobs.json
   ```
2. **GitHub Actions** (daily automation):
   - Push this repo to GitHub.
   - To auto-publish into the job-board site repo, add:
     - Repo **variable** `JOB_BOARD_REPO` = `owner/job-board`
     - Repo **secret** `JOB_BOARD_REPO_TOKEN` = a PAT with push access to that repo
   - `.github/workflows/daily-scrape.yml` runs `main.py` daily at 8:30 AM IST (adjust the cron if needed) and, if those are set, commits the fresh `jobs.json` straight into `job-board/public/data/jobs.json`. Without them, it still scrapes and produces `jobs.json` as a build artifact — you just have to copy it over yourself.

## Deduplication

Each job gets a `job_id` (the site's own stable ID when available, e.g. Technopark's `job_listing_id`, otherwise a hash of title + company + link). `main.py` de-dupes across all three sources by `job_id` before writing `jobs.json`, so re-running daily doesn't create duplicate entries.

## Legacy: Notion sync

`notion_sync.py` and the Notion database structure described below still work if you want a second, human-curated view (e.g. for a placement cell to mark jobs "Reviewed" / "Shared with students") — just run it manually, it's no longer wired into `daily-scrape.yml`.

**Don't create separate databases per IT Park or per company** — one database with filtered *views* is far easier to maintain.

### One database: `Job Listings`
Properties:
- `Job Title` (Title)
- `Company` (Text)
- `Location` (Text)
- `Posted Date` (Text)
- `Deadline` (Text)
- `Apply Link` (URL)
- `Description` (Text)
- `IT Park` (Select: Technopark / Infopark / Cyberpark)
- `Role Type` (Select — option names must match `scrapers/role_classifier.py` exactly, or Notion will auto-create duplicate options)
- `Status` (Select: New / Reviewed / Shared with students)
- `Job ID` (Text — hidden dedup key, don't edit manually)

Run it with:
```bash
export NOTION_TOKEN="your_integration_secret"
export NOTION_DATABASE_ID="your_database_id"
python notion_sync.py
```

## If one site's scraper breaks

`main.py` wraps each scraper in a try/except — if, say, Cyberpark changes its markup and its scraper starts failing, Technopark and Infopark still sync normally. You'll see a warning printed in the Action's log for whichever one failed.
