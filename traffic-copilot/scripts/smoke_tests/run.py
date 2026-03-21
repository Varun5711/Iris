#!/usr/bin/env python3
"""
End-to-end smoke test against a running TrafficCopilot API.

Usage:
    python scripts/smoke_tests/run.py [--api http://localhost:8000]

Runs 8 checks and prints PASS / FAIL for each.
Exits 0 if all pass, 1 if any fail.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

import httpx

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

results: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    icon = PASS if ok else FAIL
    print(f"  [{icon}]  {label}" + (f"  —  {detail}" if detail else ""))
    results.append((label, ok, detail))


async def run(base: str) -> None:
    print(f"\n{'='*55}")
    print("  TrafficCopilot Smoke Tests")
    print(f"  API: {base}")
    print(f"{'='*55}\n")

    async with httpx.AsyncClient(base_url=base, timeout=15.0) as client:

        # ── 1. Health ───────────────────────────────────────────────────
        try:
            r = await client.get("/health")
            check("GET /health → 200", r.status_code == 200, str(r.status_code))
        except Exception as exc:
            check("GET /health → 200", False, str(exc))
            print("\nAPI unreachable. Is `docker compose up` running?\n")
            sys.exit(1)

        # ── 2. Create incident ──────────────────────────────────────────
        incident_id: str = ""
        payload = {
            "severity": "high",
            "description": "Smoke test: multi-vehicle accident",
            "corridor_id": "smoke_test_corridor",
            "lat": 34.0522,
            "lon": -118.2437,
            "reporter_id": "smoke_test",
        }
        try:
            r = await client.post("/incidents", json=payload)
            ok = r.status_code in (200, 201)
            if ok:
                incident_id = r.json().get("id", "")
            check("POST /incidents → 201", ok, f"id={incident_id[:8]}…" if incident_id else str(r.status_code))
        except Exception as exc:
            check("POST /incidents → 201", False, str(exc))

        if not incident_id:
            print("\nCannot continue without an incident. Aborting.\n")
            _print_summary()
            sys.exit(1)

        # ── 3. Push sensor event ────────────────────────────────────────
        sensor_payload = {
            "segment_id": "smoke_seg_001",
            "speed_kmh": 8.0,
            "free_flow_kmh": 90.0,
            "occupancy_pct": 0.95,
            "lat": 34.0522,
            "lon": -118.2437,
            "corridor_id": "smoke_test_corridor",
        }
        try:
            r = await client.post("/ingest/sensor", json=sensor_payload)
            check("POST /ingest/sensor → 202", r.status_code in (200, 202), str(r.status_code))
        except Exception as exc:
            check("POST /ingest/sensor → 202", False, str(exc))

        # ── 4. Fetch incident ───────────────────────────────────────────
        await asyncio.sleep(2)
        try:
            r = await client.get(f"/incidents/{incident_id}")
            ok = r.status_code == 200
            check(f"GET /incidents/{{id}} → 200", ok, str(r.status_code))
        except Exception as exc:
            check(f"GET /incidents/{{id}} → 200", False, str(exc))

        # ── 5. Trigger recommendation generation ────────────────────────
        rec_id: str = ""
        try:
            r = await client.post(f"/recommendations/{incident_id}/generate")
            ok = r.status_code in (200, 201, 202)
            if ok:
                body = r.json()
                rec_id = body.get("id", body.get("recommendation_id", ""))
            check("POST /recommendations/{id}/generate → 2xx", ok, str(r.status_code))
        except Exception as exc:
            check("POST /recommendations/{id}/generate → 2xx", False, str(exc))

        # ── 6. List recommendations ─────────────────────────────────────
        await asyncio.sleep(2)
        try:
            r = await client.get(f"/recommendations/{incident_id}")
            ok = r.status_code == 200
            items = r.json() if ok else []
            if not rec_id and isinstance(items, list) and items:
                rec_id = items[0].get("id", "")
            check("GET /recommendations/{id} → list", ok and isinstance(items, list),
                  f"{len(items)} items" if ok else str(r.status_code))
        except Exception as exc:
            check("GET /recommendations/{id} → list", False, str(exc))

        # ── 7. Approve recommendation ───────────────────────────────────
        if rec_id:
            try:
                r = await client.post(
                    f"/approvals/{rec_id}/approve",
                    json={"officer_id": "smoke_test_officer", "note": "Smoke test approval"},
                )
                check("POST /approvals/{rec_id}/approve → 2xx",
                      r.status_code in (200, 201), str(r.status_code))
            except Exception as exc:
                check("POST /approvals/{rec_id}/approve → 2xx", False, str(exc))
        else:
            check("POST /approvals/{rec_id}/approve → 2xx", False, "no rec_id available")

        # ── 8. Chat Q&A ─────────────────────────────────────────────────
        try:
            r = await client.post(
                f"/chat/{incident_id}",
                json={"question": "How severe is the congestion?", "officer_id": "smoke_test"},
            )
            ok = r.status_code in (200, 201)
            check("POST /chat/{id} → 200", ok, str(r.status_code))
        except Exception as exc:
            check("POST /chat/{id} → 200", False, str(exc))

    _print_summary()


def _print_summary() -> None:
    passed = sum(1 for _, ok, _ in results if ok)
    total  = len(results)
    print(f"\n{'='*55}")
    print(f"  Result: {passed}/{total} checks passed")
    print(f"{'='*55}\n")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(run(args.api.rstrip("/")))
