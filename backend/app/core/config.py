from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    symbol: str = "600938"
    sector_etf: str = "512880"
    wecom_webhook: str = ""
    quote_interval: float = 1.0
    api_host: str = "127.0.0.1"
    api_port: int = 10002
    # 本地默认项目 data/；生产在 .env 中设置 DB_PATH=/data/save/t0.db
    db_path: str = str(_ROOT / "data" / "t0.db")


settings = Settings()
