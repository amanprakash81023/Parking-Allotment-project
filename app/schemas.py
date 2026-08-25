import re
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


class VehicleTypeEnum(str, Enum):
    BIKE = "BIKE"
    CAR = "CAR"
    EV = "EV"


class SlotTypeEnum(str, Enum):
    BIKE = "BIKE"
    CAR = "CAR"
    EV = "EV"


class SlotStatusEnum(str, Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"


class AllocationStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"


class AllocationFilterStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    ALL = "ALL"


# ---------------- Slots ----------------


class SlotCreate(BaseModel):
    slot_number: str = Field(..., description="Slot identifier in <FLOOR>-<NUMBER> format (e.g. A-1)")
    slot_type: SlotTypeEnum = Field(..., description="Type of slot (BIKE, CAR, EV)")

    @field_validator("slot_number")
    @classmethod
    def validate_slot_number(cls, v: str) -> str:
        v = v.strip()
        pattern = r"^[A-Z]-(?!0)[0-9]{1,3}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid slot number format. Expected format: <FLOOR>-<NUMBER> (e.g., A-1, B-999).")
        return v


class SlotResponse(BaseModel):
    id: int
    slot_number: str
    slot_type: str
    status: str

    model_config = ConfigDict(from_attributes=True)


# ---------------- Vehicles ----------------


class VehicleCreate(BaseModel):
    vehicle_number: str = Field(..., description="4-15 alphanumeric chars (no spaces or hyphens)")
    owner_name: str = Field(..., description="Owner full name, 2-100 characters")
    vehicle_type: VehicleTypeEnum = Field(..., description="Vehicle type (BIKE, CAR, EV)")

    @field_validator("vehicle_number")
    @classmethod
    def validate_vehicle_number(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.match(r"^[A-Z0-9]{4,15}$", v):
            raise ValueError("Vehicle number must be 4-15 alphanumeric characters with no spaces or hyphens.")
        return v

    @field_validator("owner_name")
    @classmethod
    def validate_owner_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 100:
            raise ValueError("Owner name must be between 2 and 100 non-empty characters.")
        return v


class VehicleResponse(BaseModel):
    id: int
    vehicle_number: str
    owner_name: str
    vehicle_type: str

    model_config = ConfigDict(from_attributes=True)


class VehicleListResponse(BaseModel):
    id: int
    vehicle_number: str
    owner_name: str
    vehicle_type: str
    is_parked: bool
    current_slot: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------- Allocations ----------------


class VehicleNumberRequest(BaseModel):
    vehicle_number: str = Field(..., description="Vehicle number to allocate or release")

    @field_validator("vehicle_number")
    @classmethod
    def validate_vehicle_number(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.match(r"^[A-Z0-9]{4,15}$", v):
            raise ValueError("Invalid vehicle number.")
        return v


class AllocateResponse(BaseModel):
    allocation_id: int
    vehicle_number: str
    slot_number: str
    slot_type: str
    entry_time: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class ReleaseResponse(BaseModel):
    allocation_id: int
    vehicle_number: str
    slot_number: str
    entry_time: str
    exit_time: str
    duration_minutes: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class AllocationListResponse(BaseModel):
    allocation_id: int
    vehicle_number: str
    owner_name: str
    slot_number: str
    entry_time: str
    exit_time: Optional[str] = None
    status: str

    model_config = ConfigDict(from_attributes=True)
