"""Read-only Streamlit Community Cloud entry point (public demo, no SQLite)."""

import streamlit as st

from jobradr.cloud import collect_public
from jobradr.cloud import triveneto_location
from jobradr.companies import COMPANIES

st.set_page_config(page_title="KZ Job Radar · demo online", page_icon="🔎", layout="wide")
st.title("KZ Job Radar")
st.caption("Demo online · area di Padova · nessuna candidatura automatica")
st.write("Trova annunci pubblici da alcune fonti e consulta le pagine carriere di aziende del Triveneto.")
st.info("Versione dimostrativa: ricerca solo quando apri la pagina o premi Cerca. Non monitora ogni ora, non salva preferenze, non importa email e non usa GPT. Per il monitoraggio personale usa la versione locale.")


@st.cache_data(ttl=3600, show_spinner=False)
def scan():
    return collect_public()


tab_jobs, tab_companies, tab_method = st.tabs(["Annunci", "Aziende", "Come funziona"])
with tab_jobs:
    st.button("Mostra annunci disponibili", type="primary", help="Le fonti sono aggiornate al massimo una volta ogni ora: i risultati possono provenire dalla cache.")
    with st.spinner("Controllo le fonti pubbliche..."):
        jobs, errors = scan()
    if errors:
        st.warning("Alcune fonti non hanno risposto: " + ", ".join(errors))
    area = st.selectbox("Dove cercare", ["Triveneto", "Tutte le sedi"],
                        help="Solo le offerte con località esplicitamente indicata nel Triveneto entrano nel primo filtro. Le altre, incluse quelle da remoto o con località ignota, sono disponibili in «Tutte le sedi».")
    in_area = [job for job in jobs if area == "Tutte le sedi" or triveneto_location(job["location"])]
    col1, col2, col3 = st.columns(3)
    col1.metric("Annunci letti dalle fonti", len(jobs))
    col2.metric("Ruoli da valutare nell'area", sum(j["score"] >= 40 for j in in_area))
    col3.metric("Con data fonte entro 24 h nell'area", sum(j["freshness"] == "Data della fonte entro 24 ore" for j in in_area))
    minimum = st.select_slider("Rilevanza minima", options=[0, 40, 75], value=40,
                               format_func=lambda n: {0: "Tutti", 40: "Da valutare", 75: "Alta"}[n])
    when = st.selectbox("Data", ["Ultime 24 h o data ignota", "Tutti", "Solo 24 h verificati"])
    shown = []
    for job in in_area:
        if job["score"] < minimum:
            continue
        if when == "Solo 24 h verificati" and job["freshness"] != "Data della fonte entro 24 ore":
            continue
        if when == "Ultime 24 h o data ignota" and job["freshness"] not in (
            "Data della fonte entro 24 ore", "Data di pubblicazione non disponibile"
        ):
            continue
        shown.append(job)
    st.caption(f"{len(shown)} annunci nel filtro · i primi 50 sono mostrati · la data della fonte può differire dalla prima pubblicazione")
    if not shown:
        st.write("Nessun risultato in questo filtro. Le fonti automatiche sono ancora poche: prova «Tutte le sedi» oppure consulta la scheda Aziende per cercare sui loro siti ufficiali.")
    for job in shown[:50]:
        with st.container(border=True):
            st.subheader(job["title"])
            st.caption(f"{job['company']} · {job['location']} · {job['source']} · {job['score']}/100")
            st.write(f"{job['freshness']}. {job['location_note']}")
            st.write(job["reason"])
            if job["url"].startswith("https://"):
                st.link_button("Apri annuncio originale ↗", job["url"])

with tab_companies:
    st.write("Pagine ufficiali verificate il 28 settembre 2026. Solo due bacheche sono lette automaticamente; le altre vanno consultate. Le sedi indicate non sono necessariamente quelle di ogni offerta.")
    search = st.text_input("Filtra per azienda o località", placeholder="Padova, Treviso, e-commerce...").casefold()
    for company in COMPANIES:
        if search and search not in (company["name"] + " " + company["area"]).casefold():
            continue
        with st.container(border=True):
            st.write(f"**{company['name']}** · {company['area']}")
            st.caption(company.get("note") or ("Bacheca seguita nella demo" if company["automatic"] else "Pagina da consultare manualmente"))
            st.link_button("Apri pagina carriere ↗", company["url"])

with tab_method:
    st.write("Fonti lette: Arbeitnow (prime due pagine), bacheche Greenhouse AutoScout24 e Lovable. Il resto è un elenco di link verificati e non viene letto automaticamente.")
    st.write("Il punteggio mette prima i titoli coerenti con e-commerce, marketing e lavoro d'ufficio e dà preferenza alle località vicine a Padova. Non è una probabilità di assunzione. Verifica sempre sede, RAL, pubblicazione e requisiti sulla pagina originale.")
    st.write("I dati vengono recuperati quando apri o aggiorni l'app, con una cache massima di un'ora condivisa tra visite. Streamlit Community Cloud può sospendere l'app quando non è utilizzata. Non caricare qui CV, alert email o chiavi personali.")
