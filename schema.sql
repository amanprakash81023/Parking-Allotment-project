-- Parking Allotment Database Schema (PostgreSQL)

DROP TABLE IF EXISTS allocations CASCADE;
DROP TABLE IF EXISTS vehicles CASCADE;
DROP TABLE IF EXISTS slots CASCADE;

-- 1. Slots Table
-- Stores physical parking spaces across multiple floors.
-- Separate floor (A-Z) and slot_num (1-999) columns guarantee proper numerical ordering (§4.1).
CREATE TABLE slots (
    id SERIAL PRIMARY KEY,
    slot_number VARCHAR(10) NOT NULL UNIQUE,
    floor VARCHAR(1) NOT NULL,
    slot_num INTEGER NOT NULL,
    slot_type VARCHAR(10) NOT NULL CHECK (slot_type IN ('BIKE', 'CAR', 'EV')),
    status VARCHAR(10) NOT NULL DEFAULT 'AVAILABLE' CHECK (status IN ('AVAILABLE', 'OCCUPIED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast allocation lookups by type & availability in strict lowest floor/number order (§4.1)
CREATE INDEX idx_slots_alloc_order ON slots (slot_type, status, floor, slot_num);

-- 2. Vehicles Table
-- Stores registered vehicles with uppercase normalized plate numbers (§4.6).
CREATE TABLE vehicles (
    id SERIAL PRIMARY KEY,
    vehicle_number VARCHAR(15) NOT NULL UNIQUE,
    owner_name VARCHAR(100) NOT NULL,
    vehicle_type VARCHAR(10) NOT NULL CHECK (vehicle_type IN ('BIKE', 'CAR', 'EV')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index on vehicle number for quick lookups
CREATE INDEX idx_vehicles_number ON vehicles (vehicle_number);

-- 3. Allocations Table
-- Stores parking allocation records from entry to release (§4.3, §4.5).
CREATE TABLE allocations (
    id SERIAL PRIMARY KEY,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE RESTRICT,
    slot_id INTEGER NOT NULL REFERENCES slots(id) ON DELETE RESTRICT,
    entry_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exit_time TIMESTAMPTZ NULL,
    duration_minutes INTEGER NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'RELEASED'))
);

-- Database-level guarantees (§4.4 Concurrency):
-- Ensures one vehicle can only have AT MOST ONE active allocation at any given time.
CREATE UNIQUE INDEX uq_active_vehicle_allocation ON allocations (vehicle_id) WHERE status = 'ACTIVE';

-- Ensures one slot can only have AT MOST ONE active allocation at any given time.
CREATE UNIQUE INDEX uq_active_slot_allocation ON allocations (slot_id) WHERE status = 'ACTIVE';

-- Index for listing allocations ordered by entry_time descending (§5.7)
CREATE INDEX idx_allocations_entry_time ON allocations (entry_time DESC);
