from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db import (
    get_family_by_phone,
    verify_password,
    get_my_contributions,
    get_my_received_contributions,
    get_my_partner_history,
    get_my_partner_transactions,
    get_my_hosted_events,
    create_event_by_host,
    update_event_by_host,
)


app = FastAPI(title="Moi Sei API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    phone_number: str = Field(min_length=1)
    password: str = Field(min_length=1)


class FamilySummary(BaseModel):
    id: int
    husband_name: str
    wife_name: str | None = None
    phone_number: str
    place: str | None = None


class LoginResponse(BaseModel):
    success: bool
    message: str
    family: FamilySummary


class TransactionSummary(BaseModel):
    """Summary of money given/received"""
    family_id: int
    total_given: float
    total_received: float
    net_balance: float  # positive = you gave more, negative = you received more


class Transaction(BaseModel):
    """Single transaction record"""
    event_name: str
    transaction_date: str
    counterparty_name: str  # who you gave to or received from
    amount: float
    type: str  # "given" or "received"


class TransactionListResponse(BaseModel):
    """List of all transactions"""
    family_id: int
    family_name: str
    total_transactions: int
    summary: TransactionSummary
    transactions: list[Transaction]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "moi-sei-api"}


@app.post("/login", response_model=LoginResponse)
def login(request: LoginRequest) -> LoginResponse:
    family: dict[str, Any] | None = get_family_by_phone(request.phone_number.strip())
    if family is None or not verify_password(
        request.password, family.get("password_hash") or ""
    ):
        raise HTTPException(status_code=401, detail="Incorrect phone number or password.")

    return LoginResponse(
        success=True,
        message="Login successful.",
        family=FamilySummary(
            id=family["id"],
            husband_name=family["husband_name"],
            wife_name=family.get("wife_name"),
            phone_number=family["phone_number"],
            place=family.get("place"),
        ),
    )


