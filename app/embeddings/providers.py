"""Configurable text embedding implementations."""

from __future__ import annotations

import hashlib
import math
from typing import Protocol, Sequence

from app.config import Settings


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashEmbeddingProvider:
    """Small deterministic embedding used for tests and offline diagnostics."""

    def __init__(self, dimension: int = 64) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        normalized = " ".join(text.strip().lower().split())
        tokens = normalized.split() or list(normalized)
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class SentenceTransformerEmbeddingProvider:
    """Lazy-loading local semantic embedding model."""

    def __init__(
        self,
        model_name: str,
        expected_dimension: int,
        local_files_only: bool = False,
    ) -> None:
        self.model_name = model_name
        self.expected_dimension = expected_dimension
        self.local_files_only = local_files_only
        self._model = None

    @property
    def dimension(self) -> int:
        return self.expected_dimension

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is required for semantic embeddings; "
                    "run `uv sync` to install project dependencies"
                ) from exc
            self._model = SentenceTransformer(
                self.model_name,
                local_files_only=self.local_files_only,
            )
            actual_dimension = self._model.get_embedding_dimension()
            if actual_dimension != self.expected_dimension:
                raise RuntimeError(
                    f"embedding dimension mismatch: configured "
                    f"{self.expected_dimension}, model reports {actual_dimension}"
                )
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load_model()
        vectors = model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vectors.tolist()


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider.strip().lower()
    if provider == "hash":
        return HashEmbeddingProvider(settings.embedding_dimension)
    if provider == "sentence_transformers":
        return SentenceTransformerEmbeddingProvider(
            settings.embedding_model,
            settings.embedding_dimension,
            settings.embedding_local_files_only,
        )
    raise ValueError(f"unsupported embedding provider: {settings.embedding_provider}")
