"""Transparent ranking, not a prediction of getting hired."""
import re
import unicodedata
from datetime import datetime, timezone, timedelta

from .profile import CORE_CITIES, EXTENDED_CITIES

BLOCKED = (
    "operaio", "operaia", "magazziniere", "magazziniera", "tornitore", "tornitrice",
    "carrellista", "montatore", "saldatore", "autista", "facchino", "addetto al picking",
    "picker di magazzino", "warehouse worker", "forklift", "machine operator", "production worker",
    "door to door", "porta a porta", "agente porta a porta", "provvigioni pure",
)
ROLE_GROUPS = (
    ("e-commerce e marketplace", 42, ("e-commerce", "ecommerce", "marketplace", "shopify", "catalog specialist", "catalogo prodotti", "digital merchandising")),
    ("marketing digitale", 34, ("digital marketing", "marketing specialist", "seo", "paid media", "google ads", "social media specialist", "content specialist")),
    ("back office e vendite", 32, ("back office", "back-office", "sales support", "sales operations", "commerciale interno", "customer service", "customer care", "order management", "ufficio vendite")),
    ("amministrazione d'ufficio", 20, ("impiegato", "impiegata", "amministrativ", "segreteri", "office assistant", "office coordinator")),
    ("logistica d'ufficio", 27, ("logistics coordinator", "supply chain analyst", "logistic specialist", "ufficio logistica", "gestione spedizioni", "inventory analyst")),
    ("analisi dati", 29, ("data analyst", "business analyst", "analista dati", "kpi analyst")),
)
SKILL_TERMS = ("shopify", "woocommerce", "prestashop", "amazon seller", "ebay", "meta ads", "google ads", "excel", "seo", "customer support", "catalogo", "ordini", "kpi", "inventory", "english", "inglese")


def norm(value):
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(x for x in value if not unicodedata.combining(x))


def has(text, word):
    return bool(re.search(r"(?<!\w)" + re.escape(norm(word)) + r"(?!\w)", norm(text)))


def region(location, remote=False):
    lower = norm(location)
    if any(has(lower, city) for city in CORE_CITIES):
        return "Zona preferita; tragitto in auto da verificare", 12
    if any(has(lower, city) for city in EXTENDED_CITIES):
        return "Zona estesa; tragitto e RAL da verificare", 5
    if remote or has(lower, "remote") or has(lower, "remoto"):
        return "Da remoto; verificare se l'Italia è ammessa", 6
    if not lower or lower in ("italia", "italy", "veneto"):
        return "Località generica; verificare la sede", 0
    return "Fuori zona o sede non riconosciuta; valutare trasferimento", -22


def freshness(published_at, now=None):
    if not published_at:
        return "Data di pubblicazione non disponibile"
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age = (now or datetime.now(timezone.utc)) - published
        if -timedelta(minutes=10) <= age <= timedelta(hours=24):
            return "Data della fonte entro 24 ore"
        if age < -timedelta(minutes=10):
            return "Data futura: verificare la fonte"
        return "Data della fonte oltre 24 ore fa"
    except ValueError:
        return "Data di pubblicazione non disponibile"


def rank(job):
    title, desc = norm(job.title), norm(job.description)
    for word in BLOCKED:
        if has(title, word):
            return {"score": 0, "category": "Escluso: lavoro manuale/vendita non desiderata",
                    "reason": f"Titolo escluso: {word}", "location_note": region(job.location, job.remote)[0]}
    matches = [(label, points) for label, points, terms in ROLE_GROUPS if any(has(title, term) for term in terms)]
    if not matches:
        # Description-only hints must not turn a manual or unrelated job into a high-scoring match.
        if job.source in ("LinkedIn Alert", "Indeed Alert"):
            return {"score": 40, "category": "Alert da verificare", "reason": "L'email non contiene informazioni sufficienti per valutare il ruolo: apri l'annuncio originale.",
                    "location_note": "Sede e tempi di viaggio da verificare"}
        return {"score": 10, "category": "Da verificare", "reason": "Il titolo non indica una mansione obiettivo",
                "location_note": region(job.location, job.remote)[0]}
    label, points = max(matches, key=lambda row: row[1])
    skills = [term for term in SKILL_TERMS if has(desc, term)]
    loc_note, loc_points = region(job.location, job.remote)
    score = max(0, min(95, 32 + points + min(len(skills), 4) * 3 + loc_points))
    explanation = f"Ruolo: {label}. " + (f"Competenze citate: {', '.join(skills[:4])}. " if skills else "Competenze specifiche non verificabili. ")
    explanation += "RAL non verificata; nessuna stima di stipendio o probabilità di assunzione."
    return {"score": score, "category": label, "reason": explanation, "location_note": loc_note}
