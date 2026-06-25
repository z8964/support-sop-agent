from fastapi import APIRouter, Query

from app.schemas.tool import ToolAuditListResponse
from app.services.business_tool_service import business_tool_service


router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("/audits", response_model=ToolAuditListResponse)
def list_tool_audits(
    limit: int = Query(default=50, ge=1, le=200),
    tool_name: str | None = None,
    status: str | None = None,
) -> ToolAuditListResponse:
    return business_tool_service.list_audits(
        limit=limit,
        tool_name=tool_name,
        status=status,
    )
