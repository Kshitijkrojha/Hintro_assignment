from typing import List, Tuple
from models import RideRequest, Ride
from db import get_session, get_lock
from math import radians, sin, cos, sqrt, atan2
from pricing import compute_price
import time


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    rlat1 = radians(lat1)
    rlat2 = radians(lat2)
    a_ = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a_), sqrt(1 - a_))
    return R * c


def approximate_detour_if_added(existing: List[RideRequest], candidate: RideRequest) -> float:
    # approximate extra distance experienced by candidate when sharing with 'existing'
    # naive: path = candidate.origin -> closest existing origin -> existing dests -> candidate.dest
    if not existing:
        return 0.0
    # pick one existing request as representative (the earliest)
    rep = existing[0]
    d_direct = haversine_km((candidate.origin_lat, candidate.origin_lng), (candidate.dest_lat, candidate.dest_lng))
    d_via = (
        haversine_km((candidate.origin_lat, candidate.origin_lng), (rep.origin_lat, rep.origin_lng))
        + haversine_km((rep.origin_lat, rep.origin_lng), (rep.dest_lat, rep.dest_lng))
        + haversine_km((rep.dest_lat, rep.dest_lng), (candidate.dest_lat, candidate.dest_lng))
    )
    return max(0.0, d_via - d_direct)


def run_matching(max_seats=4, max_luggage=4):
    """Greedy matcher: group pending requests into rides respecting seat/luggage and detour.
    This function takes a DB lock to avoid races with cancellations.
    """
    lock = get_lock("matching")
    acquired = lock.acquire(timeout=5)
    if not acquired:
        return {"status": "locked"}
    try:
        session = get_session()
        pending = session.query(RideRequest).filter(RideRequest.status == "pending").order_by(RideRequest.created_at).all()
        groups = []
        used = set()
        for r in pending:
            if r.id in used:
                continue
            group = [r]
            seats = r.seats_required
            luggage = r.luggage
            # try to add more
            for other in pending:
                if other.id == r.id or other.id in used:
                    continue
                if seats + other.seats_required > max_seats:
                    continue
                if luggage + other.luggage > max_luggage:
                    continue
                # check detour for other when added to group
                extra = approximate_detour_if_added(group, other)
                if extra <= other.detour_tolerance_km:
                    group.append(other)
                    seats += other.seats_required
                    luggage += other.luggage
            # if group size >1 create a proposed Ride
            if len(group) >= 1:
                # create ride summarizing group
                origins = [(g.origin_lat, g.origin_lng) for g in group]
                dests = [(g.dest_lat, g.dest_lng) for g in group]
                # naive route endpoints (min origin lat/lng as start, max dest lat/lng as end)
                origin = origins[0]
                dest = dests[0]
                # compute aggregate distance: sum of direct distances
                total_dist = sum(haversine_km((g.origin_lat, g.origin_lng), (g.dest_lat, g.dest_lng)) for g in group)
                ride = Ride(
                    driver=None,
                    seats_total=max_seats,
                    luggage_capacity=max_luggage,
                    occupancy=len(group),
                    luggage_used=luggage,
                    requests=",".join(str(g.id) for g in group),
                    origin_lat=origin[0],
                    origin_lng=origin[1],
                    dest_lat=dest[0],
                    dest_lng=dest[1],
                    status="proposed",
                )
                session.add(ride)
                session.commit()
                session.refresh(ride)
                # mark requests as matched
                for g in group:
                    g.status = "matched"
                    session.add(g)
                session.commit()
                # compute price per passenger and store in ride.driver temporarily
                price = compute_price(total_dist, occupancy=ride.occupancy, seats_total=ride.seats_total, demand_factor=1.0)
                ride.driver = f"price_per_passenger={price}"
                session.add(ride)
                session.commit()
                groups.append((ride, group))
                for g in group:
                    used.add(g.id)
        return {"created_rides": len(groups)}
    finally:
        lock.release()
