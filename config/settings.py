"""
Application Settings
====================
Pydantic BaseSettings that auto-loads configuration from the .env file.
Single source of truth for all LiteLLM and LLM parameters.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # LiteLLM Proxy (routes to Ollama)
    litellm_base_url: str = "http://localhost:4000"
    litellm_api_key: str = "sk-dummy-key"

    # LLM Parameters — Ollama model name (with ollama/ prefix so LiteLLM routes correctly)
    llm_model: str = "ollama/llama3.1"
    llm_temperature: float = 0.0

    # App metadata
    app_name: str = "Regulatory Circular Analyzer"
    app_version: str = "1.0.0"

    # Database
    database_url: str = "sqlite:///./data/history.db"

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()


# Known models for the UI selector
# ── Current: Ollama (local) ──
KNOWN_OLLAMA_MODELS = [
    "ollama/llama3.1",
    "ollama/llama3.2",
    "ollama/qwen2.5:7b",
    "ollama/qwen2.5:14b",
    "ollama/mistral",
    "ollama/mistral-nemo",
    "ollama/gemma2:9b",
    "ollama/gemma2:2b",
    "ollama/phi3.5",
    "ollama/deepseek-r1:7b",
    # ── Future: Gemini (swap LLM_MODEL in .env when ready) ──
    "gemini/gemini-2.5-flash",
    "gemini/gemini-2.0-flash",
    "gemini/gemini-1.5-pro",
]
