# Smart Airport Ride Pooling Backend

This project implements a simplified Smart Airport Ride Pooling backend using Starlette and SQLite (SQLModel).

Overview
- Group passengers into shared rides while respecting seats and luggage constraints.
- Minimize passenger detours by enforcing per-passenger detour tolerance.
- Demonstrate real-time cancellations and concurrency-safe matching.

Features
- REST APIs to create/cancel requests, trigger matching, list pending requests, and accept proposed rides.
- Greedy matching algorithm with simple detour approximation (Haversine distance).
- Dynamic pricing formula implemented in `pricing.py`.
- Concurrency demo and tests (in-process ASGI tests using pytest + pytest-asyncio).

Quick start (Windows PowerShell)
1. Create a virtualenv and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Initialize DB and load sample data:

```powershell
python migrate.py
python sample_data.py
```

3. Run the server:

```powershell
uvicorn main:app --reload
```

4. API docs and collection
- `openapi.json` — included (manual OpenAPI spec for the Starlette prototype)
- `postman_collection.json` — simple Postman collection for quick testing

Run tests

```powershell
pytest -q
```

Project layout
- `main.py` — Starlette ASGI app with endpoints
- `models.py` — SQLModel models and schema
- `db.py` — DB engine, session helper and simple app-level lock registry
- `matching.py` — matching algorithm and haversine helper
- `pricing.py` — pricing formula
- `sample_data.py` — seeds sample users and requests
- `migrate.py` — initializes DB schema
- `openapi.json` — OpenAPI spec
- `postman_collection.json` — Postman collection
- `tests/` — pytest concurrency test

Design & Architecture
---------------------

DSA approach and complexity
- Algorithm: Greedy first-come-first-serve clustering. Iterate pending requests in FIFO order, and attempt to add compatible requests into the same group while respecting seat and luggage capacity and detour tolerance.
- Complexity: O(n^2) worst-case (pairwise checks). Space O(n).

Edge cases considered
- Empty request list — no rides created.
- Large luggage or seat requests — prevented from grouping if capacity exceeded.
- Cancellation race — matching is protected by an application-level lock so cancelled requests are not assigned.

Low Level Design
- Classes (models): `User`, `RideRequest`, `Ride` (see `models.py`).
- Services: `matching.py` (matching service), `pricing.py` (pricing service).
- Patterns: service layer (matching/pricing) separated from transport (main app), simple locking for concurrency.

High Level Architecture
- Client → Starlette app (ASGI) → Database (SQLite for prototype)
- For scale: API servers + load balancer, queueing (Redis/Kafka), partitioned matching workers, Postgres/PostGIS for spatial queries, caching (Redis) and monitoring.

Database schema & indexing strategy
- Tables: users, ride_requests, rides (defined in `models.py`).
- Migrations: `migrate.py` creates the schema. For production use Alembic.
- Indexes to add (production): `ride_requests(status)`, `ride_requests(created_at)`, spatial index (PostGIS) on origin/dest.

Concurrency handling
- Prototype: application-level lock `db.get_lock("matching")` to serialize matching and cancellation operations.
- Production: prefer DB-level transactions + row-level locks (SELECT FOR UPDATE) or queue-based partitioned workers to avoid global locks.

Dynamic pricing
- Implemented in `pricing.py`:
  price_per_person = round((base + per_km * distance_km) * occupancy_discount * demand_factor, 2)
  occupancy_discount = max(0.7, 1.0 - 0.05 * (occupancy - 1))

API Endpoints (summary)
- POST /request — create a ride request (body: user_id, origin_lat/lng, dest_lat/lng, optional seats_required, luggage, detour_tolerance_km)
- POST /cancel/{request_id} — cancel a request
- POST /match/trigger — run the matching worker synchronously (for demo)
- GET /requests/pending — list pending requests
- GET /rides/{ride_id} — retrieve ride details
- POST /rides/{ride_id}/accept — accept a proposed ride (simulates driver acceptance)

Packaging, git and submission
- I initialized a local git repository and committed the code in this workspace (see instructions below). To publish: add a remote and push the `main` branch.

Local git commands (example)
```powershell
git init
git add .
git commit -m "Initial prototype: ride pooling backend"
# then add remote:
git remote add origin <your-repo-url>
git push -u origin main
```

Assumptions & limitations
- Straight-line distance (Haversine) distances approximate real-world travel distances.
- Starlette used in this local prototype to reduce dependency issues; OpenAPI is provided as a hand-written JSON file.
- SQLite is for local testing; switch to Postgres/PostGIS for production.

Next steps (recommended)
1. Replace SQLite with Postgres and add Alembic migrations.
2. Add a partitioned queue & background workers (Redis + RQ/Celery or Kafka + consumers).
3. Add geospatial indexing (PostGIS) or Redis GEO to scale matching and reduce O(n^2) costs.
4. Restore FastAPI + auto-generated Swagger (if you prefer), or keep Starlette and enhance `openapi.json`.

Contact
If you want me to perform any next step (Postgres/Alembic, FastAPI restore, Docker Compose, or a full Push to a git remote), tell me which and I will implement it and re-run tests.
# Smart Airport Ride Pooling Backend

This project implements a simplified Smart Airport Ride Pooling backend using FastAPI and SQLite (SQLModel).

Features
- Group passengers into shared rides using a greedy clustering algorithm.
- Respect seat and luggage constraints.
- Enforce detour tolerance per passenger (approximate with straight-line distances).
- Handle real-time cancellations and concurrency with app-level locks.
- Dynamic pricing based on distance, occupancy and demand.

Run locally
1. Create a virtualenv and install dependencies:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Initialize DB and load sample data:

```powershell
python sample_data.py
```

Database migrations

```powershell
python migrate.py
```

Export API docs

```powershell
python export_openapi.py
```

3. Run the server:

```powershell
uvicorn main:app --reload
```

API
- OpenAPI is available at `http://127.0.0.1:8000/docs` after starting the server.

Project structure
- `main.py` - FastAPI app and endpoints
- `models.py` - SQLModel ORM models
- `db.py` - Database engine and session utilities
- `matching.py` - Matching worker and grouping algorithm
- `pricing.py` - Pricing formula
- `sample_data.py` - Create sample users and requests
- `tests/` - concurrency demo tests

Concurrency demo

```powershell
python concurrency_demo.py
```

Notes & assumptions
- Distances are approximated using Haversine; no real routing engine used.
- SQLite is used for simplicity. Concurrency is demonstrated via asyncio locks.
- This is a runnable prototype to demonstrate design, not a production-ready system.
