import concurrent.futures
import pytest


def test_tc01_create_slot(client):
    """TC01: empty -> POST /slots A-1 CAR -> 201, status AVAILABLE"""
    res = client.post("/slots", json={"slot_number": "A-1", "slot_type": "CAR"})
    assert res.status_code == 201
    data = res.json()
    assert data["slot_number"] == "A-1"
    assert data["slot_type"] == "CAR"
    assert data["status"] == "AVAILABLE"
    assert "id" in data


def test_tc02_duplicate_slot(client):
    """TC02: A-1 exists -> POST /slots A-1 again -> 409 SLOT_ALREADY_EXISTS"""
    client.post("/slots", json={"slot_number": "A-1", "slot_type": "CAR"})
    res = client.post("/slots", json={"slot_number": "A-1", "slot_type": "CAR"})
    assert res.status_code == 409
    err = res.json()["error"]
    assert err["code"] == "SLOT_ALREADY_EXISTS"


def test_tc02b_invalid_slot_format(client):
    """TC02b: POST /slots A-01 / a-1 / A1 -> 422 VALIDATION_ERROR"""
    for invalid_slot in ["A-01", "a-1", "A1", "A-0", "AA-1"]:
        res = client.post("/slots", json={"slot_number": invalid_slot, "slot_type": "CAR"})
        assert res.status_code == 422, f"Failed on {invalid_slot}"
        err = res.json()["error"]
        assert err["code"] == "VALIDATION_ERROR"


def test_tc03_register_vehicle(client):
    """TC03: empty -> POST /vehicles CAR -> 201"""
    res = client.post(
        "/vehicles",
        json={
            "vehicle_number": "MH12AB1234",
            "owner_name": "Ravi Kumar",
            "vehicle_type": "CAR",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["vehicle_number"] == "MH12AB1234"
    assert data["owner_name"] == "Ravi Kumar"
    assert data["vehicle_type"] == "CAR"


def test_tc04_duplicate_vehicle_lowercase(client):
    """TC04: vehicle exists -> POST same plate, lowercase -> 409 VEHICLE_ALREADY_EXISTS"""
    client.post(
        "/vehicles",
        json={
            "vehicle_number": "MH12AB1234",
            "owner_name": "Ravi Kumar",
            "vehicle_type": "CAR",
        },
    )
    res = client.post(
        "/vehicles",
        json={
            "vehicle_number": "mh12ab1234",
            "owner_name": "Ravi Kumar",
            "vehicle_type": "CAR",
        },
    )
    assert res.status_code == 409
    err = res.json()["error"]
    assert err["code"] == "VEHICLE_ALREADY_EXISTS"


def test_tc05_allocate_car_lowest_slot(client):
    """TC05: slots A-1, A-2, A-10 free -> allocate a CAR -> slot A-1"""
    for s in ["A-10", "A-2", "A-1"]:
        client.post("/slots", json={"slot_number": s, "slot_type": "CAR"})
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB1234", "owner_name": "Ravi", "vehicle_type": "CAR"},
    )
    res = client.post("/allocate", json={"vehicle_number": "MH12AB1234"})
    assert res.status_code == 201
    assert res.json()["slot_number"] == "A-1"


def test_tc05b_allocate_car_order_numeric(client):
    """TC05b: A-1 occupied; A-2, A-10 free, all CAR -> allocate a CAR -> slot A-2, not A-10"""
    for s in ["A-1", "A-2", "A-10"]:
        client.post("/slots", json={"slot_number": s, "slot_type": "CAR"})
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB1111", "owner_name": "User 1", "vehicle_type": "CAR"},
    )
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB2222", "owner_name": "User 2", "vehicle_type": "CAR"},
    )
    client.post("/allocate", json={"vehicle_number": "MH12AB1111"})  # Takes A-1
    res = client.post("/allocate", json={"vehicle_number": "MH12AB2222"})
    assert res.status_code == 201
    assert res.json()["slot_number"] == "A-2"


