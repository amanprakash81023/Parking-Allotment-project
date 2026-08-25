# Parking Allotment Backend Service

A high-performance REST API built with **FastAPI** and **PostgreSQL** for managing vehicle parking allotment, multi-floor slot prioritization, and real-time occupancy.

---

## Quickstart

### Option 1: Docker Compose (One-command Setup)
```bash
docker compose up -d --build
```
The API will be available at `http://localhost:8000`.  
Open the interactive Swagger UI at **`http://localhost:8000/docs`**.

---

### Option 2: Local Python Setup

#### 1. Setup Virtual Environment & Dependencies
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

#### 2. Configure Environment
```bash
cp .env.example .env
```
*(Optionally set `DATABASE_URL=sqlite:///./parking.db` for local standalone SQLite testing, or point to your PostgreSQL instance).*

#### 3. Run the Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Running the Automated Test Suite

Run all acceptance tests (TC01 - TC14) with pytest:
```bash
pytest -v
```

---

## Postman Collection Runner

1. Import `postman_collection.json` into Postman.
2. Ensure the collection variable `base_url` is set to `http://localhost:8000`.
3. Run the collection top-to-bottom using Postman Collection Runner. All tests will pass green against a clean database instance.

---

## API Reference Summary

| Method | Endpoint | Description | Status Code |
| :--- | :--- | :--- | :--- |
| **POST** | `/slots` | Create one parking space (`<FLOOR>-<NUMBER>`) | `201 Created` |
| **GET** | `/slots` | List all slots (filterable by `status` & `slot_type`) | `200 OK` |
| **POST** | `/vehicles` | Register vehicle (`BIKE`, `CAR`, `EV`) | `201 Created` |
| **GET** | `/vehicles` | List vehicles with active slot and parked status (No N+1) | `200 OK` |
| **POST** | `/allocate` | Automatically allocate best available slot by preference | `201 Created` |
| **POST** | `/release` | Free slot and return duration in minutes | `200 OK` |
| **GET** | `/allocations` | List active and historical parking sessions | `200 OK` |

---

## Architecture & Design Documentation
See [`IMPLEMENTATION.md`](./IMPLEMENTATION.md) for full architectural explanations, concurrency locking proofs, slot ordering strategies, and design decisions.
