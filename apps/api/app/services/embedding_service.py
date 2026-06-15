import hashlib
import math
import re


class EmbeddingService:
    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in self._features(text):
            index = self._hash(token) % self.dimensions
            sign = 1.0 if self._hash(f"sign:{token}") % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def _features(self, text: str) -> list[str]:
        normalized = text.lower()
        latin_tokens = re.findall(r"[a-z0-9_]+", normalized)
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
        cjk_bigrams = [
            "".join(cjk_chars[index : index + 2])
            for index in range(max(len(cjk_chars) - 1, 0))
        ]
        cjk_trigrams = [
            "".join(cjk_chars[index : index + 3])
            for index in range(max(len(cjk_chars) - 2, 0))
        ]

        features: list[str] = []
        features.extend(token for token in latin_tokens if len(token) > 1)
        features.extend(cjk_chars)
        features.extend(cjk_bigrams)
        features.extend(cjk_trigrams)
        return features

    def _hash(self, value: str) -> int:
        digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, byteorder="big", signed=False)


embedding_service = EmbeddingService()

