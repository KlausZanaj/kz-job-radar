from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser


class _Stripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    parser = _Stripper()
    parser.feed(unescape(str(value or "")))
    return " ".join(" ".join(parser.parts).split())[:12000]


def date_utc(value):
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            number = float(value)
            if number > 10**11:
                number /= 1000
            return datetime.fromtimestamp(number, tz=timezone.utc).isoformat()
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return date.replace(tzinfo=timezone.utc).astimezone(timezone.utc).isoformat() if date.tzinfo is None else date.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


@dataclass(frozen=True)
class Job:
    source: str
    source_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    published_at: str | None = None
    remote: bool = False

    @property
    def key(self):
        return f"{self.source}:{self.source_id}"
