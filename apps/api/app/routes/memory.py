from fastapi import APIRouter, HTTPException, Query

from app.schemas.memory import (
    MemoryCreate,
    MemoryListResponse,
    MemoryRecord,
    MemoryRetrieveRequest,
    MemoryRetrieveResponse,
)
from app.services.memory_service import MemoryNotFoundError, memory_service


router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/users/{user_id}", response_model=MemoryListResponse)
def list_user_memories(
    user_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    memory_type: str | None = Query(default=None, alias="type"),
    include_inactive: bool = False,
) -> MemoryListResponse:
    return memory_service.list_user_memories(
        user_id=user_id,
        limit=limit,
        memory_type=memory_type,
        include_inactive=include_inactive,
    )


@router.post("", response_model=MemoryRecord, status_code=201)
def create_memory(payload: MemoryCreate) -> MemoryRecord:
    return memory_service.create_memory(payload)


@router.post("/retrieve", response_model=MemoryRetrieveResponse)
def retrieve_memories(
    payload: MemoryRetrieveRequest,
) -> MemoryRetrieveResponse:
    return memory_service.retrieve(
        user_id=payload.user_id,
        query=payload.query,
        intent=payload.intent,
        top_k=payload.top_k,
    )


@router.delete("/{memory_id}", response_model=MemoryRecord)
def forget_memory(memory_id: str) -> MemoryRecord:
    try:
        return memory_service.forget_memory(memory_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Memory not found") from exc
