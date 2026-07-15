"""
Auth module business logic: local user accounts (data/users.json) and
first-time setup config (config.yaml), separate from routing concerns.
"""
import os
import json
import hashlib
import yaml
from typing import Optional

from config import settings

_ROOT = os.path.dirname(settings.DATA_FOLDER)
CONFIG_FILE = os.path.join(_ROOT, "config.yaml")
USERS_FILE = os.path.join(settings.DATA_FOLDER, "users.json")
SETUP_FLAG = os.path.join(settings.DATA_FOLDER, ".setup_done")


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def load_users() -> dict:
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_users(users: dict):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def load_yaml() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


def save_yaml(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)


def is_setup_done() -> bool:
    return os.path.exists(SETUP_FLAG)


def mark_setup_done():
    os.makedirs(os.path.dirname(SETUP_FLAG), exist_ok=True)
    with open(SETUP_FLAG, "w") as f:
        f.write("done")


def seed_mashad_if_needed():
    """
    Pre-seed the 'mashad' owner account with the current config.yaml credentials.
    This runs once — if mashad already exists, does nothing.
    """
    users = load_users()
    if "mashad" in users:
        return  # already seeded

    users["mashad"] = {
        "password_hash": hash_password("mashad"),
        "role": "superadmin",
        "name": "Mashad",
        "preset": True,  # marker: this account uses existing config.yaml as-is
    }
    save_users(users)

    # Mark setup done if not already (mashad = owner, already configured)
    if not is_setup_done():
        mark_setup_done()


def get_current_user_from_token(token_payload: dict) -> Optional[dict]:
    return {
        "user_id": token_payload.get("sub"),
        "email": token_payload.get("email"),
    }
