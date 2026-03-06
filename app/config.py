from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_key: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 1      # SEC-004: 1h para limitar ventana de tokens comprometidos
    environment: str = "development"  # SEC-006: controla exposición de /docs


settings = Settings()
