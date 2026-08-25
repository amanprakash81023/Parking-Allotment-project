import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from app.database import Base


class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True, index=True)
    slot_number = Column(String(10), unique=True, nullable=False, index=True)
    floor = Column(String(1), nullable=False)
    slot_num = Column(Integer, nullable=False)
    slot_type = Column(String(10), nullable=False)
    status = Column(String(10), nullable=False, default="AVAILABLE")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    allocations = relationship("Allocation", back_populates="slot")

    __table_args__ = (
        Index("idx_slots_alloc_order", "slot_type", "status", "floor", "slot_num"),
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_number = Column(String(15), unique=True, nullable=False, index=True)
    owner_name = Column(String(100), nullable=False)
    vehicle_type = Column(String(10), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    allocations = relationship("Allocation", back_populates="vehicle")


class Allocation(Base):
    __tablename__ = "allocations"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=False)
    entry_time = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    exit_time = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    status = Column(String(10), nullable=False, default="ACTIVE")

    vehicle = relationship("Vehicle", back_populates="allocations")
    slot = relationship("Slot", back_populates="allocations")

    __table_args__ = (
        Index("idx_allocations_entry_time", entry_time.desc()),
        # PostgreSQL partial unique indexes will be created via schema.sql / sqlite handles app checks & DDL
        Index(
            "uq_active_vehicle_allocation",
            "vehicle_id",
            unique=True,
            postgresql_where=(status == "ACTIVE"),
            sqlite_where=(status == "ACTIVE"),
        ),
        Index(
            "uq_active_slot_allocation",
            "slot_id",
            unique=True,
            postgresql_where=(status == "ACTIVE"),
            sqlite_where=(status == "ACTIVE"),
        ),
    )
