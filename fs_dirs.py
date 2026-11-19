# Copyright (C) 2026 Enrico Miot
# Licensed under GNU GPL v3 or later — see /usr/share/common-licenses/GPL-3
# SPDX-License-Identifier: GPL-3.0-or-later

from config import SK_FILES_HOME
from pathlib import Path


def create_dir(dirname: str) -> str:
    """
    Creates a new subfolder inside SkFiles_home.
    Supports nested paths like 'folder1/subfolder'.
    Sanitizes the path to prevent escaping SkFiles_home.
    """
    if not dirname:
        return "Error: no folder name specified."

    # Sanitize: remove any '..' components that could escape SkFiles_home
    rel = Path(dirname)
    parts = [p for p in rel.parts if p not in (".", "..")]
    if not parts:
        return "Error: invalid folder name."

    safe_rel = Path(*parts)
    dp = SK_FILES_HOME / safe_rel

    if dp == SK_FILES_HOME:
        return "Error: cannot use SkFiles_home itself as target."

    if dp.exists():
        return f"A folder named '{safe_rel}' already exists."

    dp.mkdir(parents=True, exist_ok=False)
    return f"✅ Folder '{safe_rel}' created."


def rename_dir(old: str, new: str) -> str:
    """
    Renames a subfolder inside SkFiles_home.
    """
    if not old or not new:
        return "Error: both old and new folder names are required."

    old_p = SK_FILES_HOME / Path(old).name
    new_p = SK_FILES_HOME / Path(new).name

    if not old_p.exists():
        return f"Folder '{old_p.name}' does not exist."

    if not old_p.is_dir():
        return f"'{old_p.name}' is a file, not a folder. Use rename_file instead."

    if new_p.exists():
        return f"A folder named '{new_p.name}' already exists. Choose a different name."

    old_p.rename(new_p)
    return f"✅ Folder renamed: '{old_p.name}' → '{new_p.name}'."


def delete_dir(dirname: str, force: bool = False) -> str:
    """
    Deletes a subfolder inside SkFiles_home.
    If the folder is not empty, requires force=True to delete recursively.
    """
    if not dirname:
        return "Error: no folder name specified."

    dp = SK_FILES_HOME / Path(dirname).name

    if not dp.exists():
        return f"Folder '{dp.name}' does not exist."

    if not dp.is_dir():
        return f"'{dp.name}' is a file, not a folder. Use delete_file instead."

    contents = list(dp.iterdir())

    if contents and not force:
        return (
            f"Folder '{dp.name}' is not empty ({len(contents)} items inside). "
            f"Use delete_dir with force=true to delete it along with its contents."
        )

    # Recursive delete
    import shutil
    shutil.rmtree(dp)
    return f"✅ Folder '{dp.name}' deleted."


def list_dirs() -> str:
    """
    Lists all subfolders inside SkFiles_home with their item count.
    """
    if not SK_FILES_HOME.exists():
        return "SkFiles_home does not exist yet."

    dirs = sorted(d for d in SK_FILES_HOME.rglob("*") if d.is_dir())
    if not dirs:
        return "No subfolders in SkFiles_home."

    lines = [f"📂 Subfolders in SkFiles_home ({len(dirs)}):"]
    for d in dirs:
        count = len(list(d.iterdir()))
        rel = d.relative_to(SK_FILES_HOME)
        lines.append(f"   • {rel}/  ({count} items)")
    return "\n".join(lines)


def move_dir(dirname: str, destination: str) -> str:
    """
    Moves a subfolder into another subfolder inside SkFiles_home.
    Example: move_dir("new_subfolder", "new_folder")
    moves SkFiles_home/new_subfolder → SkFiles_home/new_folder/new_subfolder
    """
    import shutil

    if not dirname or not destination:
        return "Error: both dirname and destination are required."

    src_name  = Path(dirname).name
    dest_name = Path(destination).name

    # Find the source dir anywhere in SkFiles_home
    matches = [d for d in SK_FILES_HOME.rglob(src_name) if d.is_dir()]
    if not matches:
        return f"Folder '{src_name}' not found anywhere in SkFiles_home."
    if len(matches) > 1:
        paths = ", ".join(str(m.relative_to(SK_FILES_HOME)) for m in matches)
        return f"Multiple folders named '{src_name}' found: {paths}. Be more specific."

    src = matches[0]

    dest_dir = SK_FILES_HOME / dest_name
    if not dest_dir.exists():
        return f"Destination folder '{dest_name}' does not exist. Create it first."
    if not dest_dir.is_dir():
        return f"'{dest_name}' is a file, not a folder."

    target = dest_dir / src_name
    if target.exists():
        return f"A folder named '{src_name}' already exists inside '{dest_name}'."

    shutil.move(str(src), str(target))
    return f"✅ Folder moved: '{src.relative_to(SK_FILES_HOME)}' → '{target.relative_to(SK_FILES_HOME)}'."
