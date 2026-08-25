from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import SlotCreate, SlotResponse
from app import services

router = APIRouter(tags=["Slots"])


@router.post(
    "/slots",
    response_model=SlotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create one parking slot",
    description="Registers a new parking slot with floor, number and vehicle capability.",
    responses={
        201: {"description": "Slot created successfully"},
        409: {"description": "Slot number already exists"},
        422: {"description": "Validation error on slot_number or slot_type"},
    },
)
def create_slot_endpoint(slot_in: SlotCreate, db: Session = Depends(get_db)):
    return services.create_slot(db, slot_in)


@router.get(
    "/slots",
    response_model=List[SlotResponse],
    status_code=status.HTTP_200_OK,
    summary="List slots, filterable",
    description="Lists all facility parking spaces ordered by floor ASC and slot number ASC.",
    responses={
        200: {"description": "List of slots"},
        422: {"description": "Unknown filter value"},
    },
)
def list_slots_endpoint(
    status: Optional[str] = Query(None, description="Filter by status: AVAILABLE, OCCUPIED"),
    slot_type: Optional[str] = Query(None, description="Filter by slot type: BIKE, CAR, EV"),
    db: Session = Depends(get_db),
):
    return services.list_slots(db, status=status, slot_type=slot_type)
