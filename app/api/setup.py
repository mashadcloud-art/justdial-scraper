"""
Scapre Pro — First-time Setup API
===================================
Handles initial configuration: account creation, backend choice, database choice.
Config is saved to config.yaml and user accounts to data/users.json.
"""

import os
import json
import hashlib
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/setup", tags=["setup"])

from config import settings

_ROOT = os.path.dirname(settings.DATA_FOLDER)
CONFIG_FILE = os.path.join(_ROOT, "config.yaml")
USERS_FILE  = os.path.join(settings.DATA_FOLDER, "users.json")
SETUP_FLAG  = os.path.join(settings.DATA_FOLDER, ".setup_done")


# ── Helpers ──────────────────────────────────────────────────────────────────
def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _seed_mashad_if_needed():
    """
    Pre-seed the 'mashad' owner account with the current config.yaml credentials.
    This runs once — if mashad already exists, does nothing.
    """
    users = _load_users()
    if "mashad" in users:
        return  # already seeded

    # Read current config to get existing DB/backend settings
    cfg = _load_yaml()

    users["mashad"] = {
        "password_hash": _hash("mashad"),
        "role": "superadmin",
        "name": "Mashad",
        "preset": True,  # marker: this account uses existing config.yaml as-is
    }
    _save_users(users)

    # Mark setup done if not already (mashad = owner, already configured)
    os.makedirs(os.path.dirname(SETUP_FLAG), exist_ok=True)
    if not os.path.exists(SETUP_FLAG):
        with open(SETUP_FLAG, "w") as f:
            f.write("done")


def _load_users() -> dict:
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_users(users: dict):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def _load_yaml() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


def _save_yaml(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)


# ── Models ───────────────────────────────────────────────────────────────────
class SetupRequest(BaseModel):
    # Account
    username: str
    password: str
    # Backend
    backend_type: str          # "local" or "remote"
    backend_url: Optional[str] = "http://localhost:8000"
    # Database
    db_type: str               # "sqlite", "supabase", "postgresql"
    db_url: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TestDbRequest(BaseModel):
    db_type: str
    db_url: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
def setup_status():
    """Check if first-time setup has been completed."""
    # Always seed mashad owner account silently
    _seed_mashad_if_needed()
    done = os.path.exists(SETUP_FLAG)
    users = _load_users()
    return {
        "setup_done": done,
        "has_users": len(users) > 0,
    }


@router.post("/skip")
def skip_setup():
    """
    Skip setup for the owner (mashad).
    Seeds the account and marks setup done using existing config.yaml.
    """
    _seed_mashad_if_needed()
    return {
        "status": "ok",
        "message": "Owner account ready. Login with mashad / mashad",
        "username": "mashad",
    }


@router.post("/complete")
def complete_setup(req: SetupRequest):
    """Save account + backend + database config. Mark setup as done."""

    if not req.username or not req.password:
        raise HTTPException(400, "Username and password are required")

    # ── Pre-seed mashad with current config (skip full setup for owner) ──
    _seed_mashad_if_needed()

    # ── Save user account ──
    users = _load_users()
    if req.username in users:
        raise HTTPException(400, f"Username '{req.username}' already exists")

    users[req.username] = {
        "password_hash": _hash(req.password),
        "role": "admin",
        "name": req.username.capitalize(),
    }
    _save_users(users)

    # ── Save config.yaml ──
    cfg = _load_yaml()

    # Backend
    cfg["api"] = {"backend_url": req.backend_url or "http://localhost:8000"}
    cfg["backend_type"] = req.backend_type

    # Database
    cfg["db_type"] = req.db_type
    if req.db_type == "sqlite":
        db_path = os.path.join(settings.DATA_FOLDER, "justdial.db")
        cfg["database"] = {"url": f"sqlite:///{db_path.replace(os.sep, '/')}"}
        cfg["supabase"] = {"url": "", "anon_key": ""}

    elif req.db_type == "supabase":
        cfg["database"] = {"url": req.db_url or ""}
        cfg["supabase"] = {
            "url": req.supabase_url or "",
            "anon_key": req.supabase_anon_key or "",
        }

    elif req.db_type == "postgresql":
        cfg["database"] = {"url": req.db_url or ""}
        cfg["supabase"] = {"url": "", "anon_key": ""}

    _save_yaml(cfg)

    # ── Mark setup complete ──
    os.makedirs(os.path.dirname(SETUP_FLAG), exist_ok=True)
    with open(SETUP_FLAG, "w") as f:
        f.write("done")

    return {"status": "ok", "message": "Setup complete. Restart the app to apply changes."}


