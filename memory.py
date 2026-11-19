# Copyright (C) 2026 Enrico Miot
# Licensed under GNU GPL v3 or later — see /usr/share/common-licenses/GPL-3
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path
from datetime import datetime

# ─── Costanti ─────────────────────────────────────────────────────────────────

# Il file di memoria si trova nella stessa cartella dello script (non in SkFiles_home),
# così l'AI non può accedervi né eliminarlo per sbaglio durante le operazioni sui file.
MEMORY_FILE = Path(__file__).parent / ".SkFiles_memory.json"

# Struttura di default della memoria
_DEFAULT_MEMORY: dict = {
    "user": {
        "name": None,
        "preferences": [],
        "facts": []
    },
    "context": {
        "last_topic": None,
        "ongoing_tasks": []
    },
    "history_summary": None,
    "last_updated": None
}

# System prompt per il memory extractor (separato dal chat system per non confondere il modello)
_MEMORY_SYSTEM = """You are a memory extractor. Analyze the conversation and extract ONLY new, durable facts worth remembering long-term.

Reply ONLY with a valid JSON object using this exact structure (omit keys if nothing new):
{
  "user_name": "name if mentioned",
  "new_preferences": ["preference1", "preference2"],
  "new_facts": ["fact1", "fact2"],
  "last_topic": "main topic of this exchange",
  "new_ongoing_tasks": ["task description if something was started but not finished"],
  "completed_tasks": ["task description if something was completed"],
  "history_summary_update": "one sentence summarizing what happened"
}

Rules:
- Extract ONLY facts explicitly stated by the user (not inferred)
- Do NOT repeat facts already in memory
- Do NOT store file names unless they are part of a long-term project
- Preferences: things like "user likes .md files", "user wants short replies"
- Facts: things like "user's name is X", "user is building Y project", "user speaks Italian"
- Ongoing tasks: things started but not finished in this session
- If nothing new was learned, reply with: {}
"""


# ─── Load / Save ──────────────────────────────────────────────────────────────

def load_memory() -> dict:
    """
    Carica la memoria da disco. Se il file non esiste o è corrotto,
    restituisce la struttura di default.
    """
    if not MEMORY_FILE.exists():
        return _build_fresh_memory()

    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        # Merge con default per garantire che tutte le chiavi esistano
        merged = _build_fresh_memory()
        _deep_merge(merged, data)
        return merged
    except (json.JSONDecodeError, Exception):
        print("  [memory] File corrotto, ripart da zero.")
        return _build_fresh_memory()


def save_memory(memory: dict) -> None:
    """
    Salva la memoria su disco in formato JSON leggibile.
    Crea la cartella genitore se non esiste.
    """
    memory["last_updated"] = datetime.now().isoformat(timespec="seconds")
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(
        json.dumps(memory, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ─── Memory → System Prompt ───────────────────────────────────────────────────

def memory_to_context(memory: dict) -> str:
    """
    Converte la memoria in un blocco di testo da iniettare nel system prompt.
    Restituisce stringa vuota se la memoria è completamente vuota.
    """
    lines = []

    user = memory.get("user", {})
    if user.get("name"):
        lines.append(f"- User's name: {user['name']}")
    if user.get("preferences"):
        lines.append("- User preferences: " + "; ".join(user["preferences"]))
    if user.get("facts"):
        lines.append("- Known facts about the user: " + "; ".join(user["facts"]))

    ctx = memory.get("context", {})
    if ctx.get("last_topic"):
        lines.append(f"- Last topic discussed: {ctx['last_topic']}")
    if ctx.get("ongoing_tasks"):
        lines.append("- Ongoing tasks: " + "; ".join(ctx["ongoing_tasks"]))

    if memory.get("history_summary"):
        lines.append(f"- Previous sessions summary: {memory['history_summary']}")

    if not lines:
        return ""

    return "--- SkFiles's memory (from previous sessions) ---\n" + "\n".join(lines) + "\n---"


# ─── Memory Update ────────────────────────────────────────────────────────────

def update_memory(memory: dict, user_input: str, assistant_reply: str, ask_ollama_fn) -> dict:
    """
    Analizza lo scambio user/assistant e aggiorna la memoria con nuovi fatti.

    Parametri:
        memory          : dizionario memoria corrente
        user_input      : messaggio dell'utente in questo turno
        assistant_reply : risposta di SkFiles in questo turno
        ask_ollama_fn   : funzione ask_ollama da main.py (passata per evitare import ciclici)

    Restituisce il dizionario memoria aggiornato (modificato in-place e restituito).
    """
    # Prepara il contesto per il memory extractor
    current_memory_str = json.dumps(memory, ensure_ascii=False, indent=2)

    msgs = [
        {"role": "system", "content": _MEMORY_SYSTEM},
        {"role": "user", "content": (
            f"Current memory:\n{current_memory_str}\n\n"
            f"New exchange:\n"
            f"User: {user_input}\n"
            f"SkFiles: {assistant_reply[:500]}"  # tronca per non sprecare token
        )},
    ]

    raw = ask_ollama_fn(msgs, temperature=0.0, max_tokens=300)

    # Rimuovi eventuali backtick markdown
    raw = raw.strip().strip("`").strip()
    if raw.startswith("json"):
        raw = raw[4:].strip()

    try:
        updates = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return memory  # nessun aggiornamento se il modello non risponde con JSON valido

    if not updates:
        return memory  # {} → niente di nuovo

    # Applica gli aggiornamenti
    user_mem = memory.setdefault("user", {})
    ctx_mem  = memory.setdefault("context", {})

    if updates.get("user_name") and not user_mem.get("name"):
        user_mem["name"] = updates["user_name"]

    if updates.get("new_preferences"):
        existing = set(user_mem.get("preferences") or [])
        for p in updates["new_preferences"]:
            if p not in existing:
                user_mem.setdefault("preferences", []).append(p)

    if updates.get("new_facts"):
        existing = set(user_mem.get("facts") or [])
        for f in updates["new_facts"]:
            if f not in existing:
                user_mem.setdefault("facts", []).append(f)

    if updates.get("last_topic"):
        ctx_mem["last_topic"] = updates["last_topic"]

    if updates.get("new_ongoing_tasks"):
        existing = set(ctx_mem.get("ongoing_tasks") or [])
        for t in updates["new_ongoing_tasks"]:
            if t not in existing:
                ctx_mem.setdefault("ongoing_tasks", []).append(t)

    if updates.get("completed_tasks"):
        completed = set(updates["completed_tasks"])
        ctx_mem["ongoing_tasks"] = [
            t for t in (ctx_mem.get("ongoing_tasks") or [])
            if t not in completed
        ]

    if updates.get("history_summary_update"):
        old = memory.get("history_summary") or ""
        new_bit = updates["history_summary_update"]
        if old:
            # Mantieni le ultime 3 frasi per non crescere all'infinito
            sentences = [s.strip() for s in (old + " " + new_bit).split(".") if s.strip()]
            memory["history_summary"] = ". ".join(sentences[-3:]) + "."
        else:
            memory["history_summary"] = new_bit

    return memory


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_fresh_memory() -> dict:
    """Restituisce una copia fresh della struttura di default."""
    import copy
    return copy.deepcopy(_DEFAULT_MEMORY)


def _deep_merge(base: dict, override: dict) -> None:
    """Merge ricorsivo: override sovrascrive base in-place."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


# ─── CLI test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mem = load_memory()
    print("Memoria corrente:")
    print(json.dumps(mem, ensure_ascii=False, indent=2))
    print("\nContesto iniettabile:")
    print(memory_to_context(mem))
