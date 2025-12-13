from enum import StrEnum
from functools import lru_cache
import os

from pydantic import AnyUrl, Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    dev = "dev"
    stage = "stage"
    prod = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(os.getenv("ENV_FILE", "../.env"), "../.env.dev", "../.env.stage", "../.env.prod"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_prefix="",
    )


    app_env: AppEnv = Field(default=AppEnv.dev, alias="APP_ENV", description="Application environment (dev/stage/prod)")

    pg_dsn: PostgresDsn | str = Field(default="", alias="PG_DSN", validation_alias="PG_DSN")

    openai_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENAI_API_KEY")

    neo4j_uri: str = Field(default="", alias="NEO4J_URI")
    neo4j_user: str = Field(default="", alias="NEO4J_USER")
    neo4j_password: SecretStr = Field(default=SecretStr(""), alias="NEO4J_PASSWORD")

    qdrant_url: AnyUrl = Field(default="http://qdrant:6333", alias="QDRANT_URL")

    prometheus_enabled: bool = Field(default=False, alias="PROMETHEUS_ENABLED")

    cors_allow_origins: str = Field(default="", alias="CORS_ALLOW_ORIGINS")

    admin_api_key: SecretStr = Field(default=SecretStr(""), alias="ADMIN_API_KEY")

    jwt_secret_key: SecretStr = Field(default=SecretStr(""), alias="JWT_SECRET_KEY")
    jwt_access_ttl_seconds: int = Field(default=900, alias="JWT_ACCESS_TTL_SECONDS")
    jwt_refresh_ttl_seconds: int = Field(default=1209600, alias="JWT_REFRESH_TTL_SECONDS")

    bootstrap_admin_email: str = Field(default="", alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: SecretStr = Field(default=SecretStr(""), alias="BOOTSTRAP_ADMIN_PASSWORD")

    kb_domain: str = Field(default="", alias="KB_DOMAIN")
    kb_alt_domain: str = Field(default="", alias="KB_ALT_DOMAIN")
    letsencrypt_email: str = Field(default="", alias="LETSENCRYPT_EMAIL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
