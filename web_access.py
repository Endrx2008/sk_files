# Copyright (C) 2026 Enrico Miot
# Licensed under GNU GPL v3 or later — see the LICENSE file or <https://www.gnu.org/licenses/>
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import requests


# ─── Constants ────────────────────────────────────────────────────────────────

# DuckDuckGo JSON endpoint (instant answers, e.g. from Wikipedia)
DDGO_API_URL  = "https://api.duckduckgo.com/"

# DuckDuckGo HTML endpoint (normal search results)
DDGO_HTML_URL = "https://html.duckduckgo.com/html/"

# At most this many results (more would only fill the model's context)
MAX_RESULTS = 5

# User-Agent of a normal browser: DuckDuckGo blocks unknown clients
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ─── Level 1: JSON API ────────────────────────────────────────────────────────

def _search_json(query: str) -> list[str]:
    """
    Asks DuckDuckGo's JSON API. Returns the results as strings, [] for none.
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

    results = []

    # AbstractText = a direct summary (e.g. from Wikipedia)
    abstract = data.get("AbstractText", "").strip()
    abstract_source = data.get("AbstractSource", "")
    if abstract:
        results.append(f"📖 [{abstract_source}] {abstract}")

    # RelatedTopics = related subjects
    for topic in data.get("RelatedTopics", []):
        if "Text" not in topic:
            continue
        text = topic.get("Text", "").strip()
        url  = topic.get("FirstURL", "")
        if text:
            results.append(f"• {text}  →  {url}")
        if len(results) >= MAX_RESULTS:
            break

    return results


# ─── Level 2: HTML page ───────────────────────────────────────────────────────

def _search_html(query: str) -> list[str]:
    """
    Fallback: reads DuckDuckGo's HTML results page (titles and snippets of
    the organic results). Returns the results as strings, [] for none.
    """
    params = {"q": query.strip(), "kl": "wt-wt"}  # wt-wt: no region
    response = requests.post(DDGO_HTML_URL, data=params, headers=HEADERS, timeout=10)
    response.raise_for_status()
    html = response.text

    results = []

    # Every result is inside <div class="result__body">:
    # Title:    <a class="result__a" href="...">TITLE</a>
    # Snippet:  <a class="result__snippet">TEXT</a>
    titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
    urls     = re.findall(r'result__url[^>]*>\s*(.*?)\s*<', html)

    # Remove what is left of the HTML (tags, &amp; …)
    def strip_html(s: str) -> str:
        s = re.sub(r'<[^>]+>', '', s)
        s = s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&#x27;', "'")
        return s.strip()

    for i in range(min(len(titles), len(snippets), MAX_RESULTS)):
        title   = strip_html(titles[i])
        snippet = strip_html(snippets[i])
        url     = urls[i].strip() if i < len(urls) else ""
        if title and snippet:
            results.append(f"• {title}\n  {snippet}\n  → {url}")

    return results


# ─── Main function ────────────────────────────────────────────────────────────

def web_search(query: str) -> str:
    """
    Searches DuckDuckGo and returns the results as text: the JSON API first,
    the HTML page when the API has nothing.

    query: what to look for, e.g. "Pepin the Short"
    Returns the results, or an error message.
    """
    if not query or not query.strip():
        return "Error: say what to search for."

    try:
        # ── Attempt 1: JSON API ────────────────────────────────────────────────
        results = _search_json(query)

        # ── Attempt 2: HTML page (fallback) ────────────────────────────────────
        if not results:
            print("  [web] the JSON API had nothing, trying the HTML page...")
            results = _search_html(query)

    except requests.exceptions.ConnectionError:
        return "Error: no internet connection."
    except requests.exceptions.Timeout:
        return "Error: DuckDuckGo took too long to answer."
    except Exception as e:
        return f"Error while searching: {e}"

    # ── Nothing found, not even on the HTML page ───────────────────────────────
    if not results:
        return (
            f"No results for: '{query}'.\n"
            f"Try different or simpler keywords."
        )

    header = f"🔍 Search results for: \"{query}\"\n" + "─" * 40
    return header + "\n" + "\n\n".join(results)


# ─── Quick test: python3 web_access.py ────────────────────────────────────────

if __name__ == "__main__":
    print(web_search("Pepin the Short"))
