from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import (
    VehicleNumberRequest,
    AllocateResponse,
    ReleaseResponse,
    AllocationListResponse,
)
from app import services

router = APIRouter(tags=["Allocations"])


@router.post(
    "/allocate",
    response_model=AllocateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Give a vehicle the best free slot",
    description="Allocates the lowest available slot according to vehicle preference rules.",
    responses={
        201: {"description": "Allocation successful"},
        400: {"description": "No compatible slot available"},
        404: {"description": "Vehicle not found"},
        409: {"description": "Vehicle already parked"},
        422: {"description": "Validation error"},
    },
)
def allocate_slot_endpoint(
    req: VehicleNumberRequest,
    db: Session = Depends(get_db),
):
    return services.allocate_vehicle(db, req.vehicle_number)


@router.post(
    "/release",
    response_model=ReleaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Free the slot a vehicle is holding",
    description="Releases the vehicle from its active parking slot and computes duration.",
    responses={
        200: {"description": "Vehicle successfully released"},
        404: {"description": "Vehicle not found"},
        409: {"description": "Vehicle not currently parked"},
        422: {"description": "Validation error"},
    },
)
def release_slot_endpoint(
    req: VehicleNumberRequest,
    db: Session = Depends(get_db),
):
    return services.release_vehicle(db, req.vehicle_number)


@router.get(
    "/allocations",
    response_model=List[AllocationListResponse],
    status_code=status.HTTP_200_OK,
    summary="Currently parked vehicles / allocation history",
    description="Lists allocations, defaults to active parking allocations.",
    responses={
        200: {"description": "List of allocations"},
        422: {"description": "Invalid status filter"},
    },
)
def list_allocations_endpoint(
    status: Optional[str] = Query("ACTIVE", description="Filter by status: ACTIVE, RELEASED, ALL"),
    db: Session = Depends(get_db),
):
    return services.list_allocations(db, status_filter=status)
