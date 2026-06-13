from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database connection (Updated to port 5433)
    DATABASE_URL: str = "postgresql://postgres:Heer123@localhost:5433/justdial_db"
    
    # API settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Cloud API URL (Change this to your Oracle VM IP when deploying)
    CLOUD_API_URL: str = "http://localhost:8000"
    
    class Config:
        env_file = ".env"

settings = Settings()