from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    anthropic_api_key: str = Field("", env="ANTHROPIC_API_KEY")
    binance_api_key: str = Field("", env="BINANCE_API_KEY")
    binance_secret_key: str = Field("", env="BINANCE_SECRET_KEY")
    alpaca_api_key: str = Field("", env="ALPACA_API_KEY")
    alpaca_secret_key: str = Field("", env="ALPACA_SECRET_KEY")
    secret_key: str = Field("dev-secret", env="SECRET_KEY")
    api_secret: str = Field("", env="API_SECRET")
    frontend_url: str = Field("", env="FRONTEND_URL")
    environment: str = Field("development", env="ENVIRONMENT")
    base_currency: str = Field("HKD", env="BASE_CURRENCY")
    upload_dir: str = "uploads"

    # IBKR Flex Web Service
    ibkr_flex_token: str = Field("", env="IBKR_FLEX_TOKEN")
    ibkr_flex_query_id: str = Field("", env="IBKR_FLEX_QUERY_ID")

    # Futu OpenD
    futu_host: str = Field("127.0.0.1", env="FUTU_HOST")
    futu_port: int = Field(11111, env="FUTU_PORT")
    futu_trade_password_md5: str = Field("", env="FUTU_TRADE_PASSWORD_MD5")

    model_config = {"env_file": ".env", "case_sensitive": False}


settings = Settings()
