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
    matched_terms: list[str]


class SopSearchResponse(BaseModel):
    query: str
    policy_type: str | None
    hits: list[SopSearchHit]


class SopReindexResponse(BaseModel):
    status: str
    indexed_chunks: int
    documents: list[SopDocumentSummary]

