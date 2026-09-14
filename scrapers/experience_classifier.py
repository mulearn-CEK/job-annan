"""
Auto-classifies a job title into an Experience Level bucket for job-board
filtering: Fresher, Senior, or Intermediate.

Rules are checked in order — FIRST MATCH WINS. Fresher-signal keywords are
checked before Senior ones because titles like "Senior" rarely also say
"intern", but titles like "Trainee - Senior QA process" (rare, but possible)
should still read as entry-level if a fresher keyword is present.

Anything that doesn't match either list defaults to "Intermediate" — most
listings don't state seniority explicitly, and mid-level is the safest
assumption for a standard, unqualified job posting.

Keywords are matched on word boundaries so e.g. "hr" doesn't match "chr".
"""

import re

FRESHER_KEYWORDS = [
    "intern", "internship", "trainee", "fresher", "freshers", "apprentice",
    "entry level", "entry-level", "graduate trainee", "campus hire",
    "junior", "jr",
]

SENIOR_KEYWORDS = [
    "senior", "sr", "lead", "principal", "staff engineer", "architect",
    "head of", "director", "vp", "vice president", "chief", "manager",
    "team lead", "tech lead", "engineering manager",
]

_FRESHER_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(kw) for kw in FRESHER_KEYWORDS) + r")(?!\w)"
)
_SENIOR_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(kw) for kw in SENIOR_KEYWORDS) + r")(?!\w)"
)


def classify_experience(title: str) -> str:
    if not title:
        return "Intermediate"
    lowered = title.lower()
    if _FRESHER_RE.search(lowered):
        return "Fresher"
    if _SENIOR_RE.search(lowered):
        return "Senior"
    return "Intermediate"
