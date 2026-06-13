import os
from pydantic_settings import BaseSettings
from app_config import CONFIG as APP_CONFIG

# Get data folder from app_config, or use default
DATA_FOLDER = APP_CONFIG["data"]["folder"]
os.makedirs(DATA_FOLDER, exist_ok=True)

class Settings(BaseSettings):
    # Base data folder (all other paths are relative to this)
    DATA_FOLDER: str = DATA_FOLDER
    
    # Database connection (use app_config if set, else default SQLite)
    @property
    def DATABASE_URL(self) -> str:
        if APP_CONFIG["database"]["url"]:
            return APP_CONFIG["database"]["url"]
        # Default SQLite DB in data folder
        db_path = os.path.join(self.DATA_FOLDER, "justdial.db")
        return f"sqlite:///{db_path.replace(os.sep, '/')}"
    
    # API settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Cloud API URL (from app_config or default)
    CLOUD_API_URL: str = APP_CONFIG["api"]["backend_url"]
    
    class Config:
        env_file = ".env"

settings = Settings()
