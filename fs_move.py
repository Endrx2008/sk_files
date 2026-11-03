# Copyright (C) 2026 Enrico Miot
# Licensed under GNU GPL v3 or later — see /usr/share/common-licenses/GPL-3
# SPDX-License-Identifier: GPL-3.0-or-later

from config import SK_FILES_HOME
from pathlib import Path
import shutil


def move_file(filename: str, destination: str) -> str:
    """
    Moves a file to a subfolder inside SkFiles_home.
    - filename:    name of the file (can include current subfolder, e.g. "sub/file.txt")
    - destination: target subfolder name (e.g. "hy")

    The destination folder must already exist.
    """
    if not filename or not destination:
        return "Error: both filename and destination folder are required."

    # Resolve source — strip any leading path components for safety, then search
    src_name = Path(filename).name
    dest_dir = SK_FILES_HOME / Path(destination).name

    # Find the file anywhere inside SkFiles_home
    matches = list(SK_FILES_HOME.rglob(src_name))
    matches = [m for m in matches if m.is_file()]

    if not matches:
        return f"File '{src_name}' not found anywhere in SkFiles_home."

    src = matches[0]  # take the first match

    if not dest_dir.exists():
        return f"Destination folder '{dest_dir.name}' does not exist. Create it first."

    if not dest_dir.is_dir():
        return f"'{dest_dir.name}' is a file, not a folder."

    target = dest_dir / src_name

    if target.exists():
        return f"A file named '{src_name}' already exists in '{dest_dir.name}'."

    shutil.move(str(src), str(target))
    return f"✅ Moved '{src_name}' → '{dest_dir.name}/{src_name}'."