@app.get("/family/{family_id}/summary", response_model=TransactionSummary)
def get_transaction_summary(family_id: int) -> TransactionSummary:
    """Get total given, total received, and net balance for a family"""
    try:
        contributions = get_my_contributions(family_id)
        received = get_my_received_contributions(family_id)
        
        total_given = sum(float(row.get("amount", 0)) for row in contributions) if contributions else 0.0
        total_received = sum(float(row.get("amount", 0)) for row in received) if received else 0.0
        net_balance = total_given - total_received
        
        return TransactionSummary(
            family_id=family_id,
            total_given=total_given,
            total_received=total_received,
            net_balance=net_balance,
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not fetch summary: {str(error)}")


@app.get("/family/{family_id}/transactions", response_model=TransactionListResponse)
def get_all_transactions(family_id: int) -> TransactionListResponse:
    """Get all transactions (given and received) for a family"""
    try:
        family = get_family_by_phone("") if family_id else None
        family_name = "Family"
        
        contributions = get_my_contributions(family_id)
        received = get_my_received_contributions(family_id)
        
        transactions: list[Transaction] = []
        
        # Add contributions (money given)
        if contributions:
            for row in contributions:
                transactions.append(
                    Transaction(
                        event_name=row.get("event_name", ""),
                        transaction_date=str(row.get("contribution_date", "")),
                        counterparty_name=row.get("receiver_name", ""),
                        amount=float(row.get("amount", 0)),
                        type="given",
                    )
                )
        
        # Add received contributions (money received)
        if received:
            for row in received:
                transactions.append(
                    Transaction(
                        event_name=row.get("event_name", ""),
                        transaction_date=str(row.get("contribution_date", "")),
                        counterparty_name=row.get("contributor_name", ""),
                        amount=float(row.get("amount", 0)),
                        type="received",
                    )
                )
        
        # Sort by date (newest first)
        transactions.sort(key=lambda x: x.transaction_date, reverse=True)
        
        total_given = sum(t.amount for t in transactions if t.type == "given")
        total_received = sum(t.amount for t in transactions if t.type == "received")
        net_balance = total_given - total_received
        
        return TransactionListResponse(
            family_id=family_id,
            family_name=family_name,
            total_transactions=len(transactions),
            summary=TransactionSummary(
                family_id=family_id,
                total_given=total_given,
                total_received=total_received,
                net_balance=net_balance,
            ),
            transactions=transactions,
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not fetch transactions: {str(error)}")


@app.get("/family/{family_id}/upcoming-events")
def get_upcoming_events(family_id: int) -> dict[str, list[dict]]:
    """Get upcoming partner events"""
    try:
        from db import get_upcoming_partner_events
        
        events = get_upcoming_partner_events(family_id)
        
        events_list = []
        if events:
            for row in events:
                events_list.append({
                    "event_id": row.get("event_id"),
                    "event_name": row.get("event_name", ""),
                    "event_date": str(row.get("event_date", "")),
                    "other_husband_name": row.get("other_husband_name", ""),
                    "other_phone_number": row.get("other_phone_number", ""),
                    "place": row.get("place", ""),
                })
        
        return {"events": events_list}
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not fetch upcoming events: {str(error)}")


@app.get("/family/{family_id}/partner-history")
def get_partner_history(family_id: int) -> dict[str, list[dict]]:
    """Get Give & Take Summary (All Events) - summary with each partner"""
    try:
        partner_rows = get_my_partner_history(family_id)
        
        partners_list = []
        if partner_rows:
            for row in partner_rows:
                partners_list.append({
                    "other_user_id": row.get("other_user_id"),
                    "other_husband_name": row.get("other_husband_name", ""),
                    "other_phone_number": row.get("other_phone_number", ""),
                    "total_given": float(row.get("total_given", 0)),
                    "total_received": float(row.get("total_received", 0)),
                    "net_difference": float(row.get("net_difference", 0)),
                })
        
        return {"partners": partners_list}
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not fetch partner history: {str(error)}")


@app.get("/family/{family_id}/partner-transactions/{other_family_id}")
def get_partner_transactions(family_id: int, other_family_id: int) -> dict[str, list[dict]]:
    """Chronological transaction timeline with one specific family, with running balance."""
    try:
        rows = get_my_partner_transactions(family_id, other_family_id)

        timeline = []
        if rows:
            for row in rows:
                timeline.append({
                    "transaction_id": row.get("transaction_id"),
                    "transaction_date": str(row.get("transaction_date", "")),
                    "event_name": row.get("event_name", ""),
                    "direction": row.get("direction", ""),
                    "amount": float(row.get("amount", 0)),
                    "running_net_difference": float(row.get("running_net_difference", 0)),
                })

        return {"transactions": timeline}
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not fetch partner transactions: {str(error)}")


@app.get("/family/{family_id}/contributions")
def get_contributions(family_id: int) -> dict[str, list[dict]]:
    """Get all detailed contributions (what I gave to each event)"""
    try:
        contributions = get_my_contributions(family_id)
        
        contributions_list = []
        if contributions:
            for row in contributions:
                contributions_list.append({
                    "event_id": row.get("event_id"),
                    "event_name": row.get("event_name", ""),
                    "receiver_name": row.get("receiver_name", ""),
                    "receiver_phone": row.get("receiver_phone", ""),
                    "amount": float(row.get("amount", 0)),
                    "contribution_date": str(row.get("contribution_date", "")),
                })
        
        return {"contributions": contributions_list}
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not fetch contributions: {str(error)}")


@app.get("/family/{family_id}/receipts")
def get_receipts(family_id: int) -> dict[str, list[dict]]:
    """Get all detailed receipts (what I received from each event)"""
    try:
        receipts = get_my_received_contributions(family_id)
        
        receipts_list = []
        if receipts:
            for row in receipts:
                receipts_list.append({
                    "event_id": row.get("event_id"),
                    "event_name": row.get("event_name", ""),
                    "contributor_name": row.get("contributor_name", ""),
                    "contributor_phone": row.get("contributor_phone", ""),
                    "amount": float(row.get("amount", 0)),
                    "contribution_date": str(row.get("contribution_date", "")),
                })
        
        return {"receipts": receipts_list}
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not fetch receipts: {str(error)}")


@app.get("/family/{family_id}/events")
def get_family_events(family_id: int) -> dict[str, list[dict]]:
    """Get all events hosted by this family"""
    try:
        events = get_my_hosted_events(family_id)
        
        events_list = []
        if events:
            for row in events:
                events_list.append({
                    "event_id": row.get("event_id"),
                    "event_name": row.get("event_name", ""),
                    "event_date": str(row.get("event_date", "")),
                    "event_place": row.get("event_place", ""),
                    "event_location": row.get("event_location", ""),
                    "is_active": row.get("is_active", True),
                })
        
        return {"events": events_list}
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not fetch events: {str(error)}")


class CreateEventRequest(BaseModel):
    event_name: str = Field(min_length=1)
    event_date: str = Field(min_length=1)
    event_place: str = Field(min_length=1)
    event_location: str | None = None


@app.post("/family/{family_id}/event")
def create_event(family_id: int, request: CreateEventRequest) -> dict[str, Any]:
    """Create a new event hosted by this family"""
    try:
        success, result = create_event_by_host(
            request.event_name,
            request.event_date,
            request.event_place,
            request.event_location,
            family_id
        )
        
        if success:
            return {
                "success": True,
                "message": "Event created successfully",
                "event_id": result
            }
        else:
            raise HTTPException(status_code=400, detail=f"Failed to create event: {result}")
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not create event: {str(error)}")


class UpdateEventRequest(BaseModel):
    event_name: str = Field(min_length=1)
    event_date: str = Field(min_length=1)
    event_place: str = Field(min_length=1)
    event_location: str | None = None


@app.put("/family/{family_id}/event/{event_id}")
def update_event(family_id: int, event_id: int, request: UpdateEventRequest) -> dict[str, Any]:
    """Update an event hosted by this family"""
    try:
        success, message = update_event_by_host(
            event_id,
            request.event_name,
            request.event_date,
            request.event_place,
            request.event_location,
            family_id
        )
        
        if success:
            return {
                "success": True,
                "message": message
            }
        else:
            raise HTTPException(status_code=400, detail=message)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not update event: {str(error)}")
