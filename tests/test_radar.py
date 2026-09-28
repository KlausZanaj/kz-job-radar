import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from jobradr import sources
from jobradr.alerts import parse_alert
from jobradr.cloud import collect_public, triveneto_location
from jobradr.companies import COMPANIES
from jobradr.engine import Engine
from jobradr.model import Job, date_utc, plain
from jobradr.scoring import freshness, rank
from jobradr.server import create_handler
from jobradr.storage import Store


def job(title="E-commerce Specialist", location="Padova", description="Shopify catalogo ordini"):
    return Job("test", "1", title, "Azienda test", location, "https://example.org/jobs/1", description)


class RankingTests(unittest.TestCase):
    def test_manual_logistics_excluded(self):
        self.assertEqual(rank(job("Operaio logistico e-commerce", description="Shopify ordini"))["score"], 0)

    def test_office_logistics_not_excluded(self):
        self.assertGreaterEqual(rank(job("Logistics Coordinator"))["score"], 40)

    def test_unrelated_marked_uncertain(self):
        self.assertEqual(rank(job("Chef di cucina", description="Shopify marketplace"))["score"], 10)

    def test_matching_location_priority(self):
        self.assertGreater(rank(job(location="Treviso"))["score"], rank(job(location="Berlin"))["score"])

    def test_freshness_unknown_and_verified(self):
        now = datetime.now(timezone.utc)
        self.assertIn("non disponibile", freshness(None))
        self.assertIn("24 ore", freshness((now-timedelta(hours=3)).isoformat(), now))
        self.assertIn("oltre 24", freshness((now-timedelta(hours=26)).isoformat(), now))

    def test_safe_description_and_dates(self):
        self.assertEqual(plain("<b>Shopify</b> &amp; ordini"), "Shopify & ordini")
        self.assertIsNotNone(date_utc(1720000000))
        self.assertIsNone(date_utc("not-a-date"))


class FeedTests(unittest.TestCase):
    def test_arbeitnow_parsing(self):
        fake = lambda url: {"data": [{"slug": "id", "title": "Ecommerce", "company_name": "A", "location": "Padova", "url": "https://example.org/a", "description": "<p>Shopify</p>", "created_at": 1720000000}]}
        result = list(sources.arbeitnow(fake, pages=1))
        self.assertEqual(result[0].description, "Shopify")
        self.assertIsNotNone(result[0].published_at)

    def test_greenhouse_update_is_not_publication(self):
        fake = lambda url: {"jobs": [{"id": 7, "internal_job_id": 8, "title": "Catalog manager", "updated_at": datetime.now(timezone.utc).isoformat(), "location": {"name":"Padova"}, "absolute_url": "https://example.org/a"}]}
        result = list(sources.greenhouse("demo", fake))
        self.assertIsNone(result[0].published_at)

    def test_slug_validation(self):
        with self.assertRaises(ValueError):
            list(sources.lever("../../secret", lambda url: []))

    def test_adzuna_no_key_does_not_fetch(self):
        with patch.dict("os.environ", {"ADZUNA_APP_ID": "", "ADZUNA_APP_KEY": ""}):
            self.assertEqual(list(sources.adzuna(lambda url: self.fail("called"))), [])

    def test_adzuna_budget_and_attribution(self):
        calls = []
        def fake(url):
            calls.append(url)
            return {"results": [{"id": "52", "title": "Back office", "redirect_url": "https://adzuna.it/example", "created":"2026-09-28T12:00:00Z", "company":{"display_name":"Demo"}, "location":{"display_name":"Padova"}}]}
        with patch.dict("os.environ", {"ADZUNA_APP_ID": "test", "ADZUNA_APP_KEY": "test"}):
            results = list(sources.adzuna(fake))
        self.assertEqual(len(calls), 3)
        self.assertEqual(results[0].source, "Adzuna")


class AlertTests(unittest.TestCase):
    def test_extracts_direct_links_only_and_deduplicates(self):
        raw = ('From: alerts@example.org\nSubject: Nuove offerte a Padova\n'
               'MIME-Version: 1.0\nContent-Type: text/html; charset=utf-8\n\n'
               '<a href="https://www.linkedin.com/jobs/view/123456/?trackingId=secret">'
               'E-commerce Specialist</a><a href="https://www.linkedin.com/jobs/view/123456/">Vedi</a>'
               '<a href="https://it.indeed.com/viewjob?jk=abcdef1234&amp;from=alert">Back office commerciale</a>'
               '<a href="https://example.org/jobs/view/55555">Fake</a>')
        jobs = parse_alert(raw)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].url, 'https://www.linkedin.com/jobs/view/123456/')
        self.assertEqual(jobs[0].title, 'E-commerce Specialist')
        self.assertEqual(jobs[1].url, 'https://it.indeed.com/viewjob?jk=abcdef1234')
        self.assertIsNone(jobs[0].published_at)

    def test_does_not_follow_tracking_redirects(self):
        self.assertEqual(parse_alert('Subject: Offerte\n\nhttps://tracking.example.org/click?url=https://www.linkedin.com/jobs/view/12345/'), [])


