from fastapi import APIRouter

from app.schemas.sop import (
    SopDocumentSummary,
    SopReindexResponse,
    SopSearchRequest,
    SopSearchResponse,
)
from app.services.sop_service import sop_service


router = APIRouter(prefix="/api/sops", tags=["sops"])


@router.get("", response_model=list[SopDocumentSummary])
def list_sops() -> list[SopDocumentSummary]:
    if not sop_service.list_documents():
        sop_service.reindex()
    return sop_service.list_documents()


@router.post("/reindex", response_model=SopReindexResponse)
def reindex_sops() -> SopReindexResponse:
    return sop_service.reindex()


@router.post("/search", response_model=SopSearchResponse)
def search_sops(payload: SopSearchRequest) -> SopSearchResponse:
    return sop_service.search(
        query=payload.query,
        policy_type=payload.policy_type,
        top_k=payload.top_k,
    )

