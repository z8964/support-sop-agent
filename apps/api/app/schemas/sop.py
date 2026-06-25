from pydantic import BaseModel, Field


class SopChunk(BaseModel):
    id: str
    source: str
    section: str
    policy_type: str
    content: str


class SopDocumentSummary(BaseModel):
    source: str
    policy_type: str
    chunk_count: int


class SopSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    policy_type: str | None = None
    top_k: int = Field(default=4, ge=1, le=10)


class SopSearchHit(BaseModel):
    chunk: SopChunk
    score: float
    vector_score: float
    keyword_score: float
    matched_terms: list[str]


class SopSearchResponse(BaseModel):
    query: str
    policy_type: str | None
    retrieval_mode: str
    embedding_provider: str
    embedding_model: str
    vector_store_backend: str
    hits: list[SopSearchHit]


class SopReindexResponse(BaseModel):
    status: str
    indexed_chunks: int
    embedding_dimensions: int
    embedding_provider: str
    embedding_model: str
    vector_store_backend: str
    retrieval_mode: str
    documents: list[SopDocumentSummary]
