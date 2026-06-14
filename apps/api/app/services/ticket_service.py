from app.schemas.ticket import (
    RiskLevel,
    Ticket,
    TicketCreate,
    TicketIntent,
    TicketListResponse,
    TicketStatus,
    TicketUpdate,
    utc_now,
)


class TicketNotFoundError(Exception):
    pass


class TicketService:
    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}
        self._counter = 0

    def create_ticket(self, payload: TicketCreate) -> Ticket:
        self._counter += 1
        now = utc_now()
        ticket = Ticket(
            id=f"T{self._counter:08d}",
            user_id=payload.user_id,
            order_id=payload.order_id,
            message=payload.message,
            channel=payload.channel,
            created_at=now,
            updated_at=now,
        )
        self._tickets[ticket.id] = ticket
        return ticket

    def get_ticket(self, ticket_id: str) -> Ticket:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        return ticket

    def list_tickets(
        self,
        status: TicketStatus | None = None,
        intent: TicketIntent | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> TicketListResponse:
        tickets = list(self._tickets.values())

        if status is not None:
            tickets = [ticket for ticket in tickets if ticket.status == status]
        if intent is not None:
            tickets = [ticket for ticket in tickets if ticket.intent == intent]

        tickets.sort(key=lambda ticket: ticket.created_at, reverse=True)
        total = len(tickets)
        page = tickets[offset : offset + limit]

        return TicketListResponse(
            items=page,
            total=total,
            limit=limit,
            offset=offset,
        )

    def update_ticket(self, ticket_id: str, payload: TicketUpdate) -> Ticket:
        ticket = self.get_ticket(ticket_id)
        updates = payload.model_dump(exclude_unset=True)

        updated_ticket = ticket.model_copy(
            update={
                **updates,
                "updated_at": utc_now(),
            }
        )
        self._tickets[ticket_id] = updated_ticket
        return updated_ticket

    def reset(self) -> None:
        self._tickets.clear()
        self._counter = 0


ticket_service = TicketService()


def seed_demo_tickets() -> None:
    if ticket_service.list_tickets().total > 0:
        return

    ticket_service.create_ticket(
        TicketCreate(
            user_id="U1001",
            order_id="OD2026001",
            message="我买的耳机已经发货了，但是我现在不想要了，帮我退款。",
        )
    )
    ticket_service.update_ticket(
        "T00000001",
        TicketUpdate(
            intent=TicketIntent.refund_request,
            status=TicketStatus.created,
            risk_level=RiskLevel.medium,
        ),
    )

