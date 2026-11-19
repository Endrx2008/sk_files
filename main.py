# Copyright (C) 2026 Enrico Miot
# Licensed under GNU GPL v3 or later — see the LICENSE file or <https://www.gnu.org/licenses/>
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import json
import re
import requests
from pathlib import Path

# ─── UTF-8 terminal fix ───────────────────────────────────────────────────────
# Forces stdin/stdout to use UTF-8 so special characters don't crash the app.
#
# NOTE: use reconfigure() and NOT a new io.TextIOWrapper around sys.stdout.buffer.
# A fresh TextIOWrapper defaults to line_buffering=False, which turns the
# terminal's line-buffered stdout into a block-buffered one: every print()
# would sit in the buffer until the process exits. reconfigure() only changes
# the encoding and leaves the buffering behaviour of the terminal intact.
sys.stdin.reconfigure(encoding="utf-8", errors="replace")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import OLLAMA_URL, SK_FILES_HOME, MAX_FILES, CHAT_SYSTEM, TOOL_NAMES
from memory import load_memory, save_memory, memory_to_context, update_memory

# SKAI_ Memory: the memory shared by all SKAI apps (optional - everything works without it).
try:
    import skai_memory_bridge as _shared
except ImportError:
    _shared = None
_SHARED = None  # opened on first use: this app's handle to the shared memory


def shared_recall(question: str) -> str:
    """What the other SKAI apps know about this question ('' when nothing / not installed)."""
    global _SHARED
    if _shared is None:
        return ""
    if _SHARED is None:
        _SHARED = _shared.open_memory("sk_files") or False
    return _shared.recall_text(_SHARED, question) if _SHARED else ""


def shared_remember(question: str, reply: str) -> None:
    """Keep the exchange in this app's own notes of the shared memory."""
    if _SHARED:
        _shared.remember_turn(_SHARED, "sk_files", question, reply)

# ─── Model selection ─────────────────────────────────────────
# Query the local Ollama API to list all available models and pick
# the heaviest one (largest size on disk) as the best-performing model.
# If Ollama is unreachable or returns no models, sk_files exits cleanly.

def _ai_disabled_exit(detail: str = None) -> None:
    """Called when no model can be selected — sk_files exits cleanly."""
    print()
    print("=" * 57)
    # Same text as every SKAI tool (skcommon.AI_UNAVAILABLE_MESSAGE in the launcher)
    print("  AI features are disabled.")
    print("  It looks like you turned off AI in the SKAI settings.")
    print("  Without a selected model, SKAI cannot function.")
    if detail:
        print(f"  (technical detail: {detail})")
    print()
    print("  Press any key to exit...")
    print("=" * 57)
    # Make sure everything above is actually on screen BEFORE we block on read().
    # Without this the message would only appear once the process terminates.
    sys.stdout.flush()
    try:
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        # Fallback for environments without a raw terminal (pipes, IDE consoles).
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
    sys.exit(0)

_PARAMETERS = re.compile(r"([\d.]+)\s*([KMBT]?)", re.IGNORECASE)
_SCALE = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def _parameter_count(model: dict) -> float:
    """Parameters of one entry of /api/tags ("14.8B", "494.03M"); 0 when unknown."""
    text = str((model.get("details") or {}).get("parameter_size") or "").strip()
    match = _PARAMETERS.match(text)
    if not match:
        return 0.0
    try:
        return float(match.group(1)) * _SCALE[match.group(2).upper()]
    except ValueError:
        return 0.0


def _load_model() -> str:
    """The installed model with the most parameters, like every SKAI tool
    (the size on disk only breaks ties)."""
    ollama_tags_url = "http://localhost:11434/api/tags"
    # The failure reason is only recorded here; _ai_disabled_exit() is called
    # OUTSIDE the try, otherwise any exception raised inside it (e.g. termios
    # on a non-tty stdin) would be swallowed by `except Exception` and trigger
    # a second, misleading call.
    detail = None
    try:
        resp = requests.get(ollama_tags_url, timeout=5)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        if models:
            best = max(models, key=lambda m: (_parameter_count(m), m.get("size", 0) or 0))
            return best["name"]
        detail = "Ollama returned no installed models"
    except requests.exceptions.ConnectionError:
        detail = "could not connect to Ollama at localhost:11434"
    except requests.exceptions.Timeout:
        detail = "Ollama did not respond within 5 seconds"
    except Exception as e:
        detail = str(e)

    _ai_disabled_exit(detail=detail)

MODEL = _load_model()

