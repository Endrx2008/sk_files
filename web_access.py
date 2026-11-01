# Copyright (C) 2026 Enrico Miot
# Licensed under GNU GPL v3 or later — see /usr/share/common-licenses/GPL-3
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import requests


# ─── Costanti ─────────────────────────────────────────────────────────────────

# Endpoint JSON di DuckDuckGo (instant answers, tipo Wikipedia)
DDGO_API_URL  = "https://api.duckduckgo.com/"

# Endpoint HTML di DuckDuckGo (risultati di ricerca normali)
DDGO_HTML_URL = "https://html.duckduckgo.com/html/"

# Quanti risultati mostrare al massimo (per non sovraccaricare il modello)
MAX_RESULTS = 5

# User-Agent: ci presentiamo come un browser normale, altrimenti DDG ci blocca
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ─── Livello 1: API JSON ───────────────────────────────────────────────────────

def _search_json(query: str) -> list[str]:
    """
    Interroga l'API JSON di DuckDuckGo.
    Restituisce una lista di stringhe con i risultati, oppure [] se non trova nulla.
    """
    params = {
        "q": query.strip(),
        "format": "json",
        "no_redirect": "1",
        "no_html": "1",
    }
    response = requests.get(DDGO_API_URL, params=params, headers=HEADERS, timeout=10)
    response.raise_for_status()
    data = response.json()

    risultati = []

    # AbstractText = riassunto diretto (es. da Wikipedia)
    abstract = data.get("AbstractText", "").strip()
    abstract_source = data.get("AbstractSource", "")
    if abstract:
        risultati.append(f"📖 [{abstract_source}] {abstract}")

    # RelatedTopics = argomenti correlati
    for topic in data.get("RelatedTopics", []):
        if "Text" not in topic:
            continue
        testo = topic.get("Text", "").strip()
        url   = topic.get("FirstURL", "")
        if testo:
            risultati.append(f"• {testo}  →  {url}")
        if len(risultati) >= MAX_RESULTS:
            break

    return risultati


# ─── Livello 2: scraping HTML ─────────────────────────────────────────────────

def _search_html(query: str) -> list[str]:
    """
    Fa scraping della pagina HTML di DuckDuckGo come fallback.
    Estrae titoli e snippet dei risultati organici.
    Restituisce una lista di stringhe, oppure [] se non trova nulla.
    """
    params = {"q": query.strip(), "kl": "it-it"}
    response = requests.post(DDGO_HTML_URL, data=params, headers=HEADERS, timeout=10)
    response.raise_for_status()
    html = response.text

    risultati = []

    # Estrae i blocchi risultato: ogni risultato è dentro <div class="result__body">
    # Titolo:   <a class="result__a" href="...">TITOLO</a>
    # Snippet:  <a class="result__snippet">TESTO</a>
    titoli   = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
    urls     = re.findall(r'result__url[^>]*>\s*(.*?)\s*<', html)

    # Puliamo l'HTML residuo (tag, &amp; ecc.)
    def strip_html(s: str) -> str:
        s = re.sub(r'<[^>]+>', '', s)
        s = s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&#x27;', "'")
        return s.strip()

    for i in range(min(len(titoli), len(snippets), MAX_RESULTS)):
        titolo  = strip_html(titoli[i])
        snippet = strip_html(snippets[i])
        url     = urls[i].strip() if i < len(urls) else ""
        if titolo and snippet:
            risultati.append(f"• {titolo}\n  {snippet}\n  → {url}")

    return risultati


# ─── Funzione principale ───────────────────────────────────────────────────────

def web_search(query: str) -> str:
    """
    Esegue una ricerca su DuckDuckGo e restituisce i risultati come stringa.
    Prima prova l'API JSON; se non trova nulla, usa lo scraping HTML.

    Parametri:
        query (str): la cosa da cercare, es. "Pipino il Breve"

    Restituisce:
        str: testo con i risultati della ricerca (o un messaggio di errore)
    """
    if not query or not query.strip():
        return "Errore: devi specificare cosa cercare."

    try:
        # ── Tentativo 1: API JSON ──────────────────────────────────────────────
        risultati = _search_json(query)

        # ── Tentativo 2: scraping HTML (fallback) ──────────────────────────────
        if not risultati:
            print("  [web] API JSON vuota, provo scraping HTML...")
            risultati = _search_html(query)

    except requests.exceptions.ConnectionError:
        return "Errore: nessuna connessione internet disponibile."
    except requests.exceptions.Timeout:
        return "Errore: DuckDuckGo ha impiegato troppo tempo a rispondere."
    except Exception as e:
        return f"Errore durante la ricerca: {e}"

    # ── Nessun risultato trovato nemmeno con l'HTML ────────────────────────────
    if not risultati:
        return (
            f"Nessun risultato trovato per: '{query}'.\n"
            f"Prova con parole chiave diverse o più semplici."
        )

    intestazione = f"🔍 Risultati ricerca per: \"{query}\"\n" + "─" * 40
    return intestazione + "\n" + "\n\n".join(risultati)


# ─── Test rapido (eseguibile direttamente: python web_access.py) ───────────────

if __name__ == "__main__":
    risultato = web_search("Pipino il Breve")
    print(risultato)
