from fastapi import APIRouter, Query

from app.schemas.memory import MemoryCreate, MemoryListResponse, MemoryRecord
from app.services.memory_service import memory_service


router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/users/{user_id}", response_model=MemoryListResponse)
def list_user_memories(
    user_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    memory_type: str | None = Query(default=None, alias="type"),
) -> MemoryListResponse:
    return memory_service.list_user_memories(
        user_id=user_id,
        limit=limit,
        memory_type=memory_type,
    )


@router.post("", response_model=MemoryRecord, status_code=201)
def create_memory(payload: MemoryCreate) -> MemoryRecord:
    return memory_service.create_memory(payload)

