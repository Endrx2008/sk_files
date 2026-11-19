# Copyright (C) 2026 Enrico Miot
# Licensed under GNU GPL v3 or later — see /usr/share/common-licenses/GPL-3
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import os
import re
import shutil
import subprocess

# ─── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/chat"

# ─── Desktop detection ────────────────────────────────────────────────────────
# Hardcoding ~/Desktop breaks on every localized install: an Italian
# system calls it Scrivania, a French one Bureau, a German one
# Schreibtisch. The name is not the thing — what actually defines the
# desktop is the XDG_DESKTOP_DIR entry the desktop environment itself
# uses to decide which folder to paint icons from. That is what gets
# read here, so SkFiles_home always lands on the folder the user really
# sees behind their windows.

# Localized names used as a last resort, only when a folder by that
# name already exists — never to create one.
_KNOWN_DESKTOP_NAMES = [
    "Desktop",              # en, nl, pt
    "Scrivania",            # it
    "Escritorio",           # es
    "Bureau",               # fr
    "Schreibtisch",         # de
    "Área de Trabalho",     # pt-BR
    "Skrivbord",            # sv
    "Pulpit",               # pl
    "Plocha",               # cs
    "Asztal",               # hu
    "Skrivebord",           # da, nb
    "Työpöytä",             # fi
    "Masaüstü",             # tr
    "Рабочий стол",         # ru
    "Επιφάνεια εργασίας",   # el
    "デスクトップ",           # ja
    "桌面",                  # zh
    "바탕화면",               # ko
]


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def _valid_desktop(path) -> Path | None:
    """A candidate counts only if it exists, is a directory, and isn't
    just $HOME itself — some misconfigured systems set XDG_DESKTOP_DIR
    to the home folder, and dropping sk_files_home straight into $HOME
    would be a surprise, not a feature."""
    if not path:
        return None
    p = Path(os.path.expanduser(str(path))).expanduser()
    try:
        p = p.resolve()
    except OSError:
        return None
    if not p.is_dir():
        return None
    if p == _home().resolve():
        return None
    return p


def _desktop_from_env() -> Path | None:
    """An explicit override always wins."""
    return _valid_desktop(os.environ.get("XDG_DESKTOP_DIR"))


def _desktop_from_xdg_user_dir() -> Path | None:
    """Asks xdg-user-dir, the same helper file managers call. It always
    prints something (falling back to $HOME), so the answer still goes
    through _valid_desktop rather than being trusted blindly."""
    exe = shutil.which("xdg-user-dir")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "DESKTOP"], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return _valid_desktop(out.stdout.strip())


def _desktop_from_user_dirs_file() -> Path | None:
    """Parses ~/.config/user-dirs.dirs by hand, for systems where the
    xdg-user-dirs binary isn't installed but its config is there.

    The file's lines look like:
        XDG_DESKTOP_DIR="$HOME/Scrivania"
    so $HOME has to be expanded manually — os.path.expanduser doesn't
    touch $HOME, only a leading ~."""
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(_home() / ".config")
    path = Path(config_home) / "user-dirs.dirs"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    match = re.search(
        r'^\s*XDG_DESKTOP_DIR\s*=\s*"?(.*?)"?\s*$', text, re.MULTILINE
    )
    if not match:
        return None

    value = match.group(1).strip()
    home = str(_home())
    value = value.replace("$HOME", home).replace("${HOME}", home)
    return _valid_desktop(value)


def _desktop_from_known_names() -> Path | None:
    home = _home()
    for name in _KNOWN_DESKTOP_NAMES:
        candidate = _valid_desktop(home / name)
        if candidate:
            return candidate
    return None


