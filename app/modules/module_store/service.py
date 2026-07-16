"""
Module Store: discovers the manifest.json of every folder under app/modules/,
and layers persisted enable/disable + install/uninstall state (stored in the
module_configs table) on top so the rest of the app can ask "is X active?".

"enabled" and "installed" are tracked separately so the UI can distinguish a
module a user turned off (Disable) from one they removed entirely (Uninstall).
A module is only "active" when both are true.
"""
import os
import json
from typing import Optional

from sqlalchemy.orm import Session

from app import models

MODULES_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _discover_manifests() -> list[dict]:
    manifests = []
    for entry in sorted(os.listdir(MODULES_DIR)):
        manifest_path = os.path.join(MODULES_DIR, entry, "manifest.json")
        if not os.path.isfile(manifest_path):
            continue
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            continue
        manifest.setdefault("name", entry)
        manifests.append(manifest)
    return manifests


def get_manifest(module_id: str) -> Optional[dict]:
    for manifest in _discover_manifests():
        if manifest["name"] == module_id:
            return manifest
    return None


def _get_config(db: Session, module_id: str) -> Optional["models.ModuleConfig"]:
    return db.query(models.ModuleConfig).filter(models.ModuleConfig.module_id == module_id).first()


def _get_state(db: Session, module_id: str) -> dict:
    config = _get_config(db, module_id)
    if config is None:
        return {"enabled": True, "installed": True}
    try:
        stored = json.loads(config.settings) if config.settings else {}
    except Exception:
        stored = {}
    return {
        "enabled": True if config.is_enabled is None else bool(config.is_enabled),
        "installed": stored.get("installed", True),
    }


def list_modules(db: Session) -> list[dict]:
    result = []
    for manifest in _discover_manifests():
        name = manifest["name"]
        state = _get_state(db, name)
        result.append({
            "name": name,
            "version": manifest.get("version", "?"),
            "description": manifest.get("description", ""),
            "prefix": manifest.get("prefix", ""),
            "core": bool(manifest.get("core", False)),
            "enabled": state["enabled"],
            "installed": state["installed"],
            "active": state["enabled"] and state["installed"],
        })
    return result


def _upsert(db: Session, module_id: str, *, enabled: Optional[bool] = None, installed: Optional[bool] = None) -> dict:
    config = _get_config(db, module_id)
    if config is None:
        config = models.ModuleConfig(module_id=module_id, is_enabled=True, settings=json.dumps({"installed": True}))
        db.add(config)
        db.flush()

    try:
        stored = json.loads(config.settings) if config.settings else {}
    except Exception:
        stored = {}

    if enabled is not None:
        config.is_enabled = enabled
    if installed is not None:
        stored["installed"] = installed

    config.settings = json.dumps(stored)
    db.commit()
    return _get_state(db, module_id)


def set_enabled(db: Session, module_id: str, enabled: bool) -> dict:
    manifest = get_manifest(module_id)
    if manifest is None:
        raise KeyError(module_id)
    if not enabled and manifest.get("core"):
        raise PermissionError(f"'{module_id}' is a core module and cannot be disabled.")
    return _upsert(db, module_id, enabled=enabled)


def set_installed(db: Session, module_id: str, installed: bool) -> dict:
    manifest = get_manifest(module_id)
    if manifest is None:
        raise KeyError(module_id)
    if not installed and manifest.get("core"):
        raise PermissionError(f"'{module_id}' is a core module and cannot be uninstalled.")
    # Reinstalling brings a module back enabled by default.
    return _upsert(db, module_id, installed=installed, enabled=True if installed else None)
