# Parking Allotment Backend — Technical Interview Presentation

> **Objective:** Comprehensive, slide-by-slide technical presentation guide designed for the technical review call and system architecture defense.

---

## Slide 1: System Overview & Architecture

### High-Level Domain Model
The system models a single multi-floor parking facility with 3 core concepts:
1. **Slots (`slots`)**: Physical parking spaces identified by `<FLOOR>-<NUMBER>` (e.g. `A-1`, `B-10`), categorized as `BIKE`, `CAR`, or `EV`, with status `AVAILABLE` or `OCCUPIED`.
2. **Vehicles (`vehicles`)**: Registered vehicles with normalized uppercase alphanumeric license plates and assigned vehicle types.
3. **Allocations (`allocations`)**: Historical & active occupancy records linking a vehicle to a slot with UTC entry and release timestamps.

```
+-------------------------------------------------------+
|                    FastAPI Application                |
|  +----------------+  +----------------+  +---------+  |
|  | /slots Routers |  | /vehicles Rou  |  | /alloc  |  |
|  +--------+-------+  +--------+-------+  +----+----+  |
|           |                   |               |       |
|           v                   v               v       |
|  +-------------------------------------------------+  |
|  |             Service Layer (services.py)         |  |
|  |   - Slot ordering & preference selection        |  |
|  |   - Concurrency control & row locking           |  |
|  |   - Transaction management & duration math      |  |
|  +------------------------+------------------------+  |
|                           |                           |
|                           v                           |
|  +-------------------------------------------------+  |
|  |          SQLAlchemy ORM / Data Layer            |  |
|  +------------------------+------------------------+  |
+---------------------------|---------------------------+
                            v
+-------------------------------------------------------+
|                  PostgreSQL Database                  |
|  - slots table (floor: VARCHAR, slot_num: INT)        |
|  - vehicles table (vehicle_number: UNIQUE)            |
|  - allocations table (partial unique active indexes)  |
+-------------------------------------------------------+
```

---

## Slide 2: Crucial Design Decisions & Trade-Offs

### 1. The Slot Ordering Solution (§4.1)
- **Problem**: Storing `slot_number` as plain text causes alphabetical sorting bugs: `"A-1", "A-10", "A-100", "A-2", "A-9"`.
- **Solution**: Decomposed into separate physical columns:
  - `floor` (`VARCHAR(1)`): 'A' through 'Z'
  - `slot_num` (`INTEGER`): 1 through 999
- **Database Index**: Composite B-Tree Index:
  ```sql
  CREATE INDEX idx_slots_alloc_order ON slots (slot_type, status, floor, slot_num);
  ```
- **Interview Defense**: This eliminates slow runtime regex/string parsing and leverages B-Tree indexes for $O(\log N)$ lookups.

---

### 2. Concurrency & Race Condition Defense (§4.4)
- **Problem**: Multiple concurrent allocation requests could see the same available slot and attempt to assign it simultaneously (double allocation).
- **Defense in Depth**:
  1. **Application / Query Level**: Row-level locking with `SELECT ... FOR UPDATE`:
     ```python
     query = db.query(Slot).filter(
         Slot.slot_type == pref, Slot.status == 'AVAILABLE'
     ).order_by(Slot.floor.asc(), Slot.slot_num.asc()).with_for_update()
     ```
  2. **Database Level**: Partial Unique Indexes guaranteeing physical impossibility of duplicate active allocations:
     ```sql
     CREATE UNIQUE INDEX uq_active_vehicle_allocation ON allocations (vehicle_id) WHERE status = 'ACTIVE';
     CREATE UNIQUE INDEX uq_active_slot_allocation ON allocations (slot_id) WHERE status = 'ACTIVE';
     ```
  3. **Error Normalization**: Intercepts DB `IntegrityError` and translates it to a clean `409 VEHICLE_ALREADY_PARKED` without throwing a 500 error.

---

### 3. Vehicle Preference Algorithm (§4.2)
Vehicles are matched by priority, where **preference beats slot number**:
- `BIKE` $\to$ `['BIKE']`
- `CAR` $\to$ `['CAR']` (Cars can never use EV slots)
- `EV` $\to$ `['EV', 'CAR']` (EVs prefer EV slots; fall back to CAR slots if all EV slots are full)

---

