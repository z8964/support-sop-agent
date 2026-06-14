import re
from pathlib import Path

from app.schemas.sop import (
    SopChunk,
    SopDocumentSummary,
    SopReindexResponse,
    SopSearchHit,
    SopSearchResponse,
)


POLICY_TYPE_BY_FILE = {
    "refund_policy.md": "refund",
    "logistics_policy.md": "logistics",
    "invoice_policy.md": "invoice",
}


class SopService:
    def __init__(self, knowledge_base_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[4]
        self.knowledge_base_path = knowledge_base_path or root / "knowledge_base"
        self._chunks: list[SopChunk] = []

    def reindex(self) -> SopReindexResponse:
        chunks: list[SopChunk] = []

        for markdown_file in sorted(self.knowledge_base_path.glob("*.md")):
            policy_type = POLICY_TYPE_BY_FILE.get(
                markdown_file.name,
                markdown_file.stem.replace("_policy", ""),
            )
            chunks.extend(self._parse_markdown_file(markdown_file, policy_type))

        self._chunks = chunks
        return SopReindexResponse(
            status="ok",
            indexed_chunks=len(chunks),
            documents=self.list_documents(),
        )

    def list_documents(self) -> list[SopDocumentSummary]:
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
        if not self._chunks:
            self.reindex()

        query_terms = self._tokenize(query)
        candidates = [
            chunk
            for chunk in self._chunks
            if policy_type is None or chunk.policy_type == policy_type
        ]

        hits: list[SopSearchHit] = []
        for chunk in candidates:
            chunk_terms = self._tokenize(
                f"{chunk.policy_type} {chunk.section} {chunk.content}"
            )
            matched_terms = sorted(query_terms.intersection(chunk_terms))
            score = self._score(query_terms, chunk_terms, chunk)
            if score > 0:
                hits.append(
                    SopSearchHit(
                        chunk=chunk,
                        score=score,
                        matched_terms=matched_terms,
                    )
                )

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return SopSearchResponse(
            query=query,
            policy_type=policy_type,
            hits=hits[:top_k],
        )

    def reset(self) -> None:
        self._chunks = []

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

    def _tokenize(self, text: str) -> set[str]:
        normalized = text.lower()
        return {
            token
            for token in re.findall(r"[a-z0-9_]+", normalized)
            if len(token) > 1
        }

    def _score(self, query_terms: set[str], chunk_terms: set[str], chunk: SopChunk) -> float:
        if not query_terms:
            return 0

        overlap = query_terms.intersection(chunk_terms)
        if not overlap:
            return 0

        section_terms = self._tokenize(chunk.section)
        policy_terms = self._tokenize(chunk.policy_type)
        section_boost = len(overlap.intersection(section_terms)) * 1.5
        policy_boost = len(overlap.intersection(policy_terms)) * 1.0
        coverage = len(overlap) / len(query_terms)

        return round(len(overlap) + section_boost + policy_boost + coverage, 4)


sop_service = SopService()

