# Parking Allotment System — Implementation Document

This document provides a comprehensive breakdown of the architectural, data modeling, concurrency, and algorithmic decisions made in implementing the Parking Allotment Backend API.

---

## 1. How to Run It

### Option A: Using Docker Compose (Recommended)
```bash
# 1. Start database and API containers
docker compose up -d --build

# 2. Open interactive Swagger / OpenAPI docs
# Navigate to: http://localhost:8000/docs
```

### Option B: Local Setup (Python Virtualenv + PostgreSQL or SQLite)
```bash
# 1. Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Update DATABASE_URL in .env if using local PostgreSQL, or default to SQLite for quick testing:
# DATABASE_URL=sqlite:///./parking.db

# 4. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 5. Open docs
# http://localhost:8000/docs
```

### Running Tests
```bash
pytest -v
```

---

## 2. Project Layout

```text
├── app/
│   ├── __init__.py           # Application package marker
│   ├── config.py             # Pydantic Settings reading .env (DATABASE_URL, ports)
│   ├── database.py           # SQLAlchemy engine, session maker, get_db dependency
│   ├── exceptions.py         # Global error handlers enforcing §5.8 uniform JSON envelope
│   ├── main.py               # FastAPI entry point, lifecycle events, and route mounting
│   ├── models.py             # SQLAlchemy ORM models (Slot, Vehicle, Allocation) + indexes
│   ├── schemas.py            # Pydantic validation schemas with regex and domain rules
│   ├── services.py           # Core business logic: allocation algorithm, release, CRUD
│   └── routers/
│       ├── __init__.py       # Router package initialization
│       ├── slots.py          # /slots endpoints (POST create, GET filterable list)
│       ├── vehicles.py       # /vehicles endpoints (POST register, GET list with status)
│       └── allocations.py   # /allocate, /release, /allocations endpoints
├── tests/
│   ├── __init__.py           # Test package initialization
│   ├── conftest.py           # Pytest fixtures: in-memory DB, StaticPool, fresh schema per test
│   └── test_api.py           # Acceptance test suite (TC01-TC14)
├── .env.example              # Template environment configuration
├── .gitignore                # Git exclusions (venv, caches, env files)
├── Dockerfile                # Multi-stage production container image
├── docker-compose.yml        # PostgreSQL 15 + FastAPI orchestrated environment
├── postman_collection.json   # Exported Postman v2.1 collection with assertions & test scripts
├── requirements.txt          # Exact pinned Python dependencies
├── schema.sql                # Raw SQL schema definition with comments, keys, & indexes
├── IMPLEMENTATION.md         # Architecture and technical design document
└── README.md                 # Project summary and quickstart guide
```

---

## 3. Request Walkthrough: `POST /allocate`

Tracing a `POST /allocate` request end-to-end:

1. **HTTP Ingestion**:
   - The HTTP request `POST /allocate` with JSON payload `{"vehicle_number": "MH12AB1234"}` hits FastAPI.
   - Endpoint handler: `app/routers/allocations.py:allocate_slot_endpoint()`.

2. **Validation**:
   - `VehicleNumberRequest` in `app/schemas.py` validates the payload:
     - Strips surrounding whitespace and transforms to uppercase (`MH12AB1234`).
     - Regex validates `^[A-Z0-9]{4,15}$`. If invalid, `validation_exception_handler` intercepts and returns `422 VALIDATION_ERROR`.

3. **Service Layer & Database Transaction**:
   - Invokes `app/services.py:allocate_vehicle(db, "MH12AB1234")`.
   - **Step 1: Vehicle Lookup**:
     ```sql
     SELECT * FROM vehicles WHERE vehicle_number = 'MH12AB1234' LIMIT 1;
     ```
     If not found, raises `AppException(404, "VEHICLE_NOT_FOUND")`.
   - **Step 2: Active Allocation Check**:
     ```sql
     SELECT a.*, s.slot_number 
     FROM allocations a 
     JOIN slots s ON s.id = a.slot_id 
     WHERE a.vehicle_id = 1 AND a.status = 'ACTIVE' LIMIT 1;
     ```
     If found, raises `AppException(409, "VEHICLE_ALREADY_PARKED")`.
   - **Step 3: Preference Ordering**:
     - Based on `vehicle.vehicle_type`, sets candidate list:
       - `BIKE` $\to$ `['BIKE']`
       - `CAR` $\to$ `['CAR']`
       - `EV` $\to$ `['EV', 'CAR']`
   - **Step 4: Slot Selection with Row Locking**:
     - Iterates through preferences in order. Executes:
       ```sql
       SELECT * FROM slots 
       WHERE slot_type = 'EV' AND status = 'AVAILABLE' 
       ORDER BY floor ASC, slot_num ASC 
       LIMIT 1 
       FOR UPDATE;
       ```
     - If not found, tries fallback slot type (e.g. `'CAR'`).
     - If none found in any type, raises `AppException(400, "NO_SLOT_AVAILABLE")`.
   - **Step 5: Slot Status Update & Allocation Insertion**:
     ```sql
     UPDATE slots SET status = 'OCCUPIED' WHERE id = :slot_id;
     INSERT INTO allocations (vehicle_id, slot_id, entry_time, status)
     VALUES (1, :slot_id, '2026-08-25T12:00:00Z', 'ACTIVE') RETURNING id;
     ```
   - **Step 6: Transaction Commit**:
     - `db.commit()` writes changes atomically.
     - If a concurrent transaction violates the database-level partial unique index `uq_active_vehicle_allocation` or `uq_active_slot_allocation`, SQLAlchemy raises `IntegrityError`. The exception handler triggers `db.rollback()` and returns clean `409 VEHICLE_ALREADY_PARKED`.

