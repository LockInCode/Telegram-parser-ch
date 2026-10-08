from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    api_hash: str
    api_id: int
    admin_id: str
    bot_username: str
    crypto_pay_token: Optional[str] = ""
    referral_percent: float = 15.0
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
