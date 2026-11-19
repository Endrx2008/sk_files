# Copyright (C) 2026 Enrico Miot
# Licensed under GNU GPL v3 or later — see /usr/share/common-licenses/GPL-3
# SPDX-License-Identifier: GPL-3.0-or-later

from config import SK_FILES_HOME, MAX_FILES
from pathlib import Path


def delete_file(filename: str) -> str:
    """
    Deletes a file anywhere in SkFiles_home (including subfolders).
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

    fp = matches[0]
    rel = fp.relative_to(SK_FILES_HOME)
    fp.unlink()
    count = len([f for f in SK_FILES_HOME.rglob("*") if f.is_file()])
    return f"✅ File '{rel}' deleted. ({count}/{MAX_FILES} files remaining)"


def delete_all_files() -> str:
    """
    Deletes ALL files in SkFiles_home recursively (including files inside subfolders).
    Leaves the folder structure intact — only removes files.
    """
    if not SK_FILES_HOME.exists():
        return "The SkFiles_home folder does not exist yet."

    files = [f for f in SK_FILES_HOME.rglob("*") if f.is_file()]
    if not files:
        return "The folder is already empty, nothing to delete."

    deleted = []
    errors = []
    for f in files:
        try:
            f.unlink()
            deleted.append(str(f.relative_to(SK_FILES_HOME)))
        except Exception as e:
            errors.append(f"{f.name}: {e}")

    msg = f"✅ Deleted {len(deleted)} file(s): {', '.join(deleted)}."
    if errors:
        msg += f" Errors: {', '.join(errors)}."
    return msg
