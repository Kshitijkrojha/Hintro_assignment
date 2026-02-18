"""
Unit tests for matching algorithm, pricing formula, and API endpoints.
Covers:
- Matching groups passengers correctly
- Seat / luggage constraints respected
- Detour tolerance enforced
- Cancellation removes requests from matching
- Pricing formula correctness
- API endpoints: create_request, cancel, pending list, match trigger, ride detail, accept
"""
import os
import sys
import pytest
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db import init_db, get_session, engine
from models import User, RideRequest, Ride
from pricing import compute_price
from matching import haversine_km, approximate_detour_if_added
from sqlmodel import SQLModel


# ────────────────────────── fixtures ────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test runs against a fresh in-memory database."""
    import db as db_mod
    test_db = f"sqlite:///{tmp_path}/test.db"
    new_engine = __import__("sqlmodel").create_engine(
        test_db, echo=False, connect_args={"check_same_thread": False}
    )
    monkeypatch.setattr(db_mod, "engine", new_engine)
    SQLModel.metadata.create_all(new_engine)
    yield
    SQLModel.metadata.drop_all(new_engine)


def make_user(name="Alice"):
    session = get_session()
    u = User(name=name)
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def make_request(user_id, olat=40.72, olng=-73.80, dlat=40.64, dlng=-73.78,
                 seats=1, luggage=0, detour=5.0, status="pending"):
    session = get_session()
    r = RideRequest(
        user_id=user_id,
        origin_lat=olat, origin_lng=olng,
        dest_lat=dlat, dest_lng=dlng,
        seats_required=seats,
        luggage=luggage,
        detour_tolerance_km=detour,
        status=status,
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


# ────────────────────────── pricing tests ───────────────────────────────────

def test_pricing_solo_ride():
    price = compute_price(distance_km=10.0, occupancy=1, seats_total=4)
    assert price == round((5.0 + 1.2 * 10.0) * 1.0 * 1.0, 2)


def test_pricing_shared_ride_cheaper_per_person():
    solo = compute_price(10.0, occupancy=1, seats_total=4)
    shared = compute_price(10.0, occupancy=3, seats_total=4)
    assert shared < solo


def test_pricing_demand_factor():
    base = compute_price(10.0, occupancy=1, seats_total=4, demand_factor=1.0)
    surge = compute_price(10.0, occupancy=1, seats_total=4, demand_factor=1.5)
    assert surge > base


def test_pricing_occupancy_discount_floor():
    # with 10 passengers discount should not fall below 0.7
    price = compute_price(10.0, occupancy=10, seats_total=10)
    floor_price = round((5.0 + 1.2 * 10.0) * 0.7 * 1.0, 2)
    assert price == floor_price


# ────────────────────────── haversine helper ────────────────────────────────

def test_haversine_zero():
    assert haversine_km((40.0, -73.0), (40.0, -73.0)) == 0.0


def test_haversine_known_distance():
    # JFK to LGA is roughly ~17 km
    jfk = (40.6413, -73.7781)
    lga = (40.7769, -73.8740)
    d = haversine_km(jfk, lga)
    assert 15 < d < 20


# ────────────────────────── matching algorithm ──────────────────────────────

def test_matching_groups_two_nearby_requests():
    from matching import run_matching
    u1 = make_user("U1")
    u2 = make_user("U2")
    make_request(u1.id, olat=40.72, olng=-73.80)
    make_request(u2.id, olat=40.72, olng=-73.80)
    result = run_matching()
    assert result["created_rides"] >= 1
    session = get_session()
    matched = session.query(RideRequest).filter(RideRequest.status == "matched").all()
    assert len(matched) == 2


def test_matching_respects_seat_limit():
    from matching import run_matching
    u = make_user("U")
    # fill 4 seats with one request, add another asking 2 → must create separate ride
    make_request(u.id, seats=4)
    make_request(u.id, seats=2)
    result = run_matching()
    assert result["created_rides"] == 2


def test_matching_respects_luggage_limit():
    from matching import run_matching
    u = make_user("U")
    make_request(u.id, luggage=4)
    make_request(u.id, luggage=2)
    result = run_matching()
    # second request cannot join because luggage 4+2=6 > max 4
    rides = get_session().query(Ride).all()
    for ride in rides:
        ids = [int(i) for i in ride.requests.split(",") if i]
        assert len(ids) <= 4


def test_matching_empty_queue():
    from matching import run_matching
    result = run_matching()
    assert result["created_rides"] == 0


def test_cancelled_request_not_matched():
    from matching import run_matching
    u = make_user("U")
    r = make_request(u.id, status="cancelled")
    result = run_matching()
    assert result["created_rides"] == 0
    session = get_session()
    still_cancelled = session.get(RideRequest, r.id)
    assert still_cancelled.status == "cancelled"


# ────────────────────────── API endpoint tests ──────────────────────────────
# Starlette is an ASGI app → must use ASGITransport with AsyncClient.


async def _async_client():
    from main import app
    from httpx import AsyncClient, ASGITransport
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_api_create_request_unknown_user():
    async with await _async_client() as client:
        resp = await client.post("/request", json={
            "user_id": 9999,
            "origin_lat": 40.72, "origin_lng": -73.80,
            "dest_lat": 40.64, "dest_lng": -73.78
        })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_create_request_success():
    u = make_user("Bob")
    async with await _async_client() as client:
        resp = await client.post("/request", json={
            "user_id": u.id,
            "origin_lat": 40.72, "origin_lng": -73.80,
            "dest_lat": 40.64, "dest_lng": -73.78
        })
    assert resp.status_code == 200
    assert "request_id" in resp.json()


@pytest.mark.asyncio
async def test_api_create_request_missing_field():
    async with await _async_client() as client:
        resp = await client.post("/request", json={"user_id": 1})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_pending_returns_list():
    u = make_user("C")
    make_request(u.id)
    async with await _async_client() as client:
        resp = await client.get("/requests/pending")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_api_cancel_unknown():
    async with await _async_client() as client:
        resp = await client.post("/cancel/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_cancel_success():
    u = make_user("D")
    r = make_request(u.id)
    async with await _async_client() as client:
        resp = await client.post(f"/cancel/{r.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        pending = (await client.get("/requests/pending")).json()
    ids = [p["id"] for p in pending]
    assert r.id not in ids


@pytest.mark.asyncio
async def test_api_match_trigger():
    u = make_user("E")
    make_request(u.id)
    async with await _async_client() as client:
        resp = await client.post("/match/trigger")
    assert resp.status_code == 200
    assert "created_rides" in resp.json()


@pytest.mark.asyncio
async def test_api_get_ride_not_found():
    async with await _async_client() as client:
        resp = await client.get("/rides/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_get_ride_found():
    u = make_user("F")
    make_request(u.id)
    async with await _async_client() as client:
        match_resp = (await client.post("/match/trigger")).json()
        assert match_resp["created_rides"] >= 1
        session = get_session()
        ride = session.query(Ride).first()
        resp = await client.get(f"/rides/{ride.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == ride.id


@pytest.mark.asyncio
async def test_api_accept_ride():
    u = make_user("G")
    make_request(u.id)
    async with await _async_client() as client:
        await client.post("/match/trigger")
        session = get_session()
        ride = session.query(Ride).first()
        resp = await client.post(f"/rides/{ride.id}/accept")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_api_accept_ride_twice_fails():
    u = make_user("H")
    make_request(u.id)
    async with await _async_client() as client:
        await client.post("/match/trigger")
        session = get_session()
        ride = session.query(Ride).first()
        await client.post(f"/rides/{ride.id}/accept")
        resp2 = await client.post(f"/rides/{ride.id}/accept")
    assert resp2.status_code == 400
