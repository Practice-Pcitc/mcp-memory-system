"""Application configuration loaded from environment variables."""

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the REST and MCP entry points."""

    app_name: str = "MCP Long-term Memory"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3308
    mysql_database: str = "memory_system"
    mysql_user: str = "appuser"
    mysql_password: str

    milvus_uri: str = "http://127.0.0.1:19530"
    milvus_collection: str = "memory_embeddings"

    elasticsearch_enabled: bool = False
    elasticsearch_url: str = "http://127.0.0.1:9200"
    elasticsearch_index: str = "memory_documents"

    embedding_provider: str = "sentence_transformers"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_dimension: int = 512
    embedding_local_files_only: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def mysql_url(self) -> str:
        """Build a SQLAlchemy URL while safely escaping credentials."""

        user = quote_plus(self.mysql_user)
        password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{user}:{password}@{self.mysql_host}:"
            f"{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
