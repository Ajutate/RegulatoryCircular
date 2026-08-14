"""
LLM Client Factory
===================
Creates and caches a ChatOpenAI instance pointed at the LiteLLM proxy,
which in turn routes to an Ollama model running locally.

LiteLLM acts as an OpenAI-compatible gateway, so LangChain's ChatOpenAI
works unchanged regardless of whether the underlying model is Ollama,
OpenAI, or any other provider.

Model name format in .env:
  ollama/llama3.1      → LiteLLM routes to Ollama with model "llama3.1"
  ollama/qwen2.5:7b    → LiteLLM routes to Ollama with model "qwen2.5:7b"
"""

from functools import lru_cache

from langchain_openai import ChatOpenAI

from config.settings import get_settings


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """
    Return a cached ChatOpenAI instance configured for the LiteLLM proxy.

    The instance points to the LiteLLM proxy (LITELLM_BASE_URL), which
    translates the OpenAI-format request into an Ollama API call.
    """
    settings = get_settings()

    # Ollama models running via LiteLLM proxy benefit from:
    #   - higher timeout (local inference is slower than cloud APIs)
    #   - max_retries=1 (avoid hammering a resource-constrained local GPU)
    return ChatOpenAI(
        model=settings.llm_model,           # e.g. "ollama/llama3.1"
        base_url=settings.litellm_base_url,  # e.g. "http://localhost:4000"
        api_key=settings.litellm_api_key,    # LiteLLM master_key (any value)
        temperature=settings.llm_temperature,
        timeout=600,     # 10 min — local models can be slow on first call
        max_retries=1,
    )
