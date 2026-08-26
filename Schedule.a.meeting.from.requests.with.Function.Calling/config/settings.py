# config/settings.py

from typing import Literal
from functools import lru_cache
from pydantic import (
    BaseModel,
    EmailStr,
    PostgresDsn,
    RedisDsn,
    AnyHttpUrl,
    HttpUrl,
    SecretStr,
    Field,
    field_validator,
)


from pydantic_settings import BaseSettings, SettingsConfigDict


# 1. Define Sub-Configs using standard BaseModel
class AppConfig(BaseModel):
    name: str = "My FastAPI Application"
    description: str = 100
    env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"


class SecurityConfig(BaseModel):
    # secret_key: str
    session_secret: str = 32
    # algorithm: str = "HS256"
    front_end_url: int = 100
    allow_origins: list[AnyHttpUrl] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    allow_credentials: bool = True
    allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])
    # Master key represented as a 64-character hex string (256-bit AES key)
    app_master_key: str = Field(
        ...,
        description="64-character hex-encoded string representing a 32-byte master key",
    )

    @field_validator("app_master_key")
    @classmethod
    def validate_master_key_hex(cls, v: str) -> str:
        # 1. Strip whitespace
        key_str = v.strip()

        # 2. Check strict length for 256-bit key (32 bytes = 64 hex characters)
        if len(key_str) != 64:
            raise ValueError(
                "APP_MASTER_KEY must be exactly 64 hex characters (32 bytes / 256 bits long)."
            )

        # 3. Ensure string is valid hex by attempting conversion
        try:
            bytes.fromhex(key_str)
        except ValueError:
            raise ValueError("APP_MASTER_KEY must be a valid hex-encoded string.")

        return key_str


class DatabaseConfig(BaseModel):
    async_url: PostgresDsn
    sync_url: PostgresDsn
    pool_size: int = 20
    max_overflow: int = 10


class RedisConfig(BaseModel):
    dsn: RedisDsn = Field(alias="url")
    sync_db: int = 0
    async_db: int = 1
    dlq_key: str = Field(
        default="calendar_tasks:dead_letter",
        description="Key used for pushing dead letter queue payloads",
    )

    @property
    def url(self) -> str:
        """Constructs a standard Redis connection URL.
        Wehn to Use: celery_tasks, sync_background_workers, cli_scripts
        """
        return f"{self.url}/{self.sync_db}"

    @property
    def async_url(self) -> str:
        """Constructs an async Redis connection URL if using redis-py async features.
        Wehn to Use: FastAPI route handlers, Asyncio background loops
        """
        return f"{self.url}/{self.async_db}"


# Google OAuth 2.0 Configuration
class GoogleOAuthConfig(BaseModel):
    client_id: str = Field(
        ..., description="Google OAuth Client ID ending in .apps.googleusercontent.com"
    )
    client_secret: SecretStr = Field(
        ..., description="Google OAuth Client Secret protected as a SecretStr"
    )
    redirect_url: HttpUrl = Field(
        ...,
        description="OAuth Redirect URI matching Google Cloud Console configuration",
    )

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, v: str) -> str:
        client_id = v.strip()
        if not client_id.endswith(".apps.googleusercontent.com"):
            raise ValueError(
                "Invalid Google client_id: Must end with '.apps.googleusercontent.com'"
            )
        return client_id


# 2. LLM Model Provider Configuration
class LLMModelProviderConfig(BaseModel):
    gemini_api_key: SecretStr = Field(..., description="Google Gemini API Key")
    open_router_api_key: SecretStr = Field(
        ..., description="OpenRouter API Key for fallback/multi-model routing"
    )

    @field_validator("gemini_api_key", "open_router_api_key")
    @classmethod
    def validate_api_keys(cls, v: SecretStr) -> SecretStr:
        raw_key = v.get_secret_value().strip()
        if not raw_key or len(raw_key) < 10:
            raise ValueError("API Key appears invalid or too short.")
        return v


# Rate Limiting Configuration
class RateLimitingConfig(BaseModel):
    rate_limit_per_minute: int = 100
    max_file_upload_size_mb: int = 10
    request_timeout_seconds: int = 30


# Main Settings Model combining sub-configs
class Settings(BaseSettings):
    app: AppConfig = Field(default_factory=AppConfig)
    security: SecurityConfig
    db: DatabaseConfig
    redis: RedisConfig
    google_oauth: GoogleOAuthConfig
    llm: LLMModelProviderConfig

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Uses '__' to map env vars to nested fields (e.g., DB__URL maps to settings.db.url)
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )


# # JET Auth
# class JWTAuthConfig(BaseModel):
#     access_token_expire_minutes: int = 30
#     refresh_token_expire_days: int = 7


# # Email Configuration
# class EmailConfig(BaseModel):
#     smtp_host: str
#     smtp_port: int = 587
#     smtp_user: str
#     smtp_password: str
#     from_email: EmailStr


# # STRIPE Configuration
# class StripeConfig(BaseModel):
#     secret_key: str
#     webhook_secret: str


# # AWS Configuration
# class AWSConfig(BaseModel):
#     s3_bucket_name: str
#     access_key_id: str
#     secret_access_key: str
#     region: str = "us-east-1"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
