from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "ECL Platform API"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str = Field(min_length=32)

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    reload: bool = False

    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout: int = 30

    redis_url: str = "redis://localhost:6379/0"
    redis_celery_url: str = "redis://localhost:6379/1"
    redis_cache_ttl_default: int = 300

    jwt_private_key: str = ""
    jwt_public_key: str = ""
    jwt_key_id: str = "ecl-auth-2026-01"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "RS256"

    argon2_memory_cost: int = 65536
    argon2_time_cost: int = 3
    argon2_parallelism: int = 4

    cors_origins: str = "http://localhost:3000"

    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@eclplatform.com"
    smtp_from_name: str = "ECL Platform"
    smtp_tls: bool = True

    frontend_url: str = "http://localhost:3000"

    hibp_timeout_seconds: float = 2.0
    hibp_enabled: bool = True

    sentry_dsn: str = ""
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"
    release: str = "dev"

    rate_limit_enabled: bool = True

    lockout_threshold_1: int = 5
    lockout_threshold_2: int = 10
    lockout_threshold_3: int = 20

    metrics_token: str = ""

    celery_task_always_eager: bool = False

    refresh_cookie_name: str = "ecl_refresh"

    suppress_email_send: bool = False

    trust_proxy_headers: bool = False
    trusted_proxy_count: int = 1

    csrf_secret: str = "changeme-csrf-secret-32-chars-min"

    totp_issuer_name: str = "ECL Platform"
    totp_encryption_key: str = ""

    ip_hash_salt: str = "ecl-ip-hash-salt"

    storage_endpoint_url: str = "http://localhost:9000"
    storage_access_key: str = "minioadmin"
    storage_secret_key: str = "minioadmin"
    storage_bucket_name: str = "ecl-platform"
    storage_region: str = "us-east-1"
    max_upload_bytes: int = 52_428_800  # 50 MB

    compute_soft_time_limit: int = 1800
    compute_hard_time_limit: int = 2400

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list[str]) -> str:
        if isinstance(v, list):
            return ",".join(v)
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