def get_desktop_dir(create_fallback: bool = True) -> Path:
    """The user's real desktop folder, by whatever name it goes.

    Sources are tried in order of authority: environment override,
    xdg-user-dir, the user-dirs.dirs file, then known localized names
    that actually exist on disk. Falls back to ~/Desktop (created on
    demand) only when every source comes up empty — a headless or
    minimal system with no XDG setup at all. Never raises: SkFiles always
    gets a usable path back."""
    for source in (_desktop_from_env, _desktop_from_xdg_user_dir,
                   _desktop_from_user_dirs_file, _desktop_from_known_names):
        found = source()
        if found:
            return found

    fallback = _home() / "Desktop"
    if create_fallback:
        try:
            fallback.mkdir(parents=True, exist_ok=True)
        except OSError:
            return _home()
    return fallback


# ─── Filesystem ───────────────────────────────────────────────────────────────
MAX_FILES   = 100
# Resolved once at import time and shared by every module that does
# `from config import SK_FILES_HOME`, so the whole app agrees on one path.
DESKTOP_DIR = get_desktop_dir()
SK_FILES_HOME   = DESKTOP_DIR / "sk_files_home"

# ─── System prompt ────────────────────────────────────────────────────────────
CHAT_SYSTEM = """You are SkFiles, a file management assistant.
You have access to a folder called SkFiles_home to manage text files.
When the user wants to operate on files, reply ONLY with pure JSON, nothing else:
{"tool": "TOOL_NAME", "params": {...}}
Available tools:
  File tools:
  create_file   → {"filename": "...", "content": "..."}
  edit_file     → {"filename": "...", "new_content": "..."}
  delete_file   → {"filename": "..."}
  rename_file   → {"old": "...", "new": "..."}
  read_file     → {"filename": "..."}
  move_file     → {"filename": "...", "destination": "subfolder_name"}
  list_files    → {}
  Folder tools (subfolders inside SkFiles_home only):
  create_dir    → {"dirname": "..."}
  rename_dir    → {"old": "...", "new": "..."}
  delete_dir    → {"dirname": "...", "force": true}
  move_dir      → {"dirname": "...", "destination": "parent_folder"}
  list_dirs     → {}
  Web tool:
  web_search    → {"query": "2-5 keyword search query"}
Rules:
- Do NOT add any text before or after the JSON.
- Do NOT ask for confirmation before acting.
- For normal conversation reply in American English without JSON.
- If the user asks to delete all files, use the delete_all tool.
- Folder tools only work on subfolders of SkFiles_home, never on SkFiles_home itself.
- Use web_search when the user asks about current events, facts, or anything
  you don't know for certain. After getting the results, reply in plain text.
- For web_search, NEVER copy the user's sentence as the query.
  Rephrase it as 2-5 short English keywords, like a real search engine query.
  Good:  user asks "what happened in iran on march 1 2025" → "Iran news March 2025"
  Good:  user asks "chi ha vinto le elezioni in Germania?" → "Germany elections 2025 winner"
  Bad:   "what happened in iran on march 1 2025"  ← too long, copy-paste of user input
"""
# ─── Tool name registry ───────────────────────────────────────────────────────
TOOL_NAMES = {
    # File tools
    "create_file", "new_file",
    "edit_file", "write_file", "update_file",
    "delete_file", "rm", "remove_file", "del", "unlink",
    "delete_all", "rm_all", "delete_all_files", "clear_folder", "clear",
    "rename_file", "replace_file", "swap_file",
    "read_file",
    "move_file", "mv",
    "list_files",
    # Folder tools
    "create_dir", "mkdir",
    "rename_dir",
    "delete_dir", "rmdir",
    "move_dir",
    "list_dirs",
    # Web tool
    "web_search",
}


if __name__ == "__main__":
    # Quick self-check: python3 config.py prints where SkFiles will work.
    print("XDG_DESKTOP_DIR env :", os.environ.get("XDG_DESKTOP_DIR"))
    print("xdg-user-dir        :", _desktop_from_xdg_user_dir())
    print("user-dirs.dirs      :", _desktop_from_user_dirs_file())
    print("known names         :", _desktop_from_known_names())
    print("→ desktop in use    :", DESKTOP_DIR)
    print("→ SK_FILES_HOME         :", SK_FILES_HOME)
