"""Stateless public scan for the Streamlit demo; no credentials or personal data."""

from . import sources
from .scoring import freshness, rank

BOARDS = ("autoscout24", "lovable")
TRIVENETO_PLACES = (
    "padova", "padua", "vigonza", "piombino dese", "brugine", "treviso", "roncade",
    "vicenza", "verona", "rovigo", "venezia", "venice", "mestre", "quarto d'altino",
    "santa maria di sala", "belluno", "udine", "pordenone", "gorizia", "trieste",
    "trento", "bolzano", "veneto", "friuli", "trentino", "alto adige", "south tyrol",
)


def triveneto_location(location):
    """Only explicit regional locations qualify; unknown or foreign remote jobs do not."""
    from .scoring import has

    return any(has(location, place) for place in TRIVENETO_PLACES)


def collect_public():
    jobs, errors = {}, []
    feeds = [("Arbeitnow", lambda: sources.arbeitnow())]
    feeds.extend((f"Greenhouse/{slug}", lambda s=slug: sources.greenhouse(s)) for slug in BOARDS)
    for name, feed in feeds:
        try:
            for job in feed():
                detail = rank(job)
                jobs[job.key] = {
                    "id": job.key,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "url": job.url,
                    "source": job.source,
                    "published_at": job.published_at,
                    "score": detail["score"],
                    "category": detail["category"],
                    "reason": detail["reason"],
                    "location_note": detail["location_note"],
                }
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}")
    result = list(jobs.values())
    for row in result:
        row["freshness"] = freshness(row["published_at"])
    return sorted(result, key=lambda x: (-x["score"], x["title"])), errors
