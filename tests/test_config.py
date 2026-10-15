"""Tests for the settings module."""

from app.config import Settings


def test_settings_defaults(monkeypatch):
    """Defaults are safe for local development and contain no secret."""
    for name in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "API_KEY"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    assert settings.neo4j_uri == "bolt://localhost:7687"
    assert settings.neo4j_password == ""
    assert settings.api_key == ""


def test_settings_read_environment(monkeypatch):
    """Environment variables override defaults."""
    monkeypatch.setenv("NEO4J_URI", "bolt://example:7687")
    assert Settings(_env_file=None).neo4j_uri == "bolt://example:7687"
