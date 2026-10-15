"""Application settings loaded from environment variables (see .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from the environment or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