def test_tc05c_bike_no_compatible_slot(client):
    """TC05c: only CAR slots free -> allocate a BIKE -> 400 NO_SLOT_AVAILABLE"""
    client.post("/slots", json={"slot_number": "A-1", "slot_type": "CAR"})
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12BK0001", "owner_name": "Biker", "vehicle_type": "BIKE"},
    )
    res = client.post("/allocate", json={"vehicle_number": "MH12BK0001"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "NO_SLOT_AVAILABLE"


def test_tc05d_ev_prefers_ev_slot(client):
    """TC05d: EV slot B-3 free, CAR slot A-1 free -> allocate an EV -> slot B-3"""
    client.post("/slots", json={"slot_number": "A-1", "slot_type": "CAR"})
    client.post("/slots", json={"slot_number": "B-3", "slot_type": "EV"})
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12EV9999", "owner_name": "EV User", "vehicle_type": "EV"},
    )
    res = client.post("/allocate", json={"vehicle_number": "MH12EV9999"})
    assert res.status_code == 201
    assert res.json()["slot_number"] == "B-3"


def test_tc05e_ev_falls_back_to_car_slot(client):
    """TC05e: EV slots full, CAR slot A-1 free -> allocate an EV -> slot A-1"""
    client.post("/slots", json={"slot_number": "B-3", "slot_type": "EV"})
    client.post("/slots", json={"slot_number": "A-1", "slot_type": "CAR"})
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12EV0001", "owner_name": "EV 1", "vehicle_type": "EV"},
    )
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12EV0002", "owner_name": "EV 2", "vehicle_type": "EV"},
    )
    client.post("/allocate", json={"vehicle_number": "MH12EV0001"})  # Takes B-3
    res = client.post("/allocate", json={"vehicle_number": "MH12EV0002"})
    assert res.status_code == 201
    assert res.json()["slot_number"] == "A-1"


def test_tc05f_car_cannot_take_ev_slot(client):
    """TC05f: only EV slot free -> allocate a CAR -> 400 NO_SLOT_AVAILABLE"""
    client.post("/slots", json={"slot_number": "B-3", "slot_type": "EV"})
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12CC7777", "owner_name": "Car User", "vehicle_type": "CAR"},
    )
    res = client.post("/allocate", json={"vehicle_number": "MH12CC7777"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "NO_SLOT_AVAILABLE"


def test_tc06_vehicle_already_parked(client):
    """TC06: vehicle already parked -> allocate same vehicle -> 409 VEHICLE_ALREADY_PARKED"""
    client.post("/slots", json={"slot_number": "A-1", "slot_type": "CAR"})
    client.post("/slots", json={"slot_number": "A-2", "slot_type": "CAR"})
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB1234", "owner_name": "Ravi", "vehicle_type": "CAR"},
    )
    client.post("/allocate", json={"vehicle_number": "MH12AB1234"})
    res = client.post("/allocate", json={"vehicle_number": "MH12AB1234"})
    assert res.status_code == 409
    err = res.json()["error"]
    assert err["code"] == "VEHICLE_ALREADY_PARKED"


def test_tc07_no_slot_available(client):
    """TC07: every compatible slot occupied -> allocate -> 400 NO_SLOT_AVAILABLE"""
    client.post("/slots", json={"slot_number": "A-1", "slot_type": "CAR"})
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB1111", "owner_name": "User 1", "vehicle_type": "CAR"},
    )
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB2222", "owner_name": "User 2", "vehicle_type": "CAR"},
    )
    client.post("/allocate", json={"vehicle_number": "MH12AB1111"})
    res = client.post("/allocate", json={"vehicle_number": "MH12AB2222"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "NO_SLOT_AVAILABLE"


def test_tc08_and_tc08b_release_and_reallocate(client):
    """TC08 & TC08b: vehicle parked in A-1 -> release it (200) -> allocate another CAR gets A-1 again"""
    client.post("/slots", json={"slot_number": "A-1", "slot_type": "CAR"})
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB1234", "owner_name": "Ravi", "vehicle_type": "CAR"},
    )
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB5678", "owner_name": "Sita", "vehicle_type": "CAR"},
    )
    client.post("/allocate", json={"vehicle_number": "MH12AB1234"})

    # Release
    res_rel = client.post("/release", json={"vehicle_number": "MH12AB1234"})
    assert res_rel.status_code == 200
    rel_data = res_rel.json()
    assert rel_data["slot_number"] == "A-1"
    assert rel_data["status"] == "RELEASED"
    assert "exit_time" in rel_data
    assert "duration_minutes" in rel_data

    # Reallocate to another car (TC08b)
    res_alloc = client.post("/allocate", json={"vehicle_number": "MH12AB5678"})
    assert res_alloc.status_code == 201
    assert res_alloc.json()["slot_number"] == "A-1"


