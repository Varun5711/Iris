#!/usr/bin/env python3
"""
Replay a traffic incident scenario against the live API.

Usage:
    python scripts/replay_feeds/run.py [--scenario scenario_1] \
        [--api http://localhost:8000] [--speed 10.0] [--dry-run]

Protocol:
  - First event with type="manual" → POST /incidents/ → saves incident_id
  - All subsequent events          → POST /incidents/{incident_id}/events?source={type}
"""
from __future__ import annotations
import argparse, asyncio, json, sys
from pathlib import Path
import httpx

def load_events(scenario_dir: Path) -> list[dict]:
    f = scenario_dir / "events.jsonl"
    if not f.exists():
        sys.exit(f"ERROR: {f} not found")
    events = []
    for i, line in enumerate(f.read_text().splitlines(), 1):
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  WARN  line {i} skipped: {e}", file=sys.stderr)
    return events

async def run(scenario_dir: Path, base: str, speed: float, dry_run: bool) -> None:
    events = load_events(scenario_dir)
    print(f"\nLoaded {len(events)} events  api={base}  speed={speed}x  dry_run={dry_run}\n")

    incident_id: str | None = None
    prev_offset = 0.0

    async with httpx.AsyncClient(base_url=base, timeout=15.0) as client:
        for i, ev in enumerate(events, 1):
            offset = float(ev.get("offset_seconds", 0))
            delay  = max(0.0, (offset - prev_offset) / speed)
            prev_offset = offset
            if delay > 0:
                print(f"  wait  {delay:.1f}s")
                if not dry_run:
                    await asyncio.sleep(delay)

            etype   = ev["type"]
            payload = ev.get("payload", {})
            print(f"[{i:02d}/{len(events)}] T+{offset:.0f}s  type={etype}", end="  ")

            if dry_run:
                print("DRY")
                continue

            if etype == "manual":
                # First manual event creates the incident
                r = await client.post("/incidents/", json=payload)
                if r.status_code in (200, 201):
                    incident_id = r.json().get("id")
                    print(f"OK  id={incident_id[:8]}…")
                else:
                    print(f"FAIL {r.status_code}: {r.text[:120]}")
                    return
            else:
                if not incident_id:
                    print("SKIP (no incident_id yet)")
                    continue
                r = await client.post(
                    f"/incidents/{incident_id}/events",
                    params={"source": etype},
                    json=payload,
                )
                icon = "OK  " if r.status_code in (200, 202) else "FAIL"
                print(f"{icon} {r.status_code}")
                if r.status_code not in (200, 202):
                    print(f"       {r.text[:120]}")

    print(f"\nDone.  incident_id={incident_id}")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="scenario_1")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--speed", type=float, default=10.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent.parent
    asyncio.run(run(repo / "data" / "replays" / args.scenario, args.api.rstrip("/"), args.speed, args.dry_run))

if __name__ == "__main__":
    main()
