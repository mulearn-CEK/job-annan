"""
Auto-classifies a job title into a coarse Role Type bucket for Notion filtering.

Rules are checked in order — FIRST MATCH WINS — so ordering is deliberate:
specific buckets (Data/AI/ML, QA, DevOps, Support...) come before the generic
"Software Development" catch-all, otherwise titles like "Data Engineer" or
"QA Engineer" would be swallowed by the generic "engineer" keyword.
"Internship / Trainee" is first of all: a "Software Developer Intern" should
land in the bucket students filter by.

Keywords are matched on word boundaries ("qa" won't match "Qatar").
Extend ROLE_KEYWORDS as you notice titles falling into "Other".
"""

import re

ROLE_KEYWORDS = [
    ("Internship / Trainee", ["intern", "internship", "trainee", "fresher",
                              "freshers", "apprentice"]),
    ("Data / AI / ML", ["data scientist", "data analyst", "data engineer",
                        "machine learning", "ml engineer", "ai engineer",
                        "artificial intelligence", "deep learning", "nlp",
                        "computer vision", "data science", "big data",
                        "business intelligence", "power bi", "analytics"]),
    ("QA / Testing", ["qa", "quality assurance", "quality analyst",
                      "test engineer", "tester", "testing", "sdet",
                      "automation test"]),
    ("DevOps / Cloud / Sysadmin", ["devops", "cloud", "aws", "azure",
                                   "system administrator", "sysadmin",
                                   "site reliability", "sre",
                                   "network engineer", "network administrator",
                                   "infrastructure", "security engineer",
                                   "cyber security", "cybersecurity"]),
    ("Technical Support", ["technical support", "support engineer",
                           "support executive", "help desk", "helpdesk",
                           "service desk", "customer support",
                           "customer care", "product support", "it support"]),
    ("Design / UI-UX", ["designer", "ui/ux", "ux", "ui", "graphic",
                        "video editor", "video editing", "animator",
                        "illustrator", "visual content"]),
    ("Project / Product Management", ["project manager", "product manager",
                                      "product owner", "scrum master",
                                      "business analyst", "project management",
                                      "delivery manager", "program manager",
                                      "project coordinator"]),
    ("Business / Sales / Marketing", ["business development", "sales", "bde",
                                      "marketing", "marketer", "seo", "sem", "growth",
                                      "content writer", "content marketing",
                                      "social media", "brand", "pre-sales",
                                      "presales", "lead generation"]),
    ("HR / Admin / Finance", ["hr", "human resources", "recruiter",
                              "talent acquisition", "accountant", "accounts",
                              "finance", "financial", "admin", "administration",
                              "office assistant", "front office",
                              "receptionist", "payroll", "compliance"]),
    # Generic catch-all LAST — "engineer"/"developer" would otherwise swallow
    # every specific bucket above.
    ("Software Development", ["developer", "engineer", "programmer", "sde",
                              "full stack", "fullstack", "backend", "frontend",
                              "front-end", "back-end", "software", "architect",
                              "web development", "mobile app", "android", "ios",
                              "flutter", "react", "node", "python", "java",
                              "php", ".net", "dotnet", "odoo"]),
]

# Precompile one word-boundary regex per bucket. Lookarounds instead of \b so
# keywords starting with a non-word char (".net") still anchor correctly.
_COMPILED = [
    (role, re.compile(r"(?<!\w)(?:" + "|".join(re.escape(kw) for kw in kws) + r")(?!\w)"))
    for role, kws in ROLE_KEYWORDS
]


def classify_role(title: str) -> str:
    if not title:
        return "Other"
    lowered = title.lower()
    for role_type, pattern in _COMPILED:
        if pattern.search(lowered):
            return role_type
    return "Other"
