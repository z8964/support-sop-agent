import hashlib
import os
import re
from pathlib import Path

from app.config import get_settings
from app.schemas.sop import (
    SopChunk,
    SopDocumentSummary,
    SopReindexResponse,
    SopSearchHit,
    SopSearchResponse,
)
from app.services.embedding_service import embedding_service
from app.services.vector_store import VectorDocument, vector_store


POLICY_TYPE_BY_FILE = {
    "refund_policy.md": "refund",
    "logistics_policy.md": "logistics",
    "invoice_policy.md": "invoice",
}


class SopService:
    def __init__(self, knowledge_base_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[4]
        env_path = os.getenv("SUPPORT_SOP_KNOWLEDGE_BASE")
        self.knowledge_base_path = (
            knowledge_base_path
            or (Path(env_path) if env_path else root / "knowledge_base")
        )
        self._chunks: list[SopChunk] = []
        self.settings = get_settings()

    def reindex(self) -> SopReindexResponse:
        chunks: list[SopChunk] = []

        for markdown_file in sorted(self.knowledge_base_path.glob("*.md")):
            policy_type = POLICY_TYPE_BY_FILE.get(
                markdown_file.name,
                markdown_file.stem.replace("_policy", ""),
            )
            chunks.extend(self._parse_markdown_file(markdown_file, policy_type))

        embedding_texts = [self._embedding_text(chunk) for chunk in chunks]
        embeddings = embedding_service.embed_many(embedding_texts)

        self._chunks = chunks
        vector_store.reset()
        vector_store.upsert(
            [
                VectorDocument(
                    id=chunk.id,
                    content=chunk.content,
                    metadata={
                        "source": chunk.source,
                        "section": chunk.section,
                        "policy_type": chunk.policy_type,
                    },
                    embedding=embedding,
                )
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ]
        )
        vector_store.set_index_metadata(
            {
                "knowledge_signature": self._knowledge_signature(),
                "embedding_signature": embedding_service.index_signature,
            }
        )

        return SopReindexResponse(
            status="ok",
            indexed_chunks=len(chunks),
            embedding_dimensions=embedding_service.dimensions,
            embedding_provider=embedding_service.provider_name,
            embedding_model=embedding_service.model_name,
            vector_store_backend=vector_store.backend_name,
            retrieval_mode="vector_hybrid",
            documents=self.list_documents(),
        )

    def list_documents(self) -> list[SopDocumentSummary]:
        self._ensure_index()

        summaries: dict[tuple[str, str], int] = {}
        for chunk in self._chunks:
            key = (chunk.source, chunk.policy_type)
            summaries[key] = summaries.get(key, 0) + 1

        return [
            SopDocumentSummary(
                source=source,
                policy_type=policy_type,
                chunk_count=chunk_count,
            )
            for (source, policy_type), chunk_count in sorted(summaries.items())
        ]

    def search(
        self,
        query: str,
        policy_type: str | None = None,
        top_k: int = 4,
    ) -> SopSearchResponse:
        self._ensure_index()

        query_embedding = embedding_service.embed(query)
        query_terms = self._tokenize(query)
        vector_results = vector_store.search(
            query_embedding=query_embedding,
            top_k=max(top_k * 4, top_k),
            where={"policy_type": policy_type} if policy_type else None,
        )

        chunk_by_id = {chunk.id: chunk for chunk in self._chunks}
        hits: list[SopSearchHit] = []
        for result in vector_results:
            chunk = chunk_by_id[result.document.id]
            chunk_terms = self._tokenize(
                f"{chunk.policy_type} {chunk.section} {chunk.content}"
            )
            matched_terms = sorted(query_terms.intersection(chunk_terms))
            keyword_score = self._keyword_score(query_terms, chunk_terms, chunk)
            hybrid_score = self._hybrid_score(result.vector_score, keyword_score)

            hits.append(
                SopSearchHit(
                    chunk=chunk,
                    score=hybrid_score,
                    vector_score=round(result.vector_score, 4),
                    keyword_score=round(keyword_score, 4),
                    matched_terms=matched_terms,
                )
            )

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return SopSearchResponse(
            query=query,
            policy_type=policy_type,
            retrieval_mode="vector_hybrid",
            embedding_provider=embedding_service.provider_name,
            embedding_model=embedding_service.model_name,
            vector_store_backend=vector_store.backend_name,
            hits=hits[:top_k],
        )

    def reset(self) -> None:
        self._chunks = []
        vector_store.reset()

    def _ensure_index(self) -> None:
        metadata = vector_store.get_index_metadata()
        index_is_current = (
            vector_store.count() > 0
            and metadata.get("knowledge_signature") == self._knowledge_signature()
            and metadata.get("embedding_signature")
            == embedding_service.index_signature
        )
        if index_is_current:
            if not self._chunks:
                self._restore_chunks()
            return
        self.reindex()

    def _restore_chunks(self) -> None:
        self._chunks = [
            SopChunk(
                id=document.id,
                source=str(document.metadata["source"]),
                section=str(document.metadata["section"]),
                policy_type=str(document.metadata["policy_type"]),
                content=document.content,
            )
            for document in vector_store.all_documents()
        ]

    def _knowledge_signature(self) -> str:
        digest = hashlib.sha256()
        for markdown_file in sorted(self.knowledge_base_path.glob("*.md")):
            digest.update(markdown_file.name.encode("utf-8"))
            digest.update(markdown_file.read_bytes())
        return digest.hexdigest()

    def _parse_markdown_file(self, markdown_file: Path, policy_type: str) -> list[SopChunk]:
        text = markdown_file.read_text(encoding="utf-8")
        current_section = markdown_file.stem
        current_lines: list[str] = []
        chunks: list[SopChunk] = []

        def flush() -> None:
            content = "\n".join(line.strip() for line in current_lines).strip()
            if not content:
                return
            chunk_number = len(chunks) + 1
            chunks.append(
                SopChunk(
                    id=f"{markdown_file.stem}_{chunk_number:03d}",
                    source=markdown_file.name,
                    section=current_section,
                    policy_type=policy_type,
                    content=content,
                )
            )

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith("## "):
                flush()
                current_section = line.removeprefix("## ").strip()
                current_lines = []
            elif line.startswith("# "):
                continue
            else:
                current_lines.append(raw_line)

        flush()
        return chunks

    def _embedding_text(self, chunk: SopChunk) -> str:
        return f"{chunk.policy_type}\n{chunk.source}\n{chunk.section}\n{chunk.content}"

    def _tokenize(self, text: str) -> set[str]:
        normalized = text.lower()
        latin = {
            token
            for token in re.findall(r"[a-z0-9_]+", normalized)
            if len(token) > 1
        }
        cjk = set(re.findall(r"[\u4e00-\u9fff]", normalized))
        return latin.union(cjk)

    def _keyword_score(
        self,
        query_terms: set[str],
        chunk_terms: set[str],
        chunk: SopChunk,
    ) -> float:
        if not query_terms:
            return 0.0

        overlap = query_terms.intersection(chunk_terms)
        if not overlap:
            return 0.0

        section_terms = self._tokenize(chunk.section)
        policy_terms = self._tokenize(chunk.policy_type)
        section_boost = len(overlap.intersection(section_terms)) * 1.5
        policy_boost = len(overlap.intersection(policy_terms)) * 1.0
        coverage = len(overlap) / len(query_terms)

        return len(overlap) + section_boost + policy_boost + coverage

    def _hybrid_score(self, vector_score: float, keyword_score: float) -> float:
        normalized_keyword = min(keyword_score / 8.0, 1.0)
        normalized_vector = (vector_score + 1.0) / 2.0
        vector_weight = self.settings.rag_vector_weight
        keyword_weight = self.settings.rag_keyword_weight
        weight_total = vector_weight + keyword_weight
        if weight_total <= 0:
            vector_weight, keyword_weight, weight_total = 0.7, 0.3, 1.0
        return round(
            (
                normalized_vector * vector_weight
                + normalized_keyword * keyword_weight
            )
            / weight_total,
            4,
        )


sop_service = SopService()
