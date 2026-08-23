from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RESUME_", extra="ignore")

    data_dir: Path = Path(".data")
    max_upload_bytes: int = 10 * 1024 * 1024


settings = Settings()
