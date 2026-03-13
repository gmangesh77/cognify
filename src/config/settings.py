from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COGNIFY_")

    app_name: str = "Cognify"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    cors_allowed_origins: list[str] = ["http://localhost:3000"]
    rate_limit_default: str = "100/minute"
    api_v1_prefix: str = "/api/v1"
    jwt_private_key: str = ""
    jwt_public_key: str = ""
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