from fs_create import create_file
from fs_edit   import edit_file
from fs_delete import delete_file, delete_all_files
from fs_rename import rename_file
from fs_read   import read_file, list_files
from fs_dirs   import create_dir, rename_dir, delete_dir, list_dirs, move_dir
from fs_move   import move_file
from web_access import web_search


NOT_DELETED = "Cancelled: the user answered No, nothing was deleted."


def confirm(question: str) -> bool:
    """Every deletion asks the user first; Enter alone means No."""
    try:
        answer = input(f"  ⚠ {question} [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    yes = answer in ("y", "yes", "s", "si", "sì")
    print("  → yes" if yes else "  → no, nothing deleted")
    return yes

# How many times to retry if the model doesn't return valid JSON.
# qwen2.5:14b is good enough that this rarely triggers, but keep it as a safety net.
MAX_RETRIES = 3


# ─── Ollama call ─────────────────────────────────────────────────────────────

def ask_ollama(messages: list, temperature: float = 0.3, max_tokens: int = 600) -> str:
    """Send messages to Ollama and return the raw text response."""
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "").strip()
    except requests.exceptions.ConnectionError:
        return "ERROR: Ollama is not running. Start it with: ollama serve"
    except Exception as e:
        return f"ERROR: {e}"


# ─── Response parsing ─────────────────────────────────────────────────────────

def parse_tool_calls(response: str) -> list[dict] | None:
    """
    Look for one or more valid tool calls inside the model's response.
    Supports two formats:
      - Single:   {"tool": "...", "params": {...}}
      - Multiple: [{"tool": "...", "params": {...}}, ...]

    Returns a list of valid dicts, or None if nothing is found.
    """
    def normalize(data):
        """Lowercase the tool name so CREATE_FILE and create_file both work."""
        if isinstance(data, dict) and "tool" in data:
            data["tool"] = data["tool"].lower()
        return data

    # First try to parse the whole response as pure JSON
    for text in [response.strip(), response.strip().strip("`")]:
        try:
            data = json.loads(text)
            if isinstance(data, list):
                data = [normalize(d) for d in data]
                valid = [d for d in data if isinstance(d, dict) and d.get("tool") in TOOL_NAMES]
                if valid:
                    return valid
            if isinstance(data, dict):
                normalize(data)
                if data.get("tool") in TOOL_NAMES:
                    return [data]
        except json.JSONDecodeError:
            pass

    # If there's surrounding text, extract the JSON block with regex.
    # Try array [...] first, then object {...}
    for pattern in [r'\[[\s\S]*\]', r'\{[\s\S]*\}']:
        match = re.search(pattern, response)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, list):
                    data = [normalize(d) for d in data]
                    valid = [d for d in data if isinstance(d, dict) and d.get("tool") in TOOL_NAMES]
                    if valid:
                        return valid
                if isinstance(data, dict):
                    normalize(data)
                    if data.get("tool") in TOOL_NAMES:
                        return [data]
            except json.JSONDecodeError:
                pass

    return None


def is_echoed_prompt(text: str) -> bool:
    """Detect if the model echoed back the prompt instead of responding."""
    markers = ["Request:", "Files in folder:", "Reply ONLY with JSON", "Single example:"]
    return sum(1 for m in markers if m in text) >= 2


def is_boilerplate(text: str) -> bool:
    """
    Detect 'empty' responses where the model just repeats memorized phrases
    from the system prompt without actually doing anything.
    This was common with smaller models — qwen2.5:14b rarely does this,
    but we keep the check as a safety net.
    """
    phrases = [
        "i'll execute immediately",
        "executing immediately",
        "understood! executing",
        "without asking for confirmation",
        "i'm ready to help",
        "got it, executing",
    ]
    t = text.lower()
    return any(p in t for p in phrases)


# ─── Intent classifier ────────────────────────────────────────────────────────

# A separate, very short system prompt just for the classifier call.
# Keeping it separate means the model doesn't get confused by the main chat history.
_INTENT_SYSTEM = "You are a classifier. Reply ONLY with the word YES or the word NO."

def needs_tool(user_input: str, file_list: str) -> bool:
    """
    Ask the model (with a lightweight call) whether the user's message
    requires a file operation or is just normal chat.
    Returns True if a tool is needed, False for plain conversation.
    """
    msgs = [
        {"role": "system", "content": _INTENT_SYSTEM},
        {"role": "user",   "content": (
            f"The user said: \"{user_input}\"\n"
            f"Is this asking to create, read, edit, rename, or delete files? "
            f"Existing files: {file_list}.\n"
            f"Reply YES if it's a file operation, NO if it's normal conversation."
        )},
    ]
    resp = ask_ollama(msgs, temperature=0.0, max_tokens=10).strip().upper()
    return resp.startswith("YES") or resp == "Y"


