"""Migration / setup helper
This script initializes the database schema used by the prototype.
Run: python migrate.py
"""
from db import init_db


def main():
    init_db()
    print("Database initialized (ridepool.db)")


if __name__ == "__main__":
    main()
