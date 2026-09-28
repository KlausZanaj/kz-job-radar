"""Import only job links from user-selected .eml alert files, without mailbox access."""
import re
from email import policy
from email.parser import Parser
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

from .model import Job, plain

URLS = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
VAGUE = {"view job", "visualizza offerta", "visualizza lavoro", "apply now", "candidati",
         "see job", "jobs", "visualizza annuncio", "vai all'annuncio"}


class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.href = dict(attrs).get("href")
            self.text = []

    def handle_data(self, data):
        if self.href:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.href:
            self.links.append((unescape(self.href), plain(" ".join(self.text))))
            self.href = None
            self.text = []


def identify(raw):
    """Return (source, stable ID, canonical link) only for direct job links."""
    raw = unescape(raw).strip().rstrip(".,;)")
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        match = re.search(r"/jobs/view/(\d+)", path)
        if match:
            ident = match.group(1)
            return "LinkedIn Alert", ident, f"https://www.linkedin.com/jobs/view/{ident}/"
    if host == "indeed.com" or host.endswith(".indeed.com"):
        query = parse_qs(parsed.query)
        jk = (query.get("jk") or query.get("vjk") or [None])[0]
        if jk and re.fullmatch(r"[a-zA-Z0-9]{5,50}", jk) and path in ("/viewjob", "/m/viewjob", "/rc/clk", "/jobs"):
            return "Indeed Alert", jk, f"https://it.indeed.com/viewjob?jk={jk}"
    return None


def parse_alert(raw):
    if len(raw.encode("utf-8")) > 700_000:
        raise ValueError("Email troppo grande: massimo 700 KB")
    message = Parser(policy=policy.default).parsestr(raw)
    subject = plain(message.get("Subject", ""))[:180]
    candidates = []
    for part in message.walk():
        if part.get_content_disposition() == "attachment":
            continue
        if part.get_content_type() not in ("text/html", "text/plain"):
            continue
        try:
            body = part.get_content()
            if isinstance(body, bytes):
                body = body.decode("utf-8", "replace")
        except (LookupError, ValueError):
            continue
        if part.get_content_type() == "text/html":
            anchors = AnchorParser()
            anchors.feed(body)
            candidates.extend(anchors.links)
        candidates.extend((link, "") for link in URLS.findall(body))
    items = {}
    for url, label in candidates:
        target = identify(url)
        if not target:
            continue
        source, ident, canonical = target
        title = label.strip()[:180]
        if title.lower() in VAGUE or len(title) < 6:
            title = subject if "nuove offerte" not in subject.lower() else "Titolo da verificare nell'annuncio"
        key = f"{source}:{ident}"
        old = items.get(key)
        if old and old.title != "Titolo da verificare nell'annuncio" and old.title != subject:
            continue
        items[key] = Job(source, ident, title or "Titolo da verificare nell'annuncio", "Azienda da verificare",
                         "Sede da verificare", canonical)
    return list(items.values())