# ─── Search query builder ─────────────────────────────────────────────────────

_QUERY_SYSTEM = (
    "You are a search query optimizer. "
    "The user will give you a question or sentence. "
    "Reply with ONLY 2-5 English keywords suitable for a search engine. "
    "No punctuation, no explanation, no extra words. Just the keywords."
)

def build_search_query(user_input: str) -> str:
    """
    Asks the model for 2-5 keywords of the user's question, so that the
    search query is not the whole sentence copied.

    Example:
        input:  "what happened in iran on 01/03/2025?"
        output: "Iran news March 2025"
    """
    msgs = [
        {"role": "system", "content": _QUERY_SYSTEM},
        {"role": "user",   "content": user_input},
    ]
    keywords = ask_ollama(msgs, temperature=0.0, max_tokens=20).strip()
    # Sanity check: over 60 characters the model probably copied the whole
    # sentence again, so only its first 5 words are kept.
    if len(keywords) > 60:
        keywords = " ".join(keywords.split()[:5])
    return keywords


# ─── Main call with JSON retry ────────────────────────────────────────────────

_RETRY_SYSTEM = """You are a JSON generator. Output ONLY a valid JSON array of tool calls. No text, no explanation, no markdown, no code blocks.

ALWAYS use this exact format, even for a single operation:
[{"tool": "tool_name", "params": {...}}]

Available tools and their exact param names:
  create_file  → {"filename": "name.txt", "content": "text"}
  edit_file    → {"filename": "name.txt", "new_content": "text"}
  delete_file  → {"filename": "name.txt"}
  rename_file  → {"old": "old.txt", "new": "new.txt"}
  read_file    → {"filename": "name.txt"}
  move_file    → {"filename": "name.txt", "destination": "foldername"}
  move_dir     → {"dirname": "subfolder", "destination": "parent_folder"}
  create_dir   → {"dirname": "foldername"}
  rename_dir   → {"old": "oldfolder", "new": "newfolder"}
  delete_dir   → {"dirname": "foldername", "force": true}
  list_files   → {}
  list_dirs    → {}
  delete_all   → {}
  web_search   → {"query": "2-5 keyword English query — NEVER copy user's sentence"}

If the user wants N operations, output N objects in the array.
"""

_RETRY_EXAMPLE_MULTI = (
    'Example — create a file in each of 3 folders:\n'
    '[{"tool": "create_file", "params": {"filename": "folder1/note.txt", "content": "hello"}}, '
    '{"tool": "create_file", "params": {"filename": "folder2/note.txt", "content": "hello"}}, '
    '{"tool": "create_file", "params": {"filename": "folder3/note.txt", "content": "hello"}}]'
)


def ask_ollama_with_retry(messages: list, user_input: str, force_tool: bool = False) -> tuple[str, list[dict] | None]:
    """
    Main flow:
    1. First call with the full conversation history → model responds
    2. If already valid JSON → execute immediately
    3. If plain text → ask the model (needs_tool) whether a tool is needed
       - NO  → it's normal chat, return the text as-is
       - YES → retry with a clean JSON-only prompt
    """
    response = ask_ollama(messages)

    if response.startswith("ERROR"):
        return response, None

    # Case 1: valid JSON on the first try
    tool_calls = parse_tool_calls(response)
    if tool_calls:
        return "", tool_calls

    # The first response was plain text. Ask the model if a tool is needed.
    # Pass the full snapshot (files + dirs) so the classifier and retry have full context.
    snapshot = folder_snapshot()

    if not force_tool and not is_boilerplate(response) and not needs_tool(user_input, snapshot):
        return response, None

    # Case 2: a tool is needed (or boilerplate response) → clean JSON retry
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"  [retry {attempt}/{MAX_RETRIES}]...")

        retry_messages = [
            {"role": "system", "content": _RETRY_SYSTEM},
            {"role": "user",   "content": (
                f"Current state of sk_files_home:\n{snapshot}\n\n"
                f"User request: {user_input}\n\n"
                f"{_RETRY_EXAMPLE_MULTI}"
            )},
        ]

        # temperature=0 → maximum determinism, model won't drift into plain text
        response = ask_ollama(retry_messages, temperature=0.0, max_tokens=2000)
        print(f"  [debug] {response[:150]}")

        tool_calls = parse_tool_calls(response)
        if tool_calls:
            return "", tool_calls

        if is_echoed_prompt(response) or is_boilerplate(response):
            continue

    return "I didn't understand the operation. Try to be more specific (e.g. 'create a file called notes.txt')", None


