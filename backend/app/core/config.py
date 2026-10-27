from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str
    environment: Literal["development", "production", "test"]
    api_prefix: str

    debug: bool = False

    postgres_db: str
    postgres_host: str
    postgres_user: str
    postgres_port: int
    postgres_password: SecretStr

    session_cookie_name: str = "sentinel_session"
    # Must be True once the API is served over HTTPS; browsers drop Secure cookies on plain http.
    session_cookie_secure: bool = False

    # JSON array of exact browser origins, including the frontend port.
    cors_allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Shared secret the worker sends in the X-API-Key header to create events.
    worker_api_key: SecretStr

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
