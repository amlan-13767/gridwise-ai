from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str = "sqlite:///./gridwise.db"
    SECRET_KEY: str = "dev-insecure-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 480
    FRONTEND_URL: str = "http://localhost:3000"
    EXTRA_CORS_ORIGINS: str = ""
    MQTT_BROKER_URL: str = "mqtt://localhost:1883"
    MQTT_USERNAME: str = ""
    MQTT_PASSWORD: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    GRID_EMISSIONS_FACTOR: float = 0.82  # kgCO2/kWh, ADJUSTABLE ASSUMPTION - verify against official data
    ELECTRICITY_TARIFF: float = 6.0  # INR/kWh flat default, ADJUSTABLE ASSUMPTION
    DEMO_MODE: bool = True


settings = Settings()
