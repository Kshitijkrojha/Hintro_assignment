"""Export OpenAPI schema to a file without running the server.
Run: python export_openapi.py
This will write openapi.json in the project root.
"""
import json
from main import app


def main():
    spec = app.openapi()
    with open("openapi.json", "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
    print("Wrote openapi.json")


if __name__ == "__main__":
    main()
