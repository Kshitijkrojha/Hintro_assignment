"""Simple concurrency demo that calls /match/trigger concurrently against the ASGI app.
This runs in-process and doesn't require the server to be started separately.
Run: python concurrency_demo.py
"""
import asyncio
from main import app
import httpx


async def run():
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        tasks = [client.post("/match/trigger") for _ in range(10)]
        res = await asyncio.gather(*tasks)
        for r in res:
            print(r.status_code, r.json())


if __name__ == "__main__":
    asyncio.run(run())
