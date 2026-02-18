import asyncio
import httpx
import asyncio
import httpx
import pytest
import importlib.util
import os
import sys

# ensure project root in sys.path so internal imports in sample_data work
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# load sample_data module by path to avoid import issues during pytest collection
spec = importlib.util.spec_from_file_location("sample_data", os.path.join(os.path.dirname(__file__), "..", "sample_data.py"))
sample_data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sample_data)
seed = sample_data.seed

from main import app
@pytest.mark.asyncio
async def test_concurrent_requests_and_matching():
    # Ensure DB seeded
    seed()
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        # fetch pending requests
        pending = await client.get(f"/requests/pending")
        assert pending.status_code == 200
        # trigger multiple match calls concurrently
        tasks = []
        for _ in range(5):
            tasks.append(client.post(f"/match/trigger"))
        res = await asyncio.gather(*tasks)
        # ensure at least one triggered successfully
        assert any(r.status_code == 200 for r in res)
