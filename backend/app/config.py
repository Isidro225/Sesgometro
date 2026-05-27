import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Proveedor del analyzer: "anthropic" (Claude API), "ollama" (LLM local) o
    # "mock" (determinista por hash, para desarrollar UI sin LLM).
    # Default anthropic: el system prompt está diseñado para Claude y Haiku 4.5
    # lo sigue sin los parches anti-qwen. Si falla la llamada, analyze() cae a mock
    # para no romper el pipeline.
    analyzer_provider: str = "anthropic"

    anthropic_api_key: str = ""
    # Haiku 4.5 para todo el análisis. El system prompt (~8k tokens) se cachea con
    # prompt caching, así que el costo por nota posterior es marginal.
    analysis_model: str = "claude-haiku-4-5-20251001"
    anthropic_max_tokens: int = 2048
    # NOTA: Anthropic no expone API de embeddings y Haiku es un modelo de chat, no
    # de embeddings. El clustering usa TF sparse local (app/embeddings.py); estos
    # campos quedan sin uso y solo se conservan por compat con .env viejos.
    prescreen_model: str = "claude-haiku-4-5-20251001"
    embedding_model: str = "claude-haiku-4-5-20251001"

    # Ollama (LLM local). Solo se usa si analyzer_provider="ollama".
    ollama_enabled: bool = True
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_num_ctx: int = 16384
    ollama_timeout_seconds: int = 180

    # Si está activo, el analyzer recibe la orientación editorial promedio del
    # medio (económico + peronismo) como tie-breaker SOLO para PASO 1 ambiguo.
    # No es input al score base. Off por default para poder comparar A/B contra
    # análisis ciegos.
    use_source_prior: bool = False

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
        return self.analyzer_provider == "mock"

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    @property
    def effective_jwt_secret(self) -> str:
        return self.jwt_secret.strip() or _EPHEMERAL_JWT_SECRET


_EPHEMERAL_JWT_SECRET = secrets.token_urlsafe(48)

settings = Settings()
