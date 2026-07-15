"""
Export module business logic: the compiled_jsons folder holds batches of
scraped listings written by the ADB "smart scrape" flow, ready to be
downloaded, deleted, or re-ingested into the database.
"""
import os

from config import settings

COMPILED_FOLDER = os.path.join(settings.DATA_FOLDER, "compiled_jsons")


def resolve_safe_path(filename: str) -> str:
    """Resolve a filename inside COMPILED_FOLDER, raising if it escapes the folder."""
    os.makedirs(COMPILED_FOLDER, exist_ok=True)
    path = os.path.abspath(os.path.join(COMPILED_FOLDER, filename))
    if not path.startswith(os.path.abspath(COMPILED_FOLDER)):
        raise ValueError("Invalid file path.")
    return path
