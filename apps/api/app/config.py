from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/wellness_radar"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_viewer_token: str = ""
    api_analyst_token: str = ""
    api_admin_token: str = ""
    ai_cost_alert_threshold_usd: float = 25.0
    wr_alert_webhook_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
