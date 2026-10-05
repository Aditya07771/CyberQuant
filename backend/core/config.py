import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field

# Determine backend base directory
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # Security
    SECRET_KEY: str = Field(default="cyberquant-secret-key-32-chars-minimum-for-security-purposes")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # Database
    DATABASE_URL: str = Field(default=f"sqlite:///{BACKEND_DIR / 'cyberquant.db'}")

    # Storage paths
    OUTPUT_BASE_DIR: Path = Field(default=BACKEND_DIR / "outputs")
    DATA_BASE_DIR: Path = Field(default=BACKEND_DIR / "data")
    MAX_UPLOAD_SIZE_BYTES: int = Field(default=52_428_800)  # 50 MB

    # Workers
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    USE_IN_PROCESS_WORKER: bool = Field(default=True)

    # CORS
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173")

    # SMTP Notifications
    SMTP_HOST: str = Field(default="smtp.example.com")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(default="alerts@example.com")
    SMTP_PASSWORD: str = Field(default="placeholder-smtp-password")
    SMTP_FROM: str = Field(default="alerts@cyberquant.local")
    SMTP_USE_TLS: bool = Field(default=True)
    SMTP_SIMULATED: bool = Field(default=True)

    # Webhooks
    WEBHOOK_TIMEOUT_SECONDS: int = Field(default=10)
    WEBHOOK_DEFAULT_SECRET: str = Field(default="placeholder-webhook-hmac-secret")

    # Threat Intelligence Feeds
    EPSS_API_URL: str = Field(default="https://api.first.org/data/v1/epss")
    CISA_KEV_URL: str = Field(default="https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json")
    THREAT_INTEL_CACHE_TTL_HOURS: int = Field(default=24)
    THREAT_INTEL_OFFLINE_MODE: bool = Field(default=False)

    # LLM Copilot
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = BACKEND_DIR / ".env"
        extra = "ignore"


settings = Settings()
