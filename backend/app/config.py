import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    analysis_model: str = "claude-sonnet-4-6"
    prescreen_model: str = "claude-haiku-4-5-20251001"
    embedding_model: str = "claude-haiku-4-5-20251001"

    # Ollama (LLM local). Si ollama_enabled=True el analyzer corre contra el
    # servidor local en `ollama_base_url`. Si está apagado o falla, cae a mock.
    ollama_enabled: bool = True
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_num_ctx: int = 16384
    ollama_timeout_seconds: int = 180

    scraper_timeout_seconds: int = 15

    frontend_origin: str = "http://localhost:5173"

    database_url: str = "sqlite:///./sesgometro.db"
    refresh_interval_minutes: int = 60
    articles_per_portal: int = 5
    run_initial_refresh: bool = True
    # En producción (Railway) querés esto en False: el scheduler local de la PC
    # del autor es el único que escribe; el backend desplegado solo sirve lectura.
    enable_scheduler: bool = True

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 30

    cluster_similarity_threshold: float = 0.62
    cluster_time_window_hours: int = 48

    @property
    def use_mock_analyzer(self) -> bool:
        return not self.ollama_enabled

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    @property
    def effective_jwt_secret(self) -> str:
        return self.jwt_secret.strip() or _EPHEMERAL_JWT_SECRET


_EPHEMERAL_JWT_SECRET = secrets.token_urlsafe(48)

settings = Settings()
