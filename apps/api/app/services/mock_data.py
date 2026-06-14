from app.schemas.mock import (
    EscalationCreate,
    MockEscalation,
    MockLogistics,
    MockOrder,
    MockTicketHistoryItem,
    MockUser,
)


ORDERS: dict[str, MockOrder] = {
    "OD2026001": MockOrder(
        order_id="OD2026001",
        user_id="U1001",
        status="shipped",
        amount=399,
        items=[
            {
                "sku": "SKU-HEADPHONE-001",
                "name": "Wireless Headphones",
                "quantity": 1,
            }
        ],
        created_at="2026-06-10T09:00:00",
        shipped_at="2026-06-12T14:00:00",
    ),
    "OD2026002": MockOrder(
        order_id="OD2026002",
        user_id="U1002",
        status="paid",
        amount=199,
        items=[
            {
                "sku": "SKU-KEYBOARD-001",
                "name": "Mechanical Keyboard",
                "quantity": 1,
            }
        ],
        created_at="2026-06-13T11:20:00",
    ),
    "OD2026003": MockOrder(
        order_id="OD2026003",
        user_id="U1003",
        status="paid",
        amount=2999,
        items=[
            {
                "sku": "SKU-MONITOR-001",
                "name": "4K Monitor",
                "quantity": 1,
            }
        ],
        created_at="2026-06-13T16:45:00",
    ),
    "OD2026004": MockOrder(
        order_id="OD2026004",
        user_id="U1004",
        status="shipped",
        amount=88,
        items=[
            {
                "sku": "SKU-CABLE-001",
                "name": "USB-C Cable",
                "quantity": 2,
            }
        ],
        created_at="2026-06-09T10:15:00",
        shipped_at="2026-06-10T13:00:00",
    ),
    "OD2026005": MockOrder(
        order_id="OD2026005",
        user_id="U1005",
        status="delivered",
        amount=1299,
        items=[
            {
                "sku": "SKU-CHAIR-001",
                "name": "Ergonomic Chair",
                "quantity": 1,
            }
        ],
        created_at="2026-06-05T08:30:00",
        shipped_at="2026-06-06T10:30:00",
    ),
}


LOGISTICS: dict[str, MockLogistics] = {
    "OD2026001": MockLogistics(
        order_id="OD2026001",
        carrier="Mock Express",
        tracking_no="EXP2026001",
        status="in_transit",
        last_update_at="2026-06-13T15:30:00",
        stale_days=1,
        events=[
            {
                "time": "2026-06-13T15:30:00",
                "description": "Package is in transit.",
            }
        ],
    ),
    "OD2026004": MockLogistics(
        order_id="OD2026004",
        carrier="Mock Express",
        tracking_no="EXP2026004",
        status="no_update",
        last_update_at="2026-06-10T18:10:00",
        stale_days=3,
        events=[
            {
                "time": "2026-06-10T18:10:00",
                "description": "Package departed from sorting center.",
            }
        ],
    ),
    "OD2026005": MockLogistics(
        order_id="OD2026005",
        carrier="Mock Express",
        tracking_no="EXP2026005",
        status="delivered",
        last_update_at="2026-06-08T12:05:00",
        stale_days=0,
        events=[
            {
                "time": "2026-06-08T12:05:00",
                "description": "Package delivered.",
            }
        ],
    ),
}


USERS: dict[str, MockUser] = {
    "U1001": MockUser(
        user_id="U1001",
        name="Alice Chen",
        level="normal",
        is_vip=False,
        complaint_count_30d=0,
        ticket_count_30d=2,
    ),
    "U1002": MockUser(
        user_id="U1002",
        name="Bob Li",
        level="normal",
        is_vip=False,
        complaint_count_30d=0,
        ticket_count_30d=1,
    ),
    "U1003": MockUser(
        user_id="U1003",
        name="Carol Wang",
        level="vip",
        is_vip=True,
        complaint_count_30d=1,
        ticket_count_30d=5,
    ),
    "U1004": MockUser(
        user_id="U1004",
        name="David Zhang",
        level="normal",
        is_vip=False,
        complaint_count_30d=0,
        ticket_count_30d=3,
    ),
    "U1005": MockUser(
        user_id="U1005",
        name="Eva Liu",
        level="enterprise",
        is_vip=True,
        complaint_count_30d=0,
        ticket_count_30d=4,
    ),
}


TICKET_HISTORY: dict[str, list[MockTicketHistoryItem]] = {
    "U1001": [
        MockTicketHistoryItem(
            ticket_id="T-HIS-1001",
            user_id="U1001",
            order_id="OD2025990",
            intent="logistics_issue",
            status="resolved",
            summary="Customer asked about delivery delay; support explained carrier update.",
            created_at="2026-05-30T15:00:00",
        )
    ],
    "U1003": [
        MockTicketHistoryItem(
            ticket_id="T-HIS-1003",
            user_id="U1003",
            order_id="OD2025988",
            intent="refund_request",
            status="pending_human_review",
            summary="High-value refund request required manual review.",
            created_at="2026-05-28T09:45:00",
        )
    ],
}


ESCALATIONS: list[MockEscalation] = []


def create_escalation(payload: EscalationCreate) -> MockEscalation:
    escalation = MockEscalation(
        escalation_id=f"E{len(ESCALATIONS) + 1:06d}",
        ticket_id=payload.ticket_id,
        reason=payload.reason,
        risk_level=payload.risk_level,
    )
    ESCALATIONS.append(escalation)
    return escalation

