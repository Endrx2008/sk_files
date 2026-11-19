# Copyright (C) 2026 Enrico Miot
# Licensed under GNU GPL v3 or later — see /usr/share/common-licenses/GPL-3
# SPDX-License-Identifier: GPL-3.0-or-later

from config import SK_FILES_HOME, MAX_FILES
from pathlib import Path


def read_file(filename: str) -> str:
    """
    Reads and returns the content of a file anywhere in SkFiles_home (including subfolders).
    Searches recursively so the user doesn't need to specify the full path.
    """
    if not filename:
        return "Error: no filename specified."

    name = Path(filename).name
    matches = [f for f in SK_FILES_HOME.rglob(name) if f.is_file()]

    if not matches:
        return f"File '{name}' not found anywhere in SkFiles_home."

    if len(matches) > 1:
        paths = ", ".join(str(m.relative_to(SK_FILES_HOME)) for m in matches)
        return f"Multiple files named '{name}' found: {paths}. Be more specific."

    return matches[0].read_text(encoding="utf-8")


def list_files() -> str:
    """
    Returns a full recursive tree of SkFiles_home with folders and files.
    """
    if not SK_FILES_HOME.exists():
        return "The SkFiles_home folder does not exist yet."

    def _tree(path: Path, indent: int) -> list[str]:
        lines = []
        pad = "  " * indent
        children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        for child in children:
            if child.is_dir():
                lines.append(f"{pad}📂 {child.name}/")
                lines.extend(_tree(child, indent + 1))
            else:
                lines.append(f"{pad}• {child.name}  ({child.stat().st_size} bytes)")
        return lines

    tree_lines = _tree(SK_FILES_HOME, 1)
    if not tree_lines:
        return "The SkFiles_home folder is empty."

    all_files = [f for f in SK_FILES_HOME.rglob("*") if f.is_file()]
    all_dirs  = [d for d in SK_FILES_HOME.rglob("*") if d.is_dir()]
    header = f"📁 SkFiles_home ({len(all_files)} files, {len(all_dirs)} subfolders):"
    return header + "\n" + "\n".join(tree_lines)
