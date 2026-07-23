import os
import yaml
from typing import Dict, Any

# Path to the YAML config file
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

# Default config (matches current app behavior for backward compatibility)
DEFAULT_CONFIG = {
    "data": {
        "folder": os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    },
    "database": {
        "url": None  # If None, use the default from old config.py
    },
    "storage": {
        "provider": "local"  # "local", "cloudinary", "oracle", "azure", "aws"
    },
    "ui": {
        "theme": "superhero"
    },
    "api": {
        "backend_url": "http://localhost:8000"
    },
    "supabase": {
        "url": "",
        "anon_key": ""
    }
}


def load_config() -> Dict[str, Any]:
    """Load config from YAML file, or create default if it doesn't exist"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded_config = yaml.safe_load(f)
                # Merge with default config to ensure all keys exist
                return merge_configs(DEFAULT_CONFIG, loaded_config or {})
        except Exception as e:
            print(f"⚠️  Failed to load config file: {str(e)}")
            return DEFAULT_CONFIG.copy()
    else:
        # Create default config file
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    """Save config to YAML file"""
    try:
        # Ensure the parent directory exists
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        print(f"⚠️  Failed to save config file: {str(e)}")


def merge_configs(default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge override config into default recursively"""
    merged = default.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged


# Global config instance
CONFIG = load_config()
