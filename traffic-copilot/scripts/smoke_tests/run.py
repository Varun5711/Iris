#!/usr/bin/env python3
"""Run smoke tests against the running API."""
import asyncio
import httpx
import time
import sys

BASE_URL = "http://localhost:8000"

async def test_health():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/health")
        assert r.status_code == 200
        print("✅ Health check passed")

async def test_create_incident():
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/incidents", json={
            "severity": "high",
            "description": "Test incident: multi-vehicle collision",
            "lat": 40.758,
            "lon": -73.985,
            "corridor_id": "TEST-001",
            "reporter_id": "smoke_test"
        })
        assert r.status_code == 201
        data = r.json()
        incident_id = data["id"]
        print(f"✅ Incident created: {incident_id}")
        return incident_id

async def test_get_recommendations(incident_id: str):
    # Wait for processor to run
    await asyncio.sleep(5)
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/recommendations/{incident_id}")
        assert r.status_code == 200
        recs = r.json()
        print(f"✅ Recommendations fetched: {len(recs)} found")
        return recs

async def main():
    print("🚀 Running TrafficCopilot smoke tests...")
    start = time.time()
    await test_health()
    incident_id = await test_create_incident()
    recs = await test_get_recommendations(incident_id)
    elapsed = time.time() - start
    print(f"\n✅ All smoke tests passed in {elapsed:.1f}s")
    if recs:
        first_rec_time = (time.time() - start)
        print(f"⏱  Time to first recommendation: {first_rec_time:.1f}s (target: < 30s)")

if __name__ == "__main__":
    asyncio.run(main())