class CloudTests(unittest.TestCase):
    def test_triveneto_filter_rejects_foreign_remote_and_unknown_locations(self):
        self.assertTrue(triveneto_location("Padova, Veneto"))
        self.assertTrue(triveneto_location("Mestre (VE)"))
        self.assertTrue(triveneto_location("Trieste, Friuli Venezia Giulia"))
        self.assertFalse(triveneto_location("Berlin, remote"))
        self.assertFalse(triveneto_location("London"))
        self.assertFalse(triveneto_location("Remote"))
        self.assertFalse(triveneto_location(""))

    def test_public_scan_handles_failed_board_and_excludes_manual_job(self):
        fresh = job("E-commerce Specialist", "Padova")
        with patch.object(sources, "arbeitnow", return_value=[fresh]), \
             patch.object(sources, "greenhouse", side_effect=[ValueError("rete"), []]):
            rows, errors = collect_public()
        self.assertEqual(len(rows), 1)
        self.assertGreaterEqual(rows[0]["score"], 40)
        self.assertEqual(errors, ["Greenhouse/autoscout24: ValueError"])

    def test_company_directory_links_official_and_not_all_auto(self):
        self.assertGreaterEqual(len(COMPANIES), 12)
        self.assertEqual(sum(c["automatic"] for c in COMPANIES), 2)
        self.assertTrue(all(c["url"].startswith("https://") for c in COMPANIES))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.dir.name)/"jobs.db")

    def tearDown(self):
        self.dir.cleanup()

    def test_upsert_preserves_user_status(self):
        self.store.upsert(job())
        self.assertTrue(self.store.change_status("test:1", "Interessante"))
        self.store.upsert(job(title="Nuovo titolo"))
        item = self.store.jobs()[0]
        self.assertEqual(item["status"], "Interessante")
        self.assertEqual(item["title"], "Nuovo titolo")

    def test_monitor_default_off_and_ai_off(self):
        self.assertFalse(self.store.setting("monitoring_enabled"))
        self.assertFalse(self.store.setting("ai_enabled"))
        engine = Engine(self.store)
        stop = threading.Event()
        stop.set()
        engine.monitor(stop)
        self.assertIsNone(self.store.latest_scan())

    def test_two_example_boards_default(self):
        self.assertEqual([b['slug'] for b in self.store.setting('boards')], ['autoscout24', 'lovable'])

    def test_one_feed_failure_does_not_stop_other(self):
        engine = Engine(self.store)
        with patch.object(sources, "arbeitnow", side_effect=ValueError("rete assente")), \
             patch.object(sources, "greenhouse", return_value=[]):
            engine.scan()
        self.assertEqual(len(self.store.latest_scan()["errors"]), 1)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.dir.name)/"jobs.db")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.store, Engine(self.store)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.dir.cleanup()

    def request(self, path, body, token=True):
        headers = {"Content-Type":"application/json"}
        if token:
            headers["X-Job-Radar"]="local"
        with urlopen(Request(self.base+path, data=json.dumps(body).encode(), headers=headers, method="POST"),timeout=3) as response:
            return json.load(response)

    def test_server_and_manual_announcements(self):
        with urlopen(self.base+"/", timeout=3) as response:
            self.assertIn(b"KZ Job Radar",response.read())
        self.request("/api/manual", {"url":"https://example.org/job","title":"E-commerce Specialist","location":"Padova"})
        with urlopen(self.base+"/api/state", timeout=3) as response:
            data=json.load(response)
        self.assertEqual(len(data["jobs"]),1)
        self.assertEqual(data["jobs"][0]["freshness"],"Data di pubblicazione non disponibile")

    def test_company_directory_endpoint(self):
        with urlopen(self.base+"/api/companies", timeout=3) as response:
            data=json.load(response)
        self.assertEqual(len(data["companies"]),len(COMPANIES))

    def test_no_cross_origin_or_unauthorized_post(self):
        with self.assertRaises(HTTPError) as result:
            self.request("/api/settings",{"name":"ai_enabled","value":True},token=False)
        self.assertEqual(result.exception.code,403)
        request=Request(self.base+"/api/settings",data=b'{"name":"ai_enabled","value":true}',headers={"X-Job-Radar":"local","Origin":"https://elsewhere.invalid"},method="POST")
        with self.assertRaises(HTTPError) as result:
            urlopen(request,timeout=3)
        self.assertEqual(result.exception.code,403)

    def test_ai_cannot_call_when_off(self):
        self.store.upsert(job())
        with self.assertRaises(HTTPError) as result:
            self.request("/api/analyze",{"id":"test:1"})
        self.assertEqual(result.exception.code,400)

    def test_import_alert_keeps_only_canonical_link(self):
        raw = ('From: alert@example.org\nSubject: Offerte a Padova\n\n'
               'https://www.linkedin.com/jobs/view/1234567/?trackingId=secret')
        result = self.request('/api/alerts/import', {'eml': raw})
        self.assertEqual(result['imported'], 1)
        record = self.store.jobs()[0]
        self.assertEqual(record['url'], 'https://www.linkedin.com/jobs/view/1234567/')
        self.assertNotIn('alert@example.org', str(record))
        self.assertIsNone(record['published_at'])