# ─── Tool dispatcher ──────────────────────────────────────────────────────────

def dispatch_tool(tool: str, params: dict) -> str:
    """Call the filesystem function that matches the tool requested by the model."""
    match tool:
        case "list_files":
            return list_files()

        case "read_file":
            return read_file(params.get("filename", ""))

        case "create_file" | "new_file":
            content_val = params.get("content") or params.get("text") or ""
            return create_file(params.get("filename", ""), content_val)

        case "edit_file" | "write_file" | "update_file":
            # The model sometimes uses write_file or update_file as aliases for edit_file
            content_val = (params.get("new_content") or params.get("content")
                           or params.get("text") or "")
            return edit_file(params.get("filename", ""), content_val)

        case "delete_file" | "rm" | "remove_file" | "del" | "unlink":
            # Model sometimes passes {"files": [...]} for multiple deletions
            files = params.get("files")
            if files and isinstance(files, list):
                if not confirm(f"Delete {', '.join(map(str, files))}?"):
                    return NOT_DELETED
                results = [delete_file(f) for f in files]
                return "\n".join(results)

            # Model sometimes passes {"all": true} meaning "delete everything"
            all_flag = params.get("all") or params.get("all_files") or params.get("directory")
            if all_flag:
                if not confirm("Delete ALL the files in sk_files_home?"):
                    return NOT_DELETED
                return delete_all_files()

            # Normal case: single file with various possible param names
            fname = (params.get("filename") or params.get("file")
                     or params.get("name") or params.get("path") or "")
            # If the model passed an absolute path, take only the filename
            fname = Path(fname).name if fname else ""
            exists = bool(fname) and any(f.is_file() for f in SK_FILES_HOME.rglob(fname))
            if exists and not confirm(f"Delete '{fname}'?"):
                return NOT_DELETED
            return delete_file(fname)

        case "rename_file":
            # Model sometimes uses old_name/new_name instead of old/new
            old = params.get("old") or params.get("old_name", "")
            new = params.get("new") or params.get("new_name", "")
            return rename_file(old, new)

        case "delete_all" | "rm_all" | "delete_all_files" | "clear_folder" | "clear":
            if not confirm("Delete ALL the files in sk_files_home?"):
                return NOT_DELETED
            return delete_all_files()

        case "replace_file" | "swap_file":
            # The model sometimes invents replace_file: translate it into delete + create
            old_f = (params.get("old_file") or params.get("old_filename")
                     or params.get("filename") or "")
            new_f = (params.get("new_file") or params.get("new_filename")
                     or params.get("new_name") or "")
            if not old_f or not new_f:
                return "replace_file: insufficient parameters."
            if not confirm(f"Delete '{Path(old_f).name}' to replace it with '{Path(new_f).name}'?"):
                return NOT_DELETED
            r1 = delete_file(Path(old_f).name)
            r2 = create_file(Path(new_f).name, "")
            return f"{r1} | {r2}"

        # ── Folder tools ──────────────────────────────────────────────────────
        case "create_dir" | "mkdir":
            # Model sometimes uses foldername, name, or dirname as param key
            dirname = (params.get("dirname") or params.get("foldername")
                       or params.get("name") or params.get("folder") or "")
            return create_dir(dirname)

        case "rename_dir":
            old = params.get("old") or params.get("old_name", "")
            new = params.get("new") or params.get("new_name", "")
            return rename_dir(old, new)

        case "delete_dir" | "rmdir":
            dirname = (params.get("dirname") or params.get("foldername")
                       or params.get("name") or params.get("folder") or "")
            force   = bool(params.get("force", False))
            if dirname and not confirm(f"Delete the folder '{dirname}'"
                                       + (" and everything in it?" if force else "?")):
                return NOT_DELETED
            return delete_dir(dirname, force=force)

        case "move_dir":
            dirname = (params.get("dirname") or params.get("foldername")
                       or params.get("name") or params.get("folder") or "")
            dest    = (params.get("destination") or params.get("dest")
                       or params.get("destination_folder") or "")
            return move_dir(dirname, dest)

        case "list_dirs":
            return list_dirs()

        # ── Move tool ─────────────────────────────────────────────────────────
        case "move_file" | "mv":
            fname = (params.get("filename") or params.get("file")
                     or params.get("source") or params.get("source_filename") or "")
            dest  = (params.get("destination") or params.get("dest")
                     or params.get("destination_folder") or params.get("folder") or "")
            return move_file(fname, dest)

        # ── Web search ────────────────────────────────────────────────────────
        case "web_search":
            return dispatch_web_search(params)

        case _:
            return f"Unknown tool: '{tool}'."


