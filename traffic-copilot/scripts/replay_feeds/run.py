#!/usr/bin/env python3
"""
Replay a traffic incident scenario by posting events to the ingest API.

Usage:
    python scripts/replay_feeds/run.py [--scenario scenario_1] \
        [--api http://localhost:8000] [--speed 1.0] [--dry-run]

Reads data/replays/{scenario}/events.jsonl — one JSON event per line.
Each line: {"type": "sensor"|"camera"|"radio"|"manual", "offset_seconds": N, "payload": {...}}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

ENDPOINT_MAP = {
    "sensor": "/ingest/sensor",
    "camera": "/ingest/camera",
    "radio":  "/ingest/radio",
    "manual": "/incidents",
}


def load_events(scenario_dir: Path) -> list[dict]:
    events_file = scenario_dir / "events.jsonl"
    if not events_file.exists():
        print(f"ERROR: {events_file} not found", file=sys.stderr)
        sys.exit(1)

    events = []
    with open(events_file) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(f"WARNING: skipping line {i} — invalid JSON: {exc}", file=sys.stderr)
    return events


async def post_event(client: httpx.AsyncClient, base_url: str, event: dict, dry_run: bool) -> bool:
    event_type = event.get("type")
    payload = event.get("payload", {})
    endpoint = ENDPOINT_MAP.get(event_type)

    if endpoint is None:
        print(f"  SKIP  unknown type={event_type!r}")
        return True

    url = f"{base_url}{endpoint}"

    if dry_run:
        print(f"  DRY   POST {url}  keys={list(payload.keys())}")
        return True

    try:
        resp = await client.post(url, json=payload, timeout=10.0)
        ok = resp.status_code < 300
        icon = "OK  " if ok else "FAIL"
        print(f"  {icon}  POST {url} → {resp.status_code}")
        if not ok:
            print(f"        {resp.text[:200]}")
        return ok
    except httpx.RequestError as exc:
        print(f"  ERR   POST {url} → {exc}")
        return False


async def run(scenario_dir: Path, base_url: str, speed: float, dry_run: bool) -> None:
    events = load_events(scenario_dir)
    print(f"\nLoaded {len(events)} events from {scenario_dir}")
    print(f"API: {base_url}  speed: {speed}x  dry_run: {dry_run}\n")

    async with httpx.AsyncClient() as client:
        prev_offset = 0.0
        for i, event in enumerate(events, 1):
            offset = float(event.get("offset_seconds", 0))
            delay = max(0.0, (offset - prev_offset) / speed)
            prev_offset = offset

            if delay > 0:
                print(f"  WAIT  {delay:.1f}s  (scenario T+{offset:.0f}s)")
                await asyncio.sleep(delay)

            print(f"[{i:02d}/{len(events)}] T+{offset:.0f}s  type={event.get('type')}")
            await post_event(client, base_url, event, dry_run)

    print("\nReplay complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a traffic scenario against the live API")
    parser.add_argument("--scenario", default="scenario_1", help="Folder name under data/replays/")
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--speed", type=float, default=10.0,
                        help="Playback speed multiplier (default 10x for quick demo)")
    parser.add_argument("--dry-run", action="store_true", help="Print requests without sending")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    scenario_dir = repo_root / "data" / "replays" / args.scenario

    asyncio.run(run(scenario_dir, args.api.rstrip("/"), args.speed, args.dry_run))


if __name__ == "__main__":
    main()
