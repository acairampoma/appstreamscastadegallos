from pydantic_settings import BaseSettings
from typing import List
import json

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Cloudflare R2
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_ENDPOINT: str
    R2_BUCKET_NAME: str
    R2_PUBLIC_URL: str

    # Contabo VPS
    CONTABO_IP: str
    HLS_BASE_URL: str

    # CORS
    ALLOWED_ORIGINS: str = '["*"]'

    # Environment
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = True

    def get_allowed_origins(self) -> List[str]:
        """Parse ALLOWED_ORIGINS from JSON string"""
        try:
            return json.loads(self.ALLOWED_ORIGINS)
        except:
            return ["*"]

settings = Settings()