# ─── Web search dispatcher ────────────────────────────────────────────────────
# (kept separate so it's easy to find)

def dispatch_web_search(params: dict) -> str:
    """
    Runs a DuckDuckGo search. The query goes through build_search_query
    first, so that short keywords are searched instead of whole sentences.
    """
    raw_query = params.get("query") or params.get("q") or params.get("search") or ""
    if not raw_query:
        return "web_search: missing 'query' parameter."

    # Whole sentence → 2-5 keywords
    optimized_query = build_search_query(raw_query)
    print(f"  [query: '{raw_query}' → '{optimized_query}']")

    return web_search(optimized_query)


# ─── Folder snapshot ─────────────────────────────────────────────────────────

def folder_snapshot() -> str:
    """
    Reads the full tree of sk_files_home recursively and returns a compact
    string to inject into the system prompt.
    Uses rglob so sk_files sees files inside subfolders too, not just the top level.

    Example output:
      sk_files_home/
        folder1/
          ciao.txt (0 bytes)
        folder2/
        file1.txt (144 bytes)
    """
    if not SK_FILES_HOME.exists():
        return "sk_files_home does not exist yet."

    def _tree(path: Path, indent: int) -> list[str]:
        lines = []
        pad = "  " * indent
        # dirs first, then files — sorted alphabetically
        children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        for child in children:
            if child.is_dir():
                lines.append(f"{pad}{child.name}/")
                lines.extend(_tree(child, indent + 1))
            else:
                lines.append(f"{pad}{child.name} ({child.stat().st_size} bytes)")
        return lines

    tree_lines = _tree(SK_FILES_HOME, 1)
    if not tree_lines:
        return "sk_files_home is currently empty."

    return "sk_files_home/\n" + "\n".join(tree_lines)


def inject_snapshot(messages: list, shared: str = "") -> None:
    """
    Updates messages[0] (the system message) in-place with a fresh folder snapshot.
    Called automatically before every model call so sk_files always has up-to-date context.

    Think of it like this: every time sk_files is about to speak, we whisper
    "hey, here's what's in the folder right now" into its ear first.
    """
    snapshot = folder_snapshot()
    messages[0]["content"] = (
        CHAT_SYSTEM +
        f"\n\n--- Current state of sk_files_home ---\n{snapshot}\n---"
    )
    if shared:
        messages[0]["content"] += "\n\n" + shared


# ─── Startup context injection ────────────────────────────────────────────────

def build_initial_messages(memory: dict) -> list:
    """
    Build the startup conversation history with:
    1. System prompt with instructions, tool definitions, and long-term memory.
    2. Initial snapshot of the sk_files_home folder (already baked into system message).
    """
    mem_context = memory_to_context(memory)
    system_content = CHAT_SYSTEM
    if mem_context:
        system_content = CHAT_SYSTEM + "\n\n" + mem_context

    messages = [
        {"role": "system", "content": system_content},  # will be updated by inject_snapshot
        {
            "role": "user",
            "content": (
                f"[SYSTEM] Working folder: {SK_FILES_HOME} | Max file limit: {MAX_FILES}"
            ),
        },
        {
            "role": "assistant",
            "content": "Got it. Ready.",
        },
    ]
    inject_snapshot(messages)  # inject the initial snapshot right away
    return messages


# ─── Main loop ────────────────────────────────────────────────────────────────

