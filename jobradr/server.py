import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .alerts import parse_alert
from .ai import analyze
from .companies import COMPANIES
from .engine import Engine
from .model import Job, plain
from .scoring import freshness
from .sources import SLUG
from .storage import Store

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "jobs.sqlite3"
PAGE_PATH = Path(__file__).resolve().parent.parent / "web" / "index.html"


def create_handler(store, engine):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send_json(self, data, status=200):
            content = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            route = self.path.split("?", 1)[0]
            if route in ("/", "/style.css", "/app.js"):
                path = PAGE_PATH if route == "/" else PAGE_PATH.parent / route.lstrip("/")
                content = path.read_bytes()
                self.send_response(200)
                mime = {"/": "text/html", "/style.css": "text/css", "/app.js": "text/javascript"}[route]
                self.send_header("Content-Type", mime + "; charset=utf-8")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            elif route == "/api/state":
                rows = store.jobs()
                for row in rows:
                    row["freshness"] = freshness(row["published_at"])
                    row["description"] = row["description"][:1200]
                self.send_json({"jobs": rows, "settings": {key: store.setting(key) for key in (
                    "monitoring_enabled", "ai_enabled", "feed_enabled", "boards")},
                    "scan": store.latest_scan(), "active": engine.active})
            elif route == "/api/companies":
                self.send_json({"companies": COMPANIES})
            else:
                self.send_json({"error": "Indirizzo non trovato"}, 404)

        def do_POST(self):
            if self.headers.get("X-Job-Radar") != "local":
                return self.send_json({"error": "Richiesta locale non valida"}, 403)
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                return self.send_json({"error": "Origine non valida"}, 403)
            try:
                route = self.path.split("?", 1)[0]
                length = int(self.headers.get("Content-Length", "0"))
                limit = 800_000 if route == "/api/alerts/import" else 40_000
                if length < 1 or length > limit:
                    raise ValueError("Dimensione richiesta non valida")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("Dati non validi")
                if route == "/api/scan":
                    result = {"started": engine.start_scan()}
                elif route == "/api/settings":
                    name = body.get("name")
                    if name not in ("monitoring_enabled", "ai_enabled", "feed_enabled") or not isinstance(body.get("value"), bool):
                        raise ValueError("Impostazione non valida")
                    store.update_setting(name, body["value"])
                    result = {"ok": True}
                elif route == "/api/boards":
                    typ = body.get("type", "")
                    slug = body.get("slug", "")
                    if typ not in ("greenhouse", "lever", "lever_eu") or not isinstance(slug, str) or not SLUG.fullmatch(slug):
                        raise ValueError("Scegli Greenhouse/Lever e inserisci il codice dell'azienda")
                    boards = store.setting("boards") or []
                    candidate = {"type": typ, "slug": slug}
                    if candidate not in boards:
                        boards.append(candidate)
                    if len(boards) > 30:
                        raise ValueError("Massimo 30 aziende")
                    store.update_setting("boards", boards)
                    result = {"ok": True}
                elif route == "/api/boards/remove":
                    boards = store.setting("boards") or []
                    store.update_setting("boards", [b for b in boards if b != {"type": body.get("type"), "slug": body.get("slug")}])
                    result = {"ok": True}
                elif route == "/api/manual":
                    url = str(body.get("url", "")).strip()
                    parsed = urlparse(url)
                    if parsed.scheme != "https" or not parsed.netloc or len(url) > 1000:
                        raise ValueError("Serve un link HTTPS valido")
                    title = str(body.get("title", "")).strip()[:200]
                    if not title:
                        raise ValueError("Inserisci il titolo dell'annuncio")
                    job = Job("Manuale", url, title, str(body.get("company", ""))[:150],
                              str(body.get("location", ""))[:150], url, plain(body.get("description", "")))
                    store.upsert(job)
                    result = {"ok": True}
                elif route == "/api/alerts/import":
                    raw = body.get("eml")
                    if not isinstance(raw, str):
                        raise ValueError("Seleziona un'email .eml valida")
                    jobs = parse_alert(raw)
                    for job in jobs:
                        store.upsert(job)
                    result = {"imported": len(jobs)}
                elif route == "/api/status":
                    result = {"ok": store.change_status(body.get("id"), body.get("status"))}
                elif route == "/api/analyze":
                    if not store.setting("ai_enabled"):
                        raise ValueError("Attiva prima la modalità GPT")
                    job = store.job(body.get("id"))
                    if not job:
                        raise ValueError("Annuncio non trovato")
                    note = analyze(job)
                    store.save_ai_note(job["id"], note)
                    result = {"note": note}
                else:
                    return self.send_json({"error": "Indirizzo non trovato"}, 404)
                return self.send_json(result)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                return self.send_json({"error": str(exc)}, 400)
            except Exception as exc:
                return self.send_json({"error": f"Operazione non riuscita ({type(exc).__name__}). Controlla rete/chiave API."}, 502)
    return Handler


def serve(port=8765, db_path=DATA_PATH):
    store = Store(db_path)
    engine = Engine(store)
    stop = threading.Event()
    monitor = threading.Thread(target=engine.monitor, args=(stop,), daemon=True)
    monitor.start()
    server = ThreadingHTTPServer(("127.0.0.1", port), create_handler(store, engine))
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        stop.set()
        server.server_close()
