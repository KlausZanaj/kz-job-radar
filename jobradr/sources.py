"""Documented public read-only job feeds; never submit applications."""
import json
import os
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .model import Job, date_utc, plain

AGENT = "KZ-Job-Radar/0.1 (personal local job search; one request per feed per hour)"
SLUG = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def read_json(url, timeout=12):
    request = Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        if int(response.headers.get("Content-Length", 0)) > 5_000_000:
            raise ValueError("Risposta troppo grande")
        data = response.read(5_000_001)
        if len(data) > 5_000_000:
            raise ValueError("Risposta troppo grande")
        return json.loads(data)


def arbeitnow(fetch=read_json, pages=2):
    for page in range(1, min(int(pages), 3) + 1):
        data = fetch(f"https://www.arbeitnow.com/api/job-board-api?page={page}")
        for item in data.get("data", []):
            if not isinstance(item, dict) or not item.get("url"):
                continue
            yield Job("Arbeitnow", str(item.get("slug") or item["url"]), str(item.get("title") or ""),
                      str(item.get("company_name") or ""), str(item.get("location") or ""),
                      str(item["url"]), plain(item.get("description")),
                      date_utc(item.get("created_at")), bool(item.get("remote")))


def greenhouse(slug, fetch=read_json):
    if not SLUG.fullmatch(slug):
        raise ValueError("Identificativo Greenhouse non valido")
    data = fetch(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    # List endpoint supplies updated_at, not first_published: mark unknown rather than inventing publication.
    for item in data.get("jobs", []):
        if not item.get("id") or not item.get("absolute_url"):
            continue
        location = item.get("location") or {}
        yield Job(f"Greenhouse/{slug}", str(item["id"]), str(item.get("title") or ""), slug,
                  str(location.get("name") or ""), str(item["absolute_url"]), plain(item.get("content")))


def lever(slug, fetch=read_json, eu=False):
    if not SLUG.fullmatch(slug):
        raise ValueError("Identificativo Lever non valido")
    host = "api.eu.lever.co" if eu else "api.lever.co"
    data = fetch(f"https://{host}/v0/postings/{slug}?mode=json")
    for item in data:
        if not isinstance(item, dict) or not item.get("hostedUrl"):
            continue
        categories = item.get("categories") or {}
        location = categories.get("location") or ""
        yield Job(f"Lever/{slug}", str(item.get("id") or item["hostedUrl"]),
                  str(item.get("text") or ""), slug, str(location), str(item["hostedUrl"]),
                  plain(item.get("descriptionPlain") or item.get("description")),
                  date_utc(item.get("createdAt")))


def adzuna(fetch=read_json):
    """At most three searches per scan = <= 72 requests/day at hourly cadence."""
    app_id = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()
    if not app_id or not app_key:
        return
    for term in ("e-commerce", "back office", "marketing"):
        query = urlencode({"app_id": app_id, "app_key": app_key, "results_per_page": 50,
                           "what": term, "where": "Veneto", "sort_by": "date"})
        data = fetch(f"https://api.adzuna.com/v1/api/jobs/it/search/1?{query}")
        for item in data.get("results", []):
            if not item.get("redirect_url"):
                continue
            company = item.get("company") or {}
            location = item.get("location") or {}
            yield Job("Adzuna", str(item.get("id") or item["redirect_url"]),
                      str(item.get("title") or ""), str(company.get("display_name") or ""),
                      str(location.get("display_name") or ""), str(item["redirect_url"]),
                      plain(item.get("description")), date_utc(item.get("created")))
