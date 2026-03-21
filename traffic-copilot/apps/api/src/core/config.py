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
    # HuggingFace Inference API — free tier, no local model download.
    # Get a free token at https://huggingface.co/settings/tokens (read access).
    # If blank, falls back to deterministic mock embeddings.
    hf_api_token: str = ""
    # Model served by the HF Inference API.
    # all-MiniLM-L6-v2 = 384-dim, fast, free tier.  Output is padded to embedding_dim.
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "auto"
    embedding_dim: int = 1024
    # Set to true to bypass all embedding APIs and use fast deterministic mock.
    embedding_use_mock: bool = False
    # Vision analysis via HF Inference API (CLIP zero-shot image classification).
    hf_vision_model: str = "google/vit-base-patch16-224"
    vision_confidence_threshold: float = 0.3

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
    # Dev feed replay                                                      #
    # ------------------------------------------------------------------ #
    replay_scenario_dir: str = "/app/data/replays/scenario_1"
    replay_interval_seconds: float = 3.0

    # ------------------------------------------------------------------ #
    # Twilio SMS                                                           #
    # ------------------------------------------------------------------ #
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_to_number: str = ""  # Default recipient; overridden per-request when phone_number is set

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
