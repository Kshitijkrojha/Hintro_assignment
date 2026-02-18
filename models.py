from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class RideRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    origin_lat: float
    origin_lng: float
    dest_lat: float
    dest_lng: float
    seats_required: int = 1
    luggage: int = 0
    detour_tolerance_km: float = 5.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="pending", index=True)  # pending, matched, cancelled


class Ride(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    driver: Optional[str] = None
    seats_total: int = 4
    luggage_capacity: int = 4
    occupancy: int = 0
    luggage_used: int = 0
    requests: Optional[str] = None  # comma-separated request ids for simplicity
    origin_lat: Optional[float]
    origin_lng: Optional[float]
    dest_lat: Optional[float]
    dest_lng: Optional[float]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="proposed")  # proposed, active, completed, cancelled