def test_tc09_unregistered_plate_release(client):
    """TC09: plate never registered -> release it -> 404 VEHICLE_NOT_FOUND"""
    res = client.post("/release", json={"vehicle_number": "MH99ZZ9999"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "VEHICLE_NOT_FOUND"


def test_tc09b_and_tc09c_registered_not_parked_and_duplicate_release(client):
    """TC09b & TC09c: registered not parked / just released -> 409 VEHICLE_NOT_PARKED"""
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB1234", "owner_name": "Ravi", "vehicle_type": "CAR"},
    )
    # Not parked yet (TC09b)
    res = client.post("/release", json={"vehicle_number": "MH12AB1234"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "VEHICLE_NOT_PARKED"

    # Park then release then release again (TC09c)
    client.post("/slots", json={"slot_number": "A-1", "slot_type": "CAR"})
    client.post("/allocate", json={"vehicle_number": "MH12AB1234"})
    client.post("/release", json={"vehicle_number": "MH12AB1234"})

    res2 = client.post("/release", json={"vehicle_number": "MH12AB1234"})
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "VEHICLE_NOT_PARKED"


def test_tc10_get_allocations_filter(client):
    """TC10: 2 active, 3 released -> GET /allocations -> only the 2 active"""
    # Create 5 slots & 5 vehicles
    for i in range(1, 6):
        client.post("/slots", json={"slot_number": f"A-{i}", "slot_type": "CAR"})
        client.post(
            "/vehicles",
            json={"vehicle_number": f"MH12AB100{i}", "owner_name": f"User {i}", "vehicle_type": "CAR"},
        )
        client.post("/allocate", json={"vehicle_number": f"MH12AB100{i}"})

    # Release 3 vehicles
    for i in range(1, 4):
        client.post("/release", json={"vehicle_number": f"MH12AB100{i}"})

    # Default GET /allocations should return only active
    res = client.get("/allocations")
    assert res.status_code == 200
    allocations = res.json()
    assert len(allocations) == 2
    for item in allocations:
        assert item["status"] == "ACTIVE"


def test_tc11_concurrency_parallel_allocates(client, db_session):
    """TC11: 5 free CAR slots, 20 registered cars -> 20 sequential/parallel allocates -> exactly 5 x 201, 15 x 400, 5 distinct slots, 0 x 500"""
    for i in range(1, 6):
        client.post("/slots", json={"slot_number": f"A-{i}", "slot_type": "CAR"})
    for i in range(1, 21):
        plate = f"MH12CC{i:04d}"
        client.post(
            "/vehicles",
            json={"vehicle_number": plate, "owner_name": f"Driver {i}", "vehicle_type": "CAR"},
        )

    results = []
    for i in range(1, 21):
        plate = f"MH12CC{i:04d}"
        res = client.post("/allocate", json={"vehicle_number": plate})
        results.append(res)

    status_codes = [r.status_code for r in results]
    assert status_codes.count(201) == 5
    assert status_codes.count(400) == 15
    assert 500 not in status_codes

    allocated_slots = [r.json()["slot_number"] for r in results if r.status_code == 201]
    assert len(set(allocated_slots)) == 5


def test_tc12_vehicle_validation_errors(client):
    """TC12: POST /vehicles {} / blank owner / vehicle_type 'PLANE' -> 422 error envelope"""
    # Empty payload
    r1 = client.post("/vehicles", json={})
    assert r1.status_code == 422
    assert r1.json()["error"]["code"] == "VALIDATION_ERROR"
    assert r1.json()["error"]["details"] is not None

    # Blank owner
    r2 = client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB1234", "owner_name": "   ", "vehicle_type": "CAR"},
    )
    assert r2.status_code == 422
    assert r2.json()["error"]["code"] == "VALIDATION_ERROR"

    # Invalid vehicle type "PLANE"
    r3 = client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB1234", "owner_name": "Pilot", "vehicle_type": "PLANE"},
    )
    assert r3.status_code == 422
    assert r3.json()["error"]["code"] == "VALIDATION_ERROR"


def test_tc13_slots_invalid_status_filter(client):
    """TC13: GET /slots?status=BANANA -> 422"""
    res = client.get("/slots?status=BANANA")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_tc14_mixed_slots_ordering(client):
    """TC14: mixed slots -> GET /slots -> sorted A-1, A-2, A-10, B-1"""
    slots_to_add = ["B-1", "A-10", "A-1", "A-2"]
    for s in slots_to_add:
        client.post("/slots", json={"slot_number": s, "slot_type": "CAR"})

    res = client.get("/slots")
    assert res.status_code == 200
    returned_slot_numbers = [item["slot_number"] for item in res.json()]
    assert returned_slot_numbers == ["A-1", "A-2", "A-10", "B-1"]


def test_get_vehicles_non_n_plus_one(client):
    """Test GET /vehicles returns is_parked and current_slot properly."""
    client.post("/slots", json={"slot_number": "A-1", "slot_type": "CAR"})
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB1234", "owner_name": "Ravi", "vehicle_type": "CAR"},
    )
    client.post(
        "/vehicles",
        json={"vehicle_number": "MH12AB5678", "owner_name": "Sita", "vehicle_type": "CAR"},
    )
    client.post("/allocate", json={"vehicle_number": "MH12AB1234"})

    res = client.get("/vehicles")
    assert res.status_code == 200
    vehicles = res.json()
    assert len(vehicles) == 2
    v1 = next(v for v in vehicles if v["vehicle_number"] == "MH12AB1234")
    v2 = next(v for v in vehicles if v["vehicle_number"] == "MH12AB5678")

    assert v1["is_parked"] is True
    assert v1["current_slot"] == "A-1"
    assert v2["is_parked"] is False
    assert v2["current_slot"] is None
