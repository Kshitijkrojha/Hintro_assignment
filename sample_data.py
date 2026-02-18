from db import init_db, get_session
from models import User, RideRequest
import random


def seed():
    init_db()
    session = get_session()
    # add users
    users = [User(name=f"user{i}") for i in range(1, 21)]
    session.add_all(users)
    session.commit()
    # sample: generate random airport-ish requests around a city center
    center = (40.6413, -73.7781)  # JFK approximate
    for i in range(1, 51):
        u = users[(i - 1) % len(users)]
        # random origin within 10km
        lat = center[0] + (random.random() - 0.5) * 0.18
        lng = center[1] + (random.random() - 0.5) * 0.18
        # destination near airport
        dlat = center[0] + (random.random() - 0.5) * 0.05
        dlng = center[1] + (random.random() - 0.5) * 0.05
        rr = RideRequest(
            user_id=u.id,
            origin_lat=lat,
            origin_lng=lng,
            dest_lat=dlat,
            dest_lng=dlng,
            seats_required=1,
            luggage=random.choice([0, 1]),
            detour_tolerance_km=5.0,
        )
        session.add(rr)
    session.commit()
    print("Seeded sample data")


if __name__ == "__main__":
    seed()
