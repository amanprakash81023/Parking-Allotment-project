import math
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, desc
from app.models import Slot, Vehicle, Allocation
from app.schemas import (
    SlotCreate,
    VehicleCreate,
    SlotStatusEnum,
    SlotTypeEnum,
    AllocationFilterStatusEnum,
)
from app.exceptions import AppException


def format_iso_utc(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------- Slots Service ----------------


def create_slot(db: Session, slot_in: SlotCreate) -> Slot:
    # Slot format is already validated by Pydantic: <FLOOR>-<NUMBER>
    parts = slot_in.slot_number.split("-")
    floor = parts[0]
    slot_num = int(parts[1])

    # Check for existing slot
    existing = db.query(Slot).filter(Slot.slot_number == slot_in.slot_number).first()
    if existing:
        raise AppException(
            status_code=409,
            code="SLOT_ALREADY_EXISTS",
            message=f"Slot '{slot_in.slot_number}' already exists.",
        )

    slot = Slot(
        slot_number=slot_in.slot_number,
        floor=floor,
        slot_num=slot_num,
        slot_type=slot_in.slot_type.value,
        status=SlotStatusEnum.AVAILABLE.value,
    )
    db.add(slot)
    try:
        db.commit()
        db.refresh(slot)
    except IntegrityError:
        db.rollback()
        raise AppException(
            status_code=409,
            code="SLOT_ALREADY_EXISTS",
            message=f"Slot '{slot_in.slot_number}' already exists.",
        )
    return slot


def list_slots(
    db: Session,
    status: Optional[str] = None,
    slot_type: Optional[str] = None,
) -> List[Slot]:
    query = db.query(Slot)

    if status:
        if status not in [e.value for e in SlotStatusEnum]:
            raise AppException(
                status_code=422,
                code="VALIDATION_ERROR",
                message=f"Invalid slot status filter: '{status}'.",
            )
        query = query.filter(Slot.status == status)

    if slot_type:
        if slot_type not in [e.value for e in SlotTypeEnum]:
            raise AppException(
                status_code=422,
                code="VALIDATION_ERROR",
                message=f"Invalid slot type filter: '{slot_type}'.",
            )
        query = query.filter(Slot.slot_type == slot_type)

    # §4.1 Ordering: Lowest floor first, then lowest number
    query = query.order_by(Slot.floor.asc(), Slot.slot_num.asc())
    return query.all()


# ---------------- Vehicles Service ----------------


def create_vehicle(db: Session, vehicle_in: VehicleCreate) -> Vehicle:
    existing = (
        db.query(Vehicle)
        .filter(Vehicle.vehicle_number == vehicle_in.vehicle_number)
        .first()
    )
    if existing:
        raise AppException(
            status_code=409,
            code="VEHICLE_ALREADY_EXISTS",
            message=f"Vehicle with number '{vehicle_in.vehicle_number}' is already registered.",
        )

    vehicle = Vehicle(
        vehicle_number=vehicle_in.vehicle_number,
        owner_name=vehicle_in.owner_name,
        vehicle_type=vehicle_in.vehicle_type.value,
    )
    db.add(vehicle)
    try:
        db.commit()
        db.refresh(vehicle)
    except IntegrityError:
        db.rollback()
        raise AppException(
            status_code=409,
            code="VEHICLE_ALREADY_EXISTS",
            message=f"Vehicle with number '{vehicle_in.vehicle_number}' is already registered.",
        )
    return vehicle


def list_vehicles(db: Session) -> List[dict]:
    # Single efficient query without N+1 problem: LEFT JOIN to active allocations and slots
    rows = (
        db.query(
            Vehicle.id,
            Vehicle.vehicle_number,
            Vehicle.owner_name,
            Vehicle.vehicle_type,
            Allocation.id.isnot(None).label("is_parked"),
            Slot.slot_number.label("current_slot"),
        )
        .outerjoin(
            Allocation,
            (Allocation.vehicle_id == Vehicle.id) & (Allocation.status == "ACTIVE"),
        )
        .outerjoin(Slot, Slot.id == Allocation.slot_id)
        .order_by(Vehicle.id.asc())
        .all()
    )

    return [
        {
            "id": r.id,
            "vehicle_number": r.vehicle_number,
            "owner_name": r.owner_name,
            "vehicle_type": r.vehicle_type,
            "is_parked": bool(r.is_parked),
            "current_slot": r.current_slot,
        }
        for r in rows
    ]


# ---------------- Allocations Service ----------------


def allocate_vehicle(db: Session, vehicle_number: str) -> dict:
    # 1. Look up vehicle by number
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.vehicle_number == vehicle_number)
        .first()
    )
    if not vehicle:
        raise AppException(
            status_code=404,
            code="VEHICLE_NOT_FOUND",
            message=f"Vehicle '{vehicle_number}' not found.",
        )

    # 2. Check if vehicle already holds an ACTIVE allocation
    active_alloc = (
        db.query(Allocation)
        .join(Slot, Slot.id == Allocation.slot_id)
        .filter(
            Allocation.vehicle_id == vehicle.id,
            Allocation.status == "ACTIVE",
        )
        .first()
    )
    if active_alloc:
        slot_number = active_alloc.slot.slot_number if active_alloc.slot else "unknown"
        raise AppException(
            status_code=409,
            code="VEHICLE_ALREADY_PARKED",
            message=f"Vehicle {vehicle.vehicle_number} is already parked in slot {slot_number}.",
        )

    # 3. Preference list (§4.2)
    if vehicle.vehicle_type == "BIKE":
        preferences = ["BIKE"]
    elif vehicle.vehicle_type == "CAR":
        preferences = ["CAR"]
    elif vehicle.vehicle_type == "EV":
        preferences = ["EV", "CAR"]
    else:
        preferences = [vehicle.vehicle_type]

    # 4. Find available slot with row lock
    chosen_slot = None
    for pref_type in preferences:
        query = (
            db.query(Slot)
            .filter(Slot.slot_type == pref_type, Slot.status == "AVAILABLE")
            .order_by(Slot.floor.asc(), Slot.slot_num.asc())
        )
        # Apply row-level lock if supported by database engine (e.g. Postgres)
        if db.bind.dialect.name != "sqlite":
            query = query.with_for_update()

        slot_candidate = query.first()
        if slot_candidate:
            chosen_slot = slot_candidate
            break

    if not chosen_slot:
        raise AppException(
            status_code=400,
            code="NO_SLOT_AVAILABLE",
            message="No compatible parking slot is currently available.",
        )

    # 5. Mark slot OCCUPIED
    chosen_slot.status = "OCCUPIED"

    # 6. Create allocation record
    now_utc = datetime.now(timezone.utc)
    allocation = Allocation(
        vehicle_id=vehicle.id,
        slot_id=chosen_slot.id,
        entry_time=now_utc,
        status="ACTIVE",
    )
    db.add(allocation)

    try:
        db.commit()
        db.refresh(allocation)
    except IntegrityError:
        db.rollback()
        # DB-level partial unique constraint triggered under high concurrency race
        raise AppException(
            status_code=409,
            code="VEHICLE_ALREADY_PARKED",
            message=f"Vehicle {vehicle.vehicle_number} already has an active allocation.",
        )

    return {
        "allocation_id": allocation.id,
        "vehicle_number": vehicle.vehicle_number,
        "slot_number": chosen_slot.slot_number,
        "slot_type": chosen_slot.slot_type,
        "entry_time": format_iso_utc(allocation.entry_time),
        "status": allocation.status,
    }


