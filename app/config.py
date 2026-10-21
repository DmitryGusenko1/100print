from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    telegram_bot_token: str = ""
    allowed_telegram_ids: list[int] = Field(default_factory=list)
    api_key: str
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4.1-mini"
    default_project_name: str = "General"
    api_host: str = "127.0.0.1"
    api_port: int = 8088
    max_message_chars: int = 20_000
    context_message_limit: int = 30
    context_search_limit: int = 12

    @field_validator("allowed_telegram_ids", mode="before")
    @classmethod
    def parse_ids(cls, value):
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [int(x.strip()) for x in value.split(",") if x.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
