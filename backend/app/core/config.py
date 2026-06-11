import os
from pydantic_settings import BaseSettings
from typing import Optional

# 确保 .env 路径始终基于 config.py 所在目录，而非启动时的 CWD
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env")


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://indicator:indicator_pass@localhost:5432/indicator_db"
    redis_url: str = "redis://localhost:6379/0"
    watch_dir: str = "C:\\Users\\USER370107\\Documents\\yidongbangong\\15902981622\\filerecv"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: str = "openai/gpt-oss-120b:free"
    wxpusher_app_token: Optional[str] = None

    class Config:
        env_file = _ENV_PATH
        extra = "ignore"


settings = Settings()
