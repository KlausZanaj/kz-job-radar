import threading
import os
from datetime import datetime, timedelta, timezone

from . import sources


class Engine:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self.active = False
        self.last_error = ""

    def scan(self):
        if not self.lock.acquire(blocking=False):
            return False
        self.active = True
        errors, count = [], 0
        try:
            feeds = []
            if self.store.setting("feed_enabled"):
                feeds.append(("Arbeitnow", lambda: sources.arbeitnow()))
            if os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY"):
                feeds.append(("Adzuna", lambda: sources.adzuna()))
            for board in self.store.setting("boards") or []:
                typ, slug = board["type"], board["slug"]
                if typ == "greenhouse":
                    feeds.append((f"Greenhouse/{slug}", lambda s=slug: sources.greenhouse(s)))
                elif typ in ("lever", "lever_eu"):
                    feeds.append((f"Lever/{slug}", lambda s=slug, e=typ == "lever_eu": sources.lever(s, eu=e)))
            for label, feed in feeds:
                try:
                    for job in feed():
                        self.store.upsert(job)
                        count += 1
                except Exception as exc:
                    errors.append(f"{label}: {type(exc).__name__}: {str(exc)[:160]}")
            self.store.scan_result(count, errors)
            self.last_error = "; ".join(errors)
            return True
        finally:
            self.active = False
            self.lock.release()

    def start_scan(self):
        if self.active:
            return False
        threading.Thread(target=self.scan, daemon=True).start()
        return True

    def monitor(self, stop):
        while not stop.is_set():
            if self.store.setting("monitoring_enabled") and not self.active:
                last = self.store.setting("last_scan")
                try:
                    due = not last or datetime.fromisoformat(last) <= datetime.now(timezone.utc) - timedelta(hours=1)
                except ValueError:
                    due = True
                if due:
                    self.start_scan()
            stop.wait(15)
