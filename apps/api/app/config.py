from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Support SOP Agent API"
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "sqlite:///./support_sop_agent.db"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    vector_store_path: str = "./chroma"
    rag_top_k: int = 4
    rag_embedding_provider: str = "hash"
    rag_vector_store_backend: str = "sqlite"
    rag_vector_store_path: str = "./data/sop_vectors.sqlite3"
    rag_vector_weight: float = 0.7
    rag_keyword_weight: float = 0.3
    agent_tool_max_attempts: int = 3
    agent_max_steps: int = 10
    tool_store_path: str = "./data/tool_gateway.sqlite3"
    memory_store_path: str = "./data/memories.sqlite3"
    memory_retrieval_top_k: int = 5
    memory_min_confidence: float = 0.5
    high_amount_threshold: int = 500
    low_confidence_threshold: float = 0.7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
