from app.schemas.review import (
    PendingReviewItem,
    PendingReviewListResponse,
    ReviewAction,
    ReviewRecord,
    ReviewResult,
    ReviewStatus,
    ReviewSubmit,
    utc_now,
)
from app.schemas.ticket import TicketStatus, TicketUpdate
from app.services.ticket_service import TicketNotFoundError, ticket_service


class ReviewNotAllowedError(Exception):
    pass


class ReviewService:
    def __init__(self) -> None:
        self._reviews_by_ticket: dict[str, list[ReviewRecord]] = {}
        self._counter = 0

    def list_pending_reviews(self) -> PendingReviewListResponse:
        tickets = ticket_service.list_tickets(
            status=TicketStatus.pending_human_review,
            limit=100,
        ).items
        items = [
            PendingReviewItem(
                ticket_id=ticket.id,
                message=ticket.message,
                intent=ticket.intent.value,
                risk_level=ticket.risk_level,
                agent_reply=ticket.final_reply,
                reason="Ticket requires human review before final resolution.",
            )
            for ticket in tickets
        ]
        return PendingReviewListResponse(items=items, total=len(items))

    def submit_review(self, ticket_id: str, payload: ReviewSubmit) -> ReviewResult:
        ticket = ticket_service.get_ticket(ticket_id)
        if ticket.status != TicketStatus.pending_human_review:
            raise ReviewNotAllowedError(ticket_id)

        final_reply = self._resolve_final_reply(payload, ticket.final_reply)
        review_status = self._review_status(payload.action)
        ticket_status = self._ticket_status(payload.action)

        updated_ticket = ticket_service.update_ticket(
            ticket_id,
            TicketUpdate(
                status=ticket_status,
                need_human_review=False,
                final_reply=final_reply,
            ),
        )

        self._counter += 1
        review = ReviewRecord(
            id=f"R{self._counter:08d}",
            ticket_id=ticket_id,
            action=payload.action,
            status=review_status,
            agent_reply=ticket.final_reply,
            final_reply=final_reply,
            reviewer_id=payload.reviewer_id,
            comment=payload.comment,
            created_at=utc_now(),
        )
        self._reviews_by_ticket.setdefault(ticket_id, []).append(review)
        return ReviewResult(review=review, ticket=updated_ticket)

    def list_reviews(self, ticket_id: str) -> list[ReviewRecord]:
        ticket_service.get_ticket(ticket_id)
        return list(self._reviews_by_ticket.get(ticket_id, []))

    def reset(self) -> None:
        self._reviews_by_ticket.clear()
        self._counter = 0

    def _resolve_final_reply(self, payload: ReviewSubmit, agent_reply: str | None) -> str | None:
        if payload.action == ReviewAction.edit:
            if not payload.final_reply:
                raise ReviewNotAllowedError("Edit action requires final_reply")
            return payload.final_reply
        if payload.action == ReviewAction.approve:
            return payload.final_reply or agent_reply
        if payload.action == ReviewAction.reject:
            return payload.final_reply or agent_reply
        if payload.action == ReviewAction.escalate:
            return payload.final_reply or agent_reply
        return agent_reply

    def _review_status(self, action: ReviewAction) -> ReviewStatus:
        return {
            ReviewAction.approve: ReviewStatus.approved,
            ReviewAction.edit: ReviewStatus.edited,
            ReviewAction.reject: ReviewStatus.rejected,
            ReviewAction.escalate: ReviewStatus.escalated,
        }[action]

    def _ticket_status(self, action: ReviewAction) -> TicketStatus:
        return {
            ReviewAction.approve: TicketStatus.resolved,
            ReviewAction.edit: TicketStatus.resolved,
            ReviewAction.reject: TicketStatus.failed,
            ReviewAction.escalate: TicketStatus.escalated,
        }[action]


review_service = ReviewService()

