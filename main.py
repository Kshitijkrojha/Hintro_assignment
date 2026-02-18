from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.routing import Route
from db import init_db, get_session, get_lock
from models import User, RideRequest, Ride
from matching import run_matching
import json


def ensure_db():
    init_db()


async def startup():
    ensure_db()


async def create_request(request: Request):
    payload = await request.json()
    required = ["user_id", "origin_lat", "origin_lng", "dest_lat", "dest_lng"]
    for k in required:
        if k not in payload:
            return JSONResponse({"error": f"missing {k}"}, status_code=400)
    session = get_session()
    user = session.get(User, payload["user_id"])
    if not user:
        return JSONResponse({"error": "user not found"}, status_code=404)
    rr = RideRequest(
        user_id=payload["user_id"],
        origin_lat=payload["origin_lat"],
        origin_lng=payload["origin_lng"],
        dest_lat=payload["dest_lat"],
        dest_lng=payload["dest_lng"],
        seats_required=payload.get("seats_required", 1),
        luggage=payload.get("luggage", 0),
        detour_tolerance_km=payload.get("detour_tolerance_km", 5.0),
    )
    session.add(rr)
    session.commit()
    session.refresh(rr)
    return JSONResponse({"request_id": rr.id})


async def cancel_request(request: Request):
    rid = int(request.path_params["request_id"])
    lock = get_lock("matching")
    with lock:
        session = get_session()
        req = session.get(RideRequest, rid)
        if not req:
            return JSONResponse({"error": "request not found"}, status_code=404)
        req.status = "cancelled"
        session.add(req)
        session.commit()
        return JSONResponse({"status": "cancelled", "request_id": rid})


async def trigger_match(request: Request):
    res = run_matching()
    return JSONResponse(res)


async def get_ride(request: Request):
    ride_id = int(request.path_params["ride_id"])
    session = get_session()
    ride = session.get(Ride, ride_id)
    if not ride:
        return JSONResponse({"error": "ride not found"}, status_code=404)
    # serialize basic ride info
    return JSONResponse({
        "id": ride.id,
        "driver": ride.driver,
        "seats_total": ride.seats_total,
        "occupancy": ride.occupancy,
        "requests": ride.requests,
        "status": ride.status,
    })


async def pending_requests(request: Request):
    session = get_session()
    rows = session.query(RideRequest).filter(RideRequest.status == "pending").all()
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "user_id": r.user_id,
            "origin": [r.origin_lat, r.origin_lng],
            "dest": [r.dest_lat, r.dest_lng],
            "status": r.status,
        })
    return JSONResponse(out)


async def accept_ride(request: Request):
    ride_id = int(request.path_params["ride_id"])
    lock = get_lock("matching")
    with lock:
        session = get_session()
        ride = session.get(Ride, ride_id)
        if not ride:
            return JSONResponse({"error": "ride not found"}, status_code=404)
        if ride.status != "proposed":
            return JSONResponse({"error": "ride cannot be accepted"}, status_code=400)
        ride.status = "active"
        session.add(ride)
        session.commit()
        return JSONResponse({"ride_id": ride.id, "status": ride.status})


routes = [
    Route("/request", create_request, methods=["POST"]),
    Route("/cancel/{request_id}", cancel_request, methods=["POST"]),
    Route("/match/trigger", trigger_match, methods=["POST"]),
    Route("/rides/{ride_id}", get_ride, methods=["GET"]),
    Route("/requests/pending", pending_requests, methods=["GET"]),
    Route("/rides/{ride_id}/accept", accept_ride, methods=["POST"]),
]

app = Starlette(debug=True, routes=routes, on_startup=[startup])
