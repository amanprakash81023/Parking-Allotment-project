from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import VehicleCreate, VehicleResponse, VehicleListResponse
from app import services

router = APIRouter(tags=["Vehicles"])


@router.post(
    "/vehicles",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a vehicle",
    description="Registers a new vehicle with owner information and vehicle type.",
    responses={
        201: {"description": "Vehicle registered successfully"},
        409: {"description": "Vehicle number already registered"},
        422: {"description": "Validation error"},
    },
)
def register_vehicle_endpoint(vehicle_in: VehicleCreate, db: Session = Depends(get_db)):
    return services.create_vehicle(db, vehicle_in)


@router.get(
    "/vehicles",
    response_model=List[VehicleListResponse],
    status_code=status.HTTP_200_OK,
    summary="List registered vehicles",
    description="Lists all vehicles along with current parking status and occupied slot.",
    responses={
        200: {"description": "List of registered vehicles"},
    },
)
def list_vehicles_endpoint(db: Session = Depends(get_db)):
    return services.list_vehicles(db)
