#!/usr/bin/env python3
"""
End-to-end smoke test against a running TrafficCopilot API.

Usage:
    python scripts/smoke_tests/run.py [--api http://localhost:8000]

Runs 9 checks in the correct order and prints PASS / FAIL for each.
Exits 0 if all pass, 1 if any fail.

Correct route map (matches the actual FastAPI routers):
  POST /incidents/                              → create incident
  POST /incidents/{id}/events?source=sensor     → push sensor event
  POST /incidents/{id}/events?source=camera     → push camera event
  GET  /incidents/{id}                          → get incident snapshot
  GET  /recommendations/{incident_id}           → list recommendations (worker populates)
  POST /recommendations/{rec_id}/approve        → approve recommendation
  GET  /alerts/{incident_id}                    → list alert drafts
  POST /alerts/{alert_id}/publish               → publish approved alert
  POST /chat/                                   → ask a question
"""
from __future__ import annotations
import argparse, asyncio, sys
from typing import Any
import httpx

G = "\033[32m"; R = "\033[31m"; E = "\033[0m"
results: list[tuple[str, bool, str]] = []

def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}]  {label}" + (f"  —  {detail}" if detail else ""))
    results.append((label, ok, detail))

async def run(base: str) -> None:
    print(f"\n{'='*55}\n  TrafficCopilot Smoke Tests\n  API: {base}\n{'='*55}\n")

    async with httpx.AsyncClient(base_url=base, timeout=15.0) as c:

        # 1. Health
        try:
            r = await c.get("/health")
            check("GET /health → 200", r.status_code == 200)
        except Exception as exc:
            check("GET /health → 200", False, str(exc))
            print("\nAPI unreachable. Run: docker compose up -d\n"); sys.exit(1)

        # 2. Create incident
        iid = ""
        r = await c.post("/incidents/", json={
            "severity": "high",
            "description": "Smoke test incident",
            "corridor_id": "smoke_test",
            "lat": 34.0522, "lon": -118.2437,
            "reporter_id": "smoke_officer",
        })
        ok = r.status_code in (200, 201)
        if ok:
            iid = r.json().get("id", "")
        check("POST /incidents/ → 201", ok, f"id={iid[:8]}…" if iid else str(r.status_code))
        if not iid:
            print("No incident_id — aborting"); _summary(); sys.exit(1)

        # 3. Push sensor event
        r = await c.post(f"/incidents/{iid}/events", params={"source": "sensor"}, json={
            "segment_id": "smoke_seg_001",
            "speed_kmh": 8.0, "free_flow_kmh": 90.0, "occupancy_pct": 0.94,
            "lat": 34.0522, "lon": -118.2437, "corridor_id": "smoke_test",
        })
        check("POST /incidents/{id}/events?source=sensor → 202", r.status_code in (200, 202), str(r.status_code))

        # 4. Push camera event
        r = await c.post(f"/incidents/{iid}/events", params={"source": "camera"}, json={
            "camera_id": "smoke_cam_001",
            "lane_blocked": True, "vehicle_count": 40,
            "incident_detected": True, "confidence": 0.9,
            "lat": 34.0522, "lon": -118.2437,
        })
        check("POST /incidents/{id}/events?source=camera → 202", r.status_code in (200, 202), str(r.status_code))

        # 5. Get incident
        r = await c.get(f"/incidents/{iid}")
        check("GET /incidents/{id} → 200", r.status_code == 200, str(r.status_code))

        # 6. Wait for worker, then get recommendations
        print("  wait  8s for Kafka workers…")
        await asyncio.sleep(8)
        r = await c.get(f"/recommendations/{iid}")
        ok = r.status_code == 200 and isinstance(r.json(), list)
        recs = r.json() if ok else []
        rec_id = recs[0]["id"] if recs else ""
        check("GET /recommendations/{incident_id} → list", ok, f"{len(recs)} recs")

        # 7. Approve recommendation
        if rec_id:
            r = await c.post(f"/recommendations/{rec_id}/approve", json={
                "officer_id": "smoke_officer", "note": "smoke test approval"
            })
            check("POST /recommendations/{rec_id}/approve → 200", r.status_code == 200, str(r.status_code))
        else:
            check("POST /recommendations/{rec_id}/approve → 200", False, "no recommendation yet (worker may be slow)")

        # 8. List alerts + publish one
        r = await c.get(f"/alerts/{iid}")
        alerts = r.json() if r.status_code == 200 else []
        alert_id = alerts[0]["id"] if alerts else ""
        check("GET /alerts/{incident_id} → list", r.status_code == 200, f"{len(alerts)} alerts")
        if alert_id:
            r = await c.post(f"/alerts/{alert_id}/publish", json={"officer_id": "smoke_officer"})
            check("POST /alerts/{alert_id}/publish → 200", r.status_code == 200, str(r.status_code))
        else:
            check("POST /alerts/{alert_id}/publish → 200", False, "no alert to publish")

        # 9. Chat Q&A
        r = await c.post("/chat/", json={
            "incident_id": iid,
            "question": "How severe is the current congestion?",
            "officer_id": "smoke_officer",
        })
        check("POST /chat/ → 200", r.status_code == 200, str(r.status_code))

    _summary()

def _summary() -> None:
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{'='*55}\n  Result: {passed}/{len(results)} passed\n{'='*55}\n")
    if passed < len(results):
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(run(args.api.rstrip("/")))