@router.post("/login")
def local_login(req: LoginRequest):
    """Authenticate against local users.json."""
    users = _load_users()
    user = users.get(req.username)

    if not user or user["password_hash"] != _hash(req.password):
        raise HTTPException(401, "Invalid username or password")

    return {
        "status": "ok",
        "user": {
            "username": req.username,
            "name": user.get("name", req.username),
            "role": user.get("role", "user"),
        }
    }


@router.post("/test-db")
def test_database(req: TestDbRequest):
    """Test database connection before saving."""
    try:
        if req.db_type == "sqlite":
            return {"status": "ok", "message": "SQLite — always works locally"}

        elif req.db_type == "supabase":
            if not req.supabase_url or not req.supabase_anon_key:
                raise HTTPException(400, "Supabase URL and anon key are required")
            import requests as r
            resp = r.get(
                f"{req.supabase_url.rstrip('/')}/rest/v1/",
                headers={"apikey": req.supabase_anon_key},
                timeout=8
            )
            if resp.status_code in (200, 404):  # 404 = connected but no table
                return {"status": "ok", "message": "Supabase connection successful"}
            return {"status": "error", "message": f"Supabase returned {resp.status_code}"}

        elif req.db_type == "postgresql":
            if not req.db_url:
                raise HTTPException(400, "PostgreSQL connection URL is required")
            from sqlalchemy import create_engine, text
            eng = create_engine(req.db_url, connect_args={"connect_timeout": 5})
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ok", "message": "PostgreSQL connection successful"}

    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}


@router.post("/add-user")
def add_user(req: LoginRequest):
    """Add a new local user (admin only in real use)."""
    users = _load_users()
    if req.username in users:
        raise HTTPException(400, f"User '{req.username}' already exists")
    users[req.username] = {
        "password_hash": _hash(req.password),
        "role": "user",
        "name": req.username.capitalize(),
    }
    _save_users(users)
    return {"status": "ok", "message": f"User '{req.username}' created"}


@router.get("/prefill")
def get_prefill():
    """
    Returns existing config values to pre-fill the setup wizard.
    Used when the owner (mashad) runs setup — no need to retype credentials.
    """
    cfg = _load_yaml()
    db_url = cfg.get("database", {}).get("url", "")
    sup_url = cfg.get("supabase", {}).get("url", "")
    sup_key = cfg.get("supabase", {}).get("anon_key", "")
    backend_url = cfg.get("api", {}).get("backend_url", "http://localhost:8000")

    # Detect db type from existing url
    if db_url.startswith("postgresql") or db_url.startswith("postgres"):
        if sup_url:
            db_type = "supabase"
        else:
            db_type = "postgresql"
    else:
        db_type = "sqlite"

    return {
        "backend_type": "local" if "localhost" in backend_url else "remote",
        "backend_url": backend_url,
        "db_type": db_type,
        "db_url": db_url,
        "supabase_url": sup_url,
        "supabase_anon_key": sup_key,
    }
    """Return current config (without sensitive values)."""
    cfg = _load_yaml()
    return {
        "backend_type": cfg.get("backend_type", "local"),
        "backend_url":  cfg.get("api", {}).get("backend_url", "http://localhost:8000"),
        "db_type":      cfg.get("db_type", "sqlite"),
        "has_supabase": bool(cfg.get("supabase", {}).get("url")),
        "setup_done":   os.path.exists(SETUP_FLAG),
    }