4. **Response**:
   - Returns status code `201 Created` with payload:
     ```json
     {
       "allocation_id": 1,
       "vehicle_number": "MH12AB1234",
       "slot_number": "A-1",
       "slot_type": "CAR",
       "entry_time": "2026-08-25T12:00:00Z",
       "status": "ACTIVE"
     }
     ```

---

## 4. Concurrency Solution (§4.4)

### The Chosen Approach
We use a **defense-in-depth model** combining **Row-Level Locking (`FOR UPDATE`)** with **Database Partial Unique Indexes**.

1. **Row-Level Locking during Selection**:
   ```python
   query = (
       db.query(Slot)
       .filter(Slot.slot_type == pref_type, Slot.status == "AVAILABLE")
       .order_by(Slot.floor.asc(), Slot.slot_num.asc())
   )
   if db.bind.dialect.name != "sqlite":
       query = query.with_for_update()
   slot_candidate = query.first()
   ```
2. **Database-Level Partial Unique Constraints**:
   ```sql
   CREATE UNIQUE INDEX uq_active_vehicle_allocation 
   ON allocations (vehicle_id) 
   WHERE status = 'ACTIVE';

   CREATE UNIQUE INDEX uq_active_slot_allocation 
   ON allocations (slot_id) 
   WHERE status = 'ACTIVE';
   ```

### Why Other Approaches Were Rejected:
- **Application-only `if` checks**: In concurrent workloads under `READ COMMITTED` isolation, two threads can read the same slot as available and both proceed to write, resulting in double booking.
- **`SERIALIZABLE` isolation level**: High rate of serialization failures requiring application-level retry loops and backoffs, increasing latency and deadlocks.
- **Global Table Lock / Application Mutex**: Serializes all requests across all threads and workers, destroying throughput in multi-worker ASGI deployments.

### Concurrency Guarantees:
- `FOR UPDATE` serializes conflicting slot updates at the database level.
- Partial unique indexes make it physically impossible for two active records to exist for the same slot or vehicle, even if locking is bypassed.
- Any constraint collision is intercepted and translated to a clean `409` response without 500 stack traces.

---

## 5. Slot Ordering Solution (§4.1)

### The Pitfall of Plain Text Sorting:
Lexicographical string sorting sorts character by character:
`"A-1", "A-10", "A-100", "A-2", "A-9"` $\to$ `"A-10"` comes before `"A-2"`.

### Our Solution:
We decompose each slot into two explicit structured columns:
1. `floor`: `VARCHAR(1)` representing floor letters `'A'` to `'Z'`.
2. `slot_num`: `INTEGER` representing the slot number `1` to `999`.
3. `slot_number`: `VARCHAR(10)` generated/stored representation for API inputs and outputs.

### SQL Query & Index:
```sql
CREATE INDEX idx_slots_alloc_order ON slots (slot_type, status, floor, slot_num);

SELECT * FROM slots 
WHERE slot_type = 'CAR' AND status = 'AVAILABLE' 
ORDER BY floor ASC, slot_num ASC 
LIMIT 1;
```
This guarantees strict mathematical ordering (`A-1 < A-2 < A-9 < A-10 < A-100 < B-1`) directly utilizing composite B-tree indexes without dynamic runtime string parsing.

---

## 6. Assumptions

1. **Timezone Handling**: All timestamps are stored and formatted in UTC with ISO-8601 representation (e.g. `2026-08-25T12:00:00Z`).
2. **Duration Calculation**: Parking duration in `POST /release` is calculated in whole minutes rounded up (`math.ceil(seconds / 60)`), with a minimum of 1 minute.
3. **Vehicle Number Normalization**: Plates are trimmed and converted to uppercase upon API entry. The database enforces uniqueness on the uppercase representation.
4. **GET /vehicles N+1 Prevention**: To satisfy the non-N+1 requirement without extraneous caching, `GET /vehicles` uses a single `LEFT OUTER JOIN` linking `vehicles` $\to$ active `allocations` $\to$ `slots`.

---

## 7. Known Gaps & Future Enhancements

If extending this system beyond the MVP:
1. **Dynamic Dynamic Pricing & Billing Engine**: Tiered tariffs per slot type, weekend rates, and automated payment gateway integration.
2. **Multi-Facility Support**: Tenant-partitioned facilities with configurable floor plans and electric charger capacities.
3. **Reservation & Queuing**: Time-slotted future reservations and FIFO waiting queues with webhook notifications.
4. **Audit Logging & Telemetry**: Event-driven architecture with structured OpenTelemetry spans and slot occupancy heatmaps.

---

## 8. AI Usage & Self-Correction

- **Tools Used**: Antigravity AI pair programmer for scaffolding schemas, writing unit test cases, and OpenAPI specification alignment.
- **Concrete Example of AI Output Rejected/Rewritten**:
  - *Initial AI output*: Proposed using a single `slot_number` column in SQLite and sorting via regex string splitting (`ORDER BY SUBSTR(...)`).
  - *Why rejected*: Runtime string splitting in SQL prevents index utilization, degrades query performance to $O(N)$ table scans, and breaks across different database dialects (PostgreSQL vs SQLite).
  - *Corrected approach*: Decomposed the schema into separate indexed `floor` and `slot_num` columns with a composite B-tree index `(slot_type, status, floor, slot_num)`.
