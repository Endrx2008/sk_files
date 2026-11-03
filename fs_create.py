# Copyright (C) 2026 Enrico Miot
# Licensed under GNU GPL v3 or later — see /usr/share/common-licenses/GPL-3
# SPDX-License-Identifier: GPL-3.0-or-later

from config import SK_FILES_HOME, MAX_FILES
from pathlib import Path


def create_file(filename: str, content: str) -> str:
    """
    Creates a new file in SkFiles_home with the given content.
    - Supports subfolder paths like 'folder1/notes.txt'
    - Appends .txt if the file has no extension.
    - Rejects if MAX_FILES limit is reached.
    - Rejects if the file already exists.
    """
    SK_FILES_HOME.mkdir(parents=True, exist_ok=True)

    all_files = [f for f in SK_FILES_HOME.rglob("*") if f.is_file()]
    if len(all_files) >= MAX_FILES:
        return f"File limit of {MAX_FILES} reached. Delete something before creating new files."

    # Build the full path, keeping any subfolder the model specified
    # but stripping anything that tries to escape SkFiles_home (e.g. ../../etc)
    rel = Path(filename)
    parts = [p for p in rel.parts if p not in (".", "..")]  # sanitize
    safe_rel = Path(*parts) if parts else Path(filename)

    # Add .txt if no extension
    if not safe_rel.suffix:
        safe_rel = safe_rel.with_suffix(".txt")

    fp = SK_FILES_HOME / safe_rel

    # If the subfolder doesn't exist yet, create it automatically
    fp.parent.mkdir(parents=True, exist_ok=True)

    if fp.exists():
        return f"File '{safe_rel}' already exists. Use 'edit' if you want to change its content."

    fp.write_text(content, encoding="utf-8")
    count = len([f for f in SK_FILES_HOME.rglob("*") if f.is_file()])
    return f"✅ File '{safe_rel}' created successfully. ({count}/{MAX_FILES} files in SkFiles_home)"
