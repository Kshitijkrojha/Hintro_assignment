"""initial_schema

Revision ID: 199d3cfa0210
Revises: 
Create Date: 2026-02-18 22:34:49.040219

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '199d3cfa0210'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial tables: user, riderequest, ride."""
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "riderequest",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("origin_lat", sa.Float(), nullable=False),
        sa.Column("origin_lng", sa.Float(), nullable=False),
        sa.Column("dest_lat", sa.Float(), nullable=False),
        sa.Column("dest_lng", sa.Float(), nullable=False),
        sa.Column("seats_required", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("luggage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("detour_tolerance_km", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_riderequest_status", "riderequest", ["status"])
    op.create_index("ix_riderequest_user_id", "riderequest", ["user_id"])
    op.create_index("ix_riderequest_created_at", "riderequest", ["created_at"])
    op.create_table(
        "ride",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("driver", sa.String(), nullable=True),
        sa.Column("seats_total", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("luggage_capacity", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("occupancy", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("luggage_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requests", sa.String(), nullable=True),
        sa.Column("origin_lat", sa.Float(), nullable=True),
        sa.Column("origin_lng", sa.Float(), nullable=True),
        sa.Column("dest_lat", sa.Float(), nullable=True),
        sa.Column("dest_lng", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="proposed"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ride_status", "ride", ["status"])


def downgrade() -> None:
    """Drop all initial tables."""
    op.drop_index("ix_ride_status", table_name="ride")
    op.drop_table("ride")
    op.drop_index("ix_riderequest_created_at", table_name="riderequest")
    op.drop_index("ix_riderequest_user_id", table_name="riderequest")
    op.drop_index("ix_riderequest_status", table_name="riderequest")
    op.drop_table("riderequest")
    op.drop_table("user")
