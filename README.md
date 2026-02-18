# Smart Airport Ride Pooling Backend

A runnable prototype implementing the Hintro assignment: group airport passengers into shared rides while respecting seat/luggage constraints, detour tolerances, real-time cancellations, concurrency handling, and dynamic pricing.

---

## Features

- REST APIs: create/cancel ride requests, trigger matching, list pending, accept rides
- Greedy matching algorithm with Haversine-based detour estimation
- Dynamic pricing formula (distance + occupancy discount + demand factor)
- Concurrency-safe matching via app-level locks
- Alembic database migrations (SQLite locally, Postgres via Docker Compose)
- OpenAPI spec (`openapi.json`) + Swagger UI at `/docs`
- Postman collection (`postman_collection.json`)
- 23 passing tests (unit + integration + concurrency)

---

## Quick Start (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python migrate.py          # create schema
python sample_data.py      # seed sample users & requests

uvicorn main:app --reload  # start server
```

- Swagger UI → http://127.0.0.1:8000/docs
- Raw OpenAPI → http://127.0.0.1:8000/openapi.json
- Import `postman_collection.json` into Postman for quick testing

---

## Run Tests

```powershell
pytest -v
```

Expected: **23 passed** (unit tests for pricing, Haversine, matching algorithm, all 6 API endpoints, plus a concurrency test with 5 simultaneous match triggers).

---

## Run with Docker Compose (Postgres + Redis)

```powershell
docker compose up --build
```

| Service | URL |
|---------|-----|
| App | http://localhost:8000 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

On startup the container runs `python migrate.py` automatically.

---

## Database Migrations (Alembic)

```powershell
# apply all migrations
alembic upgrade head

# generate a new migration after model changes
alembic revision --autogenerate -m "describe change"

# downgrade one step
alembic downgrade -1
```

To target Postgres instead of SQLite:

```powershell
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/ridepool"
alembic upgrade head
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/request` | Create a ride request |
| POST | `/cancel/{request_id}` | Cancel a pending request |
| POST | `/match/trigger` | Run the matching worker (synchronous demo) |
| GET | `/requests/pending` | List all pending requests |
| GET | `/rides/{ride_id}` | Get ride details |
| POST | `/rides/{ride_id}/accept` | Accept a proposed ride |

Full request/response schemas in `openapi.json`.

---

## Project Structure

```
.
├── main.py                  # Starlette ASGI app & all routes
├── models.py                # SQLModel ORM models (User, RideRequest, Ride)
├── db.py                    # DB engine, session factory, lock registry
├── matching.py              # Greedy matching algorithm + Haversine helper
├── pricing.py               # Dynamic pricing formula
├── migrate.py               # Direct schema creation (SQLite quick-start)
├── sample_data.py           # Seed sample users & requests
├── export_openapi.py        # Exports openapi.json from running server
├── concurrency_demo.py      # Concurrency demonstration script
├── openapi.json             # OpenAPI 3.0 spec (served at /openapi.json)
├── postman_collection.json  # Postman collection
├── Dockerfile               # Container image
├── docker-compose.yml       # App + Postgres + Redis
├── alembic/                 # Alembic migration scripts
│   ├── env.py
│   └── versions/
│       └── 199d3cfa0210_initial_schema.py
└── tests/
    ├── test_unit.py         # 22 unit + integration tests
    └── test_concurrency.py  # Concurrency test
```

---

## Design Deliverables

### DSA Approach & Complexity

**Algorithm**: Greedy first-come-first-served (FCFS) clustering.

1. Fetch all `pending` requests ordered by `created_at` (FIFO).
2. For each unassigned request (seed), create a new ride group.
3. Iterate remaining unassigned requests; merge into the group if:
   - Combined seats ≤ `max_seats`
   - Combined luggage ≤ `max_luggage`
   - Approximate detour for existing passengers ≤ their `detour_tolerance_km`
4. Commit ride to DB; mark grouped requests as `matched`.

**Complexity**: O(n²) worst-case (pairwise comparisons). Space O(n).

For production: use spatial indexing (PostGIS / Redis GEO) to pre-filter candidates by proximity, reducing effective comparisons to O(n · k) where k ≪ n.

---

### Low-Level Design (Class Diagram)

```mermaid
classDiagram
    class User {
        int id
        str name
    }
    class RideRequest {
        int id
        int user_id
        float origin_lat
        float origin_lng
        float dest_lat
        float dest_lng
        int seats_required
        int luggage
        float detour_tolerance_km
        datetime created_at
        str status
    }
    class Ride {
        int id
        str driver
        int seats_total
        int occupancy
        int luggage_capacity
        int luggage_used
        str requests
        float origin_lat
        float origin_lng
        float dest_lat
        float dest_lng
        datetime created_at
        str status
    }
    User "1" --> "*" RideRequest
    RideRequest "*" --> "1" Ride : grouped_into
```

---

### High-Level Architecture

```mermaid
flowchart LR
  Client --> API[Starlette API :8000]
  API --> DB[(SQLite / Postgres)]
  API --> Matcher[Matching Worker]
  Matcher --> DB

  subgraph Production Scale
    LB[Load Balancer] --> App1[API Server]
    LB --> App2[API Server]
    App1 --> Queue[(Redis / Kafka)]
    App2 --> Queue
    Queue --> W1[Matching Worker]
    Queue --> W2[Matching Worker]
    W1 --> PG[(Postgres + PostGIS)]
    W2 --> PG
    Cache[Redis Cache] --> App1
    Cache --> App2
  end
```

---

### Concurrency Handling

| Layer | Mechanism |
|-------|-----------|
| Prototype | `threading.Lock` via `db.get_lock("matching")` — serialises matching + cancellation |
| Production | DB row-level locks (`SELECT FOR UPDATE`), optimistic locking with version columns, or partitioned queue consumers (one worker per geo-partition) to eliminate global locks |

Tests: `tests/test_concurrency.py` fires 5 simultaneous `/match/trigger` requests and asserts at least one succeeds.

---

### Database Schema & Indexing

| Table | Key Indexes |
|-------|-------------|
| `ride_requests` | `status` (filter pending), `created_at` (FIFO ordering), `(origin_lat, origin_lng)` spatial |
| `rides` | `status` |
| `users` | primary key |

Migrations live in `alembic/versions/`. Run `alembic upgrade head` to apply.

---

### Dynamic Pricing Formula

```
price_per_person = round(
    (5.0 + 1.2 × distance_km)
    × max(0.7, 1.0 − 0.05 × (occupancy − 1))
    × demand_factor,
    2
)
```

- Base fare: **$5.00**
- Per-km rate: **$1.20**
- Occupancy discount: 5% per extra passenger, floor at 30% discount
- Demand factor: multiplier (default 1.0; raise during peak hours)

---

## Assumptions & Limitations

- Haversine straight-line distance approximates actual road distance.
- Starlette used instead of FastAPI to avoid a Pydantic v1 / Python 3.12 incompatibility; OpenAPI spec is hand-written JSON.
- SQLite for local development; switch `DATABASE_URL` env var to Postgres for production.
- Matching is triggered manually via API for demo simplicity; in production this runs as a scheduled background job.
