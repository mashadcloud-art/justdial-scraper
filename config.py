import os
from app_config import CONFIG as APP_CONFIG

# Get data folder from app_config, or use default
DATA_FOLDER = APP_CONFIG["data"]["folder"]
os.makedirs(DATA_FOLDER, exist_ok=True)

class Settings:
    """Simple settings container without external dependencies."""
    DATA_FOLDER = DATA_FOLDER
    # Database URL – env var overrides config, else fallback to config or SQLite
    @property
    def DATABASE_URL(self) -> str:
        # Environment variable takes precedence
        env_url = os.getenv("DATABASE_URL")
        if env_url:
            return env_url
        # Config file URL if present
        cfg_url = APP_CONFIG.get("database", {}).get("url")
        if cfg_url:
            return cfg_url
        # Default to local SQLite DB in the data folder
        db_path = os.path.join(self.DATA_FOLDER, "justdial.db")
        return f"sqlite:///{db_path.replace(os.sep, '/') }"

    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    CLOUD_API_URL: str = APP_CONFIG.get("api", {}).get("backend_url", "")

settings = Settings()
