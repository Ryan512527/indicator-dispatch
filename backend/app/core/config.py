from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://indicator:indicator_pass@localhost:5432/indicator_db"
    redis_url: str = "redis://localhost:6379/0"
    watch_dir: str = "/data"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    wxpusher_app_token: Optional[str] = None

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