def release_vehicle(db: Session, vehicle_number: str) -> dict:
    # 1. Look up vehicle
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.vehicle_number == vehicle_number)
        .first()
    )
    if not vehicle:
        raise AppException(
            status_code=404,
            code="VEHICLE_NOT_FOUND",
            message=f"Vehicle '{vehicle_number}' not found.",
        )

    # 2. Find active allocation with lock
    query = (
        db.query(Allocation)
        .join(Slot, Slot.id == Allocation.slot_id)
        .filter(
            Allocation.vehicle_id == vehicle.id,
            Allocation.status == "ACTIVE",
        )
    )
    if db.bind.dialect.name != "sqlite":
        query = query.with_for_update()

    allocation = query.first()
    if not allocation:
        raise AppException(
            status_code=409,
            code="VEHICLE_NOT_PARKED",
            message=f"Vehicle '{vehicle_number}' is not currently parked.",
        )

    slot = allocation.slot
    now_utc = datetime.now(timezone.utc)
    allocation.exit_time = now_utc
    allocation.status = "RELEASED"

    # Calculate duration_minutes (rounded up)
    entry_time = allocation.entry_time
    if entry_time.tzinfo is None:
        entry_time = entry_time.replace(tzinfo=timezone.utc)
    delta_seconds = (now_utc - entry_time).total_seconds()
    duration_minutes = max(1, math.ceil(delta_seconds / 60))
    allocation.duration_minutes = duration_minutes

    # Free the slot
    if slot:
        slot.status = "AVAILABLE"

    db.commit()
    db.refresh(allocation)

    return {
        "allocation_id": allocation.id,
        "vehicle_number": vehicle.vehicle_number,
        "slot_number": slot.slot_number if slot else "",
        "entry_time": format_iso_utc(allocation.entry_time),
        "exit_time": format_iso_utc(allocation.exit_time),
        "duration_minutes": allocation.duration_minutes,
        "status": allocation.status,
    }


def list_allocations(
    db: Session,
    status_filter: Optional[str] = "ACTIVE",
) -> List[dict]:
    query = (
        db.query(
            Allocation.id.label("allocation_id"),
            Vehicle.vehicle_number,
            Vehicle.owner_name,
            Slot.slot_number,
            Allocation.entry_time,
            Allocation.exit_time,
            Allocation.status,
        )
        .join(Vehicle, Vehicle.id == Allocation.vehicle_id)
        .join(Slot, Slot.id == Allocation.slot_id)
    )

    if status_filter:
        valid_filters = [e.value for e in AllocationFilterStatusEnum]
        if status_filter not in valid_filters:
            raise AppException(
                status_code=422,
                code="VALIDATION_ERROR",
                message=f"Invalid status filter: '{status_filter}'. Expected one of {valid_filters}.",
            )
        if status_filter in ["ACTIVE", "RELEASED"]:
            query = query.filter(Allocation.status == status_filter)
        # If ALL, do not filter by status

    query = query.order_by(Allocation.entry_time.desc())
    rows = query.all()

    return [
        {
            "allocation_id": r.allocation_id,
            "vehicle_number": r.vehicle_number,
            "owner_name": r.owner_name,
            "slot_number": r.slot_number,
            "entry_time": format_iso_utc(r.entry_time),
            "exit_time": format_iso_utc(r.exit_time),
            "status": r.status,
        }
        for r in rows
    ]
