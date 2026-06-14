from fastapi import APIRouter, HTTPException

from app.schemas.review import (
    PendingReviewListResponse,
    ReviewRecord,
    ReviewResult,
    ReviewSubmit,
)
from app.services.review_service import ReviewNotAllowedError, review_service
from app.services.ticket_service import TicketNotFoundError


router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("/pending", response_model=PendingReviewListResponse)
def list_pending_reviews() -> PendingReviewListResponse:
    return review_service.list_pending_reviews()


@router.post("/{ticket_id}", response_model=ReviewResult)
def submit_review(ticket_id: str, payload: ReviewSubmit) -> ReviewResult:
    try:
        return review_service.submit_review(ticket_id, payload)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Ticket not found") from exc
    except ReviewNotAllowedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{ticket_id}", response_model=list[ReviewRecord])
def list_reviews(ticket_id: str) -> list[ReviewRecord]:
    try:
        return review_service.list_reviews(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Ticket not found") from exc

