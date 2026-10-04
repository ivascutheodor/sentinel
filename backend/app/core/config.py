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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
