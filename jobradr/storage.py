"""Local SQLite: only public postings and the user's preferences, no CV PDF storage."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .scoring import rank

DEFAULTS = {"monitoring_enabled": False, "ai_enabled": False, "feed_enabled": True,
            "boards": [{"type": "greenhouse", "slug": "autoscout24"},
                       {"type": "greenhouse", "slug": "lovable"}], "last_scan": None}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                  id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL,
                  company TEXT NOT NULL, location TEXT NOT NULL, url TEXT NOT NULL,
                  description TEXT NOT NULL, published_at TEXT, remote INTEGER NOT NULL,
                  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
                  score INTEGER NOT NULL, category TEXT NOT NULL, reason TEXT NOT NULL,
                  location_note TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Da valutare',
                  ai_note TEXT
                );
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY, started TEXT NOT NULL,
                  found INTEGER NOT NULL, errors TEXT NOT NULL);
            """)
            for name, value in DEFAULTS.items():
                db.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (name, json.dumps(value)))

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def setting(self, name):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (name,)).fetchone()
            return json.loads(row[0]) if row else None

    def update_setting(self, name, value):
        if name not in DEFAULTS:
            raise ValueError("Impostazione sconosciuta")
        with self.connect() as db:
            db.execute("INSERT INTO settings VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (name, json.dumps(value)))

    def upsert(self, job):
        result = rank(job)
        now = utcnow()
        with self.connect() as db:
            db.execute("""INSERT INTO jobs
                (id,source,title,company,location,url,description,published_at,remote,
                 first_seen,last_seen,score,category,reason,location_note)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title, company=excluded.company,
                location=excluded.location,url=excluded.url,description=excluded.description,
                published_at=excluded.published_at,remote=excluded.remote,
                last_seen=excluded.last_seen, score=excluded.score,category=excluded.category,
                reason=excluded.reason,location_note=excluded.location_note""",
                (job.key, job.source, job.title, job.company, job.location, job.url,
                 job.description, job.published_at, int(job.remote), now, now,
                 result["score"], result["category"], result["reason"], result["location_note"]))

    def jobs(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY score DESC, first_seen DESC LIMIT 2000")]

    def job(self, key):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (key,)).fetchone()
            return dict(row) if row else None

    def change_status(self, key, status):
        if status not in ("Da valutare", "Interessante", "Candidatura inviata", "Scartato"):
            raise ValueError("Stato non valido")
        with self.connect() as db:
            changed = db.execute("UPDATE jobs SET status=? WHERE id=?", (status, key)).rowcount
            return bool(changed)

    def save_ai_note(self, key, note):
        with self.connect() as db:
            db.execute("UPDATE jobs SET ai_note=? WHERE id=?", (note[:2500], key))

    def scan_result(self, found, errors):
        now = utcnow()
        with self.connect() as db:
            db.execute("INSERT INTO scans(started,found,errors) VALUES(?,?,?)", (now, found, json.dumps(errors)))
        self.update_setting("last_scan", now)

    def latest_scan(self):
        with self.connect() as db:
            row = db.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                result = dict(row)
                result["errors"] = json.loads(result["errors"])
                return result
        return None
