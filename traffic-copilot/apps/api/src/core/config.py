"""
Application configuration via pydantic-settings.

All values can be overridden via environment variables or a .env file located
at the repository root (or wherever the process is started from).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ #
    # LLM                                                                  #
    # ------------------------------------------------------------------ #
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048

    # ------------------------------------------------------------------ #
    # Persistence                                                          #
    # ------------------------------------------------------------------ #
    database_url: str  # asyncpg DSN, e.g. postgresql+asyncpg://user:pw@host/db
    redis_url: str = "redis://localhost:6379/0"

    # ------------------------------------------------------------------ #
    # Kafka                                                                #
    # ------------------------------------------------------------------ #
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group_id: str = "trafficcopilot-api"

    # ------------------------------------------------------------------ #
    # Auth / Security                                                      #
    # ------------------------------------------------------------------ #
    secret_key: str = "dev-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ------------------------------------------------------------------ #
    # Runtime                                                              #
    # ------------------------------------------------------------------ #
    environment: str = "development"  # "development" | "production" | "test"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ------------------------------------------------------------------ #
    # OSM / Routing                                                        #
    # ------------------------------------------------------------------ #
    osm_place_name: str = "Manhattan, New York, USA"
    osm_graph_cache: str = "/app/data/processed/graph.gpickle"

    # ------------------------------------------------------------------ #
    # Detection                                                            #
    # ------------------------------------------------------------------ #
    detection_confidence_threshold: float = 0.5

    # ------------------------------------------------------------------ #
    # Prompts                                                              #
    # ------------------------------------------------------------------ #
    prompts_dir: str = "/app/prompts"

    # ------------------------------------------------------------------ #
    # Derived helpers                                                      #
    # ------------------------------------------------------------------ #
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def is_test(self) -> bool:
        return self.environment.lower() == "test"


# Module-level singleton — import this everywhere.
settings = Settings()