### 4. Preventing N+1 Query Anti-Pattern (§5.4)
- In `GET /vehicles`, instead of querying active allocations in a loop per vehicle ($O(N)$ extra queries), a single `LEFT OUTER JOIN` resolves parking status and current slot:
  ```python
  db.query(Vehicle, Allocation.id.isnot(None), Slot.slot_number)\
    .outerjoin(Allocation, (Allocation.vehicle_id == Vehicle.id) & (Allocation.status == 'ACTIVE'))\
    .outerjoin(Slot, Slot.id == Allocation.slot_id).all()
  ```

---

## Slide 3: Code Deep-Dive & "What Breaks If We Delete This Line?"

In the review call, interviewers frequently test line-by-line understanding:

### Scenario A:
```python
# app/services.py (inside allocate_vehicle)
if db.bind.dialect.name != "sqlite":
    query = query.with_for_update()
```
- **What breaks if deleted?** Under high concurrency (e.g. 20 concurrent requests for 5 slots), multiple worker processes/threads in PostgreSQL can read the same slot before either commits, leading to race conditions and reliance solely on constraint rollbacks rather than ordered lock acquisition.

---

### Scenario B:
```sql
-- schema.sql
CREATE UNIQUE INDEX uq_active_slot_allocation ON allocations (slot_id) WHERE status = 'ACTIVE';
```
- **What breaks if deleted?** The database loses the ultimate authority to prevent duplicate active allocations for the same slot. If an application bug or direct SQL insert bypasses application checks, two vehicles will occupy the same slot concurrently.

---

### Scenario C:
```python
# app/schemas.py (inside VehicleCreate validator)
v = v.strip().upper()
```
- **What breaks if deleted?** `mh12ab1234` and `MH12AB1234` would be treated as distinct strings, violating §4.6 case-insensitive uniqueness and allowing duplicate registrations.

---

### Scenario D:
```python
# app/services.py (inside release_vehicle)
duration_minutes = max(1, math.ceil(delta_seconds / 60))
```
- **What breaks if deleted?** Duration would either be floating-point/truncated instead of rounded up per §4.5, or could return 0 for sub-minute stays.

---

## Slide 4: Error Handling Envelope Architecture (§5.8)

Every single error response across all endpoints (including Pydantic validation errors) conforms to the strict contract:
```json
{
  "error": {
    "code": "VEHICLE_NOT_FOUND",
    "message": "Vehicle 'MH12AB1234' not found.",
    "details": null
  }
}
```
Implemented centrally via 4 global exception handlers in `app/exceptions.py`:
1. `AppException` $\to$ Domain business logic errors (400, 404, 409).
2. `RequestValidationError` $\to$ Pydantic schema validation failures (422).
3. `StarletteHTTPException` $\to$ Framework HTTP errors.
4. `Exception` $\to$ Unhandled fallback returning safe 500 `INTERNAL_ERROR` without leaking SQL or stack traces.

---

## Slide 5: Testing Strategy & Verification

### Automated Pytest Suite (`tests/test_api.py`)
- **22 Unit & Acceptance Tests** covering TC01–TC14.
- **Isolated In-Memory Fixtures**: Each test function creates a clean schema with SQLite `StaticPool` and drops it upon teardown, ensuring 100% test independence and idempotency.
- **Concurrency Test (TC11)**: Validates that 20 parallel/sequential allocations against 5 slots yield exactly 5 $\times$ `201`, 15 $\times$ `400`, 5 distinct slots, and 0 $\times$ `500`.

---

## Slide 6: Interview Q&A Quick Sheet

| Question | Strong Answer |
| :--- | :--- |
| **Why not use Redis for locks?** | For a single database backend, database row locks (`FOR UPDATE`) and partial unique indexes provide strict ACID guarantees without introducing external network dependencies, distributed lock timeouts, or split-brain states. |
| **Why separate `floor` and `slot_num`?** | Lexicographical ASCII sorting sorts `"A-10"` before `"A-2"`. Splitting them allows direct composite indexing and native numeric sorting in the database engine. |
| **Why use partial indexes instead of table constraints?** | Allocations has historical records where a vehicle or slot can appear multiple times with status `RELEASED`. A standard unique constraint would block historical records. A partial unique index (`WHERE status = 'ACTIVE'`) enforces uniqueness only for active sessions. |
