from fastapi import APIRouter, HTTPException

from app.schemas.mock import (
    EscalationCreate,
    MockEscalation,
    MockLogistics,
    MockOrder,
    MockTicketHistoryItem,
    MockUser,
)
from app.services.mock_data import (
    LOGISTICS,
    ORDERS,
    TICKET_HISTORY,
    USERS,
    create_escalation,
)


router = APIRouter(prefix="/mock", tags=["mock"])


@router.get("/orders/{order_id}", response_model=MockOrder)
def get_order(order_id: str) -> MockOrder:
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/logistics/{order_id}", response_model=MockLogistics)
def get_logistics(order_id: str) -> MockLogistics:
    logistics = LOGISTICS.get(order_id)
    if logistics is None:
        raise HTTPException(status_code=404, detail="Logistics not found")
    return logistics


@router.get("/users/{user_id}", response_model=MockUser)
def get_user(user_id: str) -> MockUser:
    user = USERS.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/{user_id}/tickets", response_model=list[MockTicketHistoryItem])
def get_user_ticket_history(user_id: str) -> list[MockTicketHistoryItem]:
    if user_id not in USERS:
        raise HTTPException(status_code=404, detail="User not found")
    return TICKET_HISTORY.get(user_id, [])


@router.post("/escalations", response_model=MockEscalation, status_code=201)
def post_escalation(payload: EscalationCreate) -> MockEscalation:
    return create_escalation(payload)

