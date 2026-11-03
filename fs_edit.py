# Copyright (C) 2026 Enrico Miot
# Licensed under GNU GPL v3 or later — see /usr/share/common-licenses/GPL-3
# SPDX-License-Identifier: GPL-3.0-or-later

from config import SK_FILES_HOME
from pathlib import Path


def edit_file(filename: str, new_content: str) -> str:
    """
    Overwrites the content of a file anywhere in SkFiles_home (including subfolders).
    Searches recursively so the user doesn't need to specify the full path.
    """
    name = Path(filename).name
    matches = [f for f in SK_FILES_HOME.rglob(name) if f.is_file()]

    if not matches:
        return f"File '{name}' not found anywhere in SkFiles_home. Use 'create' to make it."

    if len(matches) > 1:
        paths = ", ".join(str(m.relative_to(SK_FILES_HOME)) for m in matches)
        return f"Multiple files named '{name}' found: {paths}. Be more specific."

    fp = matches[0]
    fp.write_text(new_content, encoding="utf-8")
    rel = fp.relative_to(SK_FILES_HOME)
    return f"✅ File '{rel}' updated ({len(new_content)} characters)."
