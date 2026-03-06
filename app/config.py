from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación cargada desde variables de entorno o archivo .env.

    Attributes:
        supabase_url: URL del proyecto Supabase.
        supabase_service_key: Service role key de Supabase (acceso total, sin RLS).
        jwt_secret: Clave secreta para firmar y verificar JWT.
        jwt_algorithm: Algoritmo de firma JWT. Por defecto HS256.
        jwt_expire_hours: Duración del JWT en horas (SEC-004). Por defecto 1h.
        environment: Entorno de ejecución; "production" deshabilita /docs (SEC-006).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_key: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 1
    environment: str = "development"


settings = Settings()
