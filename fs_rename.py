# Copyright (C) 2026 Enrico Miot
# Licensed under GNU GPL v3 or later — see /usr/share/common-licenses/GPL-3
# SPDX-License-Identifier: GPL-3.0-or-later

from config import SKAI_HOME
from pathlib import Path


def rename_file(old: str, new: str) -> str:
    """
    Renames a file anywhere inside SkAi_home (including subfolders).
    Searches recursively so the user doesn't need to specify the full path.
    If the new name has no extension, it inherits the original file's extension.
    """
    if not old or not new:
        return "Error: both old and new file names are required."

    old_name = Path(old).name  # strip any path, take just the filename

    # Search recursively for the file anywhere in SkAi_home
    matches = [f for f in SKAI_HOME.rglob(old_name) if f.is_file()]

    if not matches:
        return f"File '{old_name}' not found anywhere in SkAi_home."

    if len(matches) > 1:
        paths = ", ".join(str(m.relative_to(SKAI_HOME)) for m in matches)
        return f"Multiple files named '{old_name}' found: {paths}. Be more specific."

    old_p = matches[0]
    new_name = Path(new).name

    # If the new name has no extension, inherit from the original
    if not Path(new_name).suffix:
        new_name = new_name + old_p.suffix

    new_p = old_p.parent / new_name  # keep it in the same folder

    if new_p.exists():
        return f"A file named '{new_name}' already exists in '{old_p.parent.name}'. Choose a different name."

    old_p.rename(new_p)
    rel_old = old_p.relative_to(SKAI_HOME)
    rel_new = new_p.relative_to(SKAI_HOME)
    return f"✅ File renamed: '{rel_old}' → '{rel_new}'."
