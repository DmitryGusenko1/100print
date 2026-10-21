from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    telegram_bot_token: str = ""
    database_url: str = "postgresql+asyncpg://ai_brain:change_me@localhost:5432/ai_brain"


settings = Settings()
