from app.schemas.trace import TicketTrace, TraceStep, utc_now


class TraceNotFoundError(Exception):
    pass


class TraceService:
    def __init__(self) -> None:
        self._traces_by_ticket: dict[str, list[TicketTrace]] = {}
        self._counter = 0

    def save_trace(self, ticket_id: str, steps: list[dict]) -> TicketTrace:
        self._counter += 1
        trace = TicketTrace(
            trace_id=f"TR{self._counter:08d}",
            ticket_id=ticket_id,
            steps=[TraceStep(**step) for step in steps],
            created_at=utc_now(),
        )
        self._traces_by_ticket.setdefault(ticket_id, []).append(trace)
        return trace

    def get_latest_trace(self, ticket_id: str) -> TicketTrace:
        traces = self._traces_by_ticket.get(ticket_id, [])
        if not traces:
            raise TraceNotFoundError(ticket_id)
        return traces[-1]

    def list_traces(self, ticket_id: str) -> list[TicketTrace]:
        return list(self._traces_by_ticket.get(ticket_id, []))

    def reset(self) -> None:
        self._traces_by_ticket.clear()
        self._counter = 0


trace_service = TraceService()