def main():
    print("=" * 57)
    print(f"  sk_files - SKAI file assistant, model {MODEL}")
    print(f"  Folder  : {SK_FILES_HOME}")
    print(f"  Limit   : {MAX_FILES} files")
    print(f"  Model   : {MODEL}")
    print("  Type 'exit' to quit, 'files' for a quick file list")
    print("  Prefixes: '!' force tool | '?' force plain text")
    print("=" * 57)

    memory = load_memory()
    messages = build_initial_messages(memory)

    while True:
        # ── User input ────────────────────────────────────────────────────────
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Bye!")
            break
        if user_input.lower() in ("files", "ls", "list"):
            print(f"\n{list_files()}")
            continue

        # ── Override prefixes ─────────────────────────────────────────────────
        # '!' = force tool execution (skip needs_tool, go straight to JSON retry)
        # '?' = force plain text response (skip everything, raw Ollama response)
        force_tool = user_input.startswith("!")
        force_text = user_input.startswith("?")
        # Strip the prefix before passing to the model
        clean_input = user_input[1:].strip() if (force_tool or force_text) else user_input

        # ── Add the user message to the conversation history ──────────────────
        messages.append({"role": "user", "content": clean_input})

        # ── Refresh folder snapshot in the system message ─────────────────────
        # Updates messages[0] with the real current state of sk_files_home so sk_files
        # always knows what files exist before it even starts thinking.
        inject_snapshot(messages, shared_recall(clean_input))

        # ── Ask the model what to do ──────────────────────────────────────────
        print("SKAI is thinking...")

        if force_text:
            # Plain text mode: direct Ollama response, no retry logic
            llm_response = ask_ollama(messages)
            tool_calls = None
        else:
            llm_response, tool_calls = ask_ollama_with_retry(
                messages, clean_input, force_tool=force_tool
            )

        if tool_calls:
            results = []
            web_results_to_forward = []   # raccoglie i risultati web da rimandare al modello

            for tc in tool_calls:
                tool   = tc["tool"]
                params = tc.get("params", {})
                print(f"SKAI executing: {tool}({params})...")
                result = dispatch_tool(tool, params)
                print(f"  → {result[:120]}...")  # only the beginning, to keep the screen readable

                if tool == "web_search":
                    # Web results are not printed raw: they go back to the model,
                    # which reads them and answers the user in plain words.
                    web_results_to_forward.append(result)
                else:
                    results.append(f"{tool}: {result}")

            # After web searches, a second call gives the model the results.
            if web_results_to_forward:
                context = "\n\n".join(web_results_to_forward)
                messages.append({
                    "role": "user",
                    "content": (
                        f"[WEB SEARCH RESULTS]\n{context}\n\n"
                        f"If the user's original request only asked a question, answer "
                        f"in plain English using the results above.\n"
                        f"If the user also asked to create or edit a file with this "
                        f"information, output ONLY the JSON tool call to do so — "
                        f"no extra text."
                    ),
                })
                print("SKAI is reading the results...")
                final_answer = ask_ollama(messages, temperature=0.3, max_tokens=800)

                # The model may answer with a JSON tool call (e.g. create_file)
                # or with plain text: check which before acting.
                follow_up_calls = parse_tool_calls(final_answer)
                if follow_up_calls:
                    # Another web_search means the model found nothing and wants
                    # to try again: stop the loop here.
                    if all(ftc["tool"] == "web_search" for ftc in follow_up_calls):
                        print("\nSKAI: I couldn't find results for that search. "
                              "Try rephrasing your question with different keywords.")
                        messages.append({
                            "role": "assistant",
                            "content": "No results found. Asked user to rephrase.",
                        })
                    else:
                        # A real tool call (e.g. create_file): run it
                        for ftc in follow_up_calls:
                            ftool   = ftc["tool"]
                            fparams = ftc.get("params", {})
                            print(f"SKAI executing (follow-up): {ftool}({fparams})...")
                            fresult = dispatch_tool(ftool, fparams)
                            print(f"  → {fresult}")
                            results.append(f"{ftool}: {fresult}")
                        messages.append({
                            "role": "assistant",
                            "content": "Operations done: " + " | ".join(
                                ftc["tool"] for ftc in follow_up_calls
                            ),
                        })
                else:
                    # Plain text: it is SKAI's answer
                    print(f"\nSKAI: {final_answer}")
                    messages.append({"role": "assistant", "content": final_answer})

            # Other tools ran too (e.g. create a file + search the web): show the folder
            if results:
                print(f"\n[folder updated]\n{list_files()}")
                tool_summary = "Operations done: " + " | ".join(results)
                messages.append({
                    "role": "assistant",
                    "content": tool_summary,
                })
                memory = update_memory(memory, clean_input, tool_summary, ask_ollama)
                save_memory(memory)
                shared_remember(clean_input, tool_summary)

        else:
            # Normal text response (or error message after retries)
            print(f"\nSKAI: {llm_response}")
            messages.append({"role": "assistant", "content": llm_response})
            memory = update_memory(memory, clean_input, llm_response, ask_ollama)
            save_memory(memory)
            shared_remember(clean_input, llm_response)


if __name__ == "__main__":
    main()
