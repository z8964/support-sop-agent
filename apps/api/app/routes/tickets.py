from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.ticket import (
    Ticket,
    TicketCreate,
    TicketIntent,
    TicketListResponse,
    TicketStatus,
    TicketUpdate,
)
from app.services.ticket_service import TicketNotFoundError, ticket_service


router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.post("", response_model=Ticket, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate) -> Ticket:
    return ticket_service.create_ticket(payload)


@router.get("", response_model=TicketListResponse)
def list_tickets(
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    intent: TicketIntent | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TicketListResponse:
    return ticket_service.list_tickets(
        status=status_filter,
        intent=intent,
        limit=limit,
        offset=offset,
    )


@router.get("/{ticket_id}", response_model=Ticket)
def get_ticket(ticket_id: str) -> Ticket:
    try:
        return ticket_service.get_ticket(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Ticket not found") from exc


@router.patch("/{ticket_id}", response_model=Ticket)
def update_ticket(ticket_id: str, payload: TicketUpdate) -> Ticket:
    try:
        return ticket_service.update_ticket(ticket_id, payload)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Ticket not found") from exc

