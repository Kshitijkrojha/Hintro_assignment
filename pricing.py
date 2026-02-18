from math import ceil


def compute_price(distance_km: float, occupancy: int, seats_total: int, demand_factor: float = 1.0) -> float:
    """Simple dynamic pricing:
    price = base + per_km * distance * occupancy_factor * demand_factor
    occupancy_factor rewards shared rides (lower per-person cost), but we apply a small reduction per extra passenger.
    """
    base = 5.0
    per_km = 1.2
    # occupancy discount: more people -> split base, slight per-person reduction
    occ_discount = 1.0 - 0.05 * (occupancy - 1)
    occ_discount = max(0.7, occ_discount)
    raw = (base + per_km * distance_km) * occ_discount * demand_factor
    # per passenger price (we'll round up to cents)
    return round(raw, 2)
