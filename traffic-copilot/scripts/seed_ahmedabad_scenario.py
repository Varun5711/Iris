#!/usr/bin/env python3
"""
seed_ahmedabad_scenario.py
--------------------------
Reads /Users/varunhotani/Downloads/df.csv (Indian city traffic accident data),
filters for Ahmedabad rows, and generates ManualIncidentEvent + SensorSpeedEvent
+ RadioTranscriptEvent JSON files into:
  data/replays/ahmedabad_scenario/

Each JSON file matches the TrafficEvent schema consumed by feed_replay.py
which publishes to Kafka topic traffic.events.raw.

Run from the repo root:
    python scripts/seed_ahmedabad_scenario.py
"""

from __future__ import annotations

import csv
import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CSV_PATH = Path("/Users/varunhotani/Downloads/df.csv")
OUT_DIR = Path(__file__).parent.parent / "data" / "replays" / "ahmedabad_scenario"
CITY_FILTER = "Ahmedabad"

# Ahmedabad real corridors
CORRIDORS = [
    {"id": "AMD-SPRR-01", "name": "SP Ring Road (West)",          "lat": 23.0469, "lon": 72.5211},
    {"id": "AMD-SGH-01",  "name": "SG Highway",                   "lat": 23.0395, "lon": 72.5039},
    {"id": "AMD-CGR-01",  "name": "CG Road",                      "lat": 23.0269, "lon": 72.5855},
    {"id": "AMD-ASH-01",  "name": "Ashram Road",                  "lat": 23.0300, "lon": 72.5800},
    {"id": "AMD-DIN-01",  "name": "Drive-in Road",                "lat": 23.0446, "lon": 72.5280},
    {"id": "AMD-NHW-08",  "name": "NH-48 (Delhi-Mumbai Highway)", "lat": 22.9964, "lon": 72.5800},
]

# Speed params by severity (speed_kmh, free_flow_kmh, occupancy_pct)
SPEED_BY_SEVERITY = {
    "critical": (8.0,  60.0, 95.0),
    "high":     (18.0, 60.0, 85.0),
    "medium":   (30.0, 60.0, 70.0),
    "low":      (45.0, 60.0, 50.0),
}

# Radio transcripts per cause subcategory
RADIO_TRANSCRIPTS = {
    "Uncontrolled":           "Unit 7 to dispatch — major collision at uncontrolled junction, multiple vehicles blocked, injuries reported, request ambulance and traffic police immediately",
    "Others":                 "Dispatch this is unit 4 — road obstruction and collision reported, traffic backed up severely, emergency response needed at this location",
    "Traffic Light Signal":   "Unit 3 reporting accident near traffic light signal intersection, lane fully blocked, ambulance requested, witness confirmed two vehicles involved",
    "Police Controlled":      "Unit 12 to base — crash at police-controlled junction, debris on road, one injury confirmed, requesting backup and medical unit",
    "Flashing Signal/Blinker":"Unit 9 calling dispatch — collision at flashing signal intersection, vehicle damage and injury, recommend closure of approach lane",
    "Stop Sign":              "Dispatch unit 6 here — accident at stop sign location, vehicle impact, minor injuries reported, tow truck and first aid needed",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def derive_severity(persons_killed: float, grievously_injured: float) -> str:
    if persons_killed > 50:
        return "critical"
    if persons_killed > 0:
        return "high"
    if grievously_injured > 0:
        return "medium"
    return "low"


def slugify(text: str) -> str:
    return text.lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")


def make_event_time(base: datetime, offset_seconds: int = 0) -> str:
    return (base + timedelta(seconds=offset_seconds)).isoformat()


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {path.name}")


# ---------------------------------------------------------------------------
# Parse CSV
# ---------------------------------------------------------------------------

def load_ahmedabad_data(csv_path: Path) -> dict[str, dict[str, float]]:
    """
    Returns dict keyed by Cause Subcategory, each value is a dict of
    { outcome_name: count }.
    Only includes rows for CITY_FILTER.
    """
    data: dict[str, dict[str, float]] = {}
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = row["Million Plus Cities"].strip()
            if city != CITY_FILTER:
                continue
            subcat = row["Cause Subcategory"].strip()
            outcome = row["Outcome of Incident"].strip()
            count = float(row["Count"] or 0)
            if subcat not in data:
                data[subcat] = {}
            data[subcat][outcome] = count
    return data


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate_scenario(ahmedabad_data: dict[str, dict[str, float]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Sort subcategories by total accidents descending for file ordering
    subcats_sorted = sorted(
        ahmedabad_data.items(),
        key=lambda kv: kv[1].get("Total number of Accidents", 0),
        reverse=True,
    )

    file_index = 1
    base_time = datetime.now(tz=timezone.utc).replace(microsecond=0)

    for corridor_idx, (subcat, outcomes) in enumerate(subcats_sorted):
        total_accidents = outcomes.get("Total number of Accidents", 0)
        if total_accidents == 0:
            print(f"  skipping {subcat!r} — 0 accidents")
            continue

        persons_killed     = outcomes.get("Persons Killed", 0)
        grievously_injured = outcomes.get("Greviously Injured", 0)  # note CSV spelling
        minor_injury       = outcomes.get("Minor Injury", 0)

        severity    = derive_severity(persons_killed, grievously_injured)
        corridor    = CORRIDORS[corridor_idx % len(CORRIDORS)]
        slug        = slugify(subcat)
        incident_id = str(uuid.uuid4())
        t0          = base_time + timedelta(minutes=corridor_idx * 3)  # stagger each incident

        speed_kmh, free_flow_kmh, occupancy_pct = SPEED_BY_SEVERITY[severity]
        radio_transcript = RADIO_TRANSCRIPTS.get(
            subcat,
            f"Unit to dispatch — traffic incident at {corridor['name']}, {subcat} cause, response requested",
        )

        desc = (
            f"Traffic Control incident — {subcat}. "
            f"{int(total_accidents)} recorded accidents, {int(persons_killed)} fatalities, "
            f"{int(grievously_injured)} grievously injured on {corridor['name']} ({corridor['id']}). "
            f"Immediate traffic management required."
        )

        print(f"\n[{severity.upper()}] {subcat} → {corridor['id']} ({corridor['name']})")

        # ---- 1. ManualIncidentEvent ----------------------------------------
        manual = {
            "event_id":    str(uuid.uuid4()),
            "source":      "manual",
            "event_time":  make_event_time(t0, 0),
            "corridor_id": corridor["id"],
            "lat":         corridor["lat"],
            "lon":         corridor["lon"],
            "payload": {
                "city":               CITY_FILTER,
                "cause_category":     "Traffic Control",
                "cause_subcategory":  subcat,
                "total_accidents":    int(total_accidents),
                "persons_killed":     int(persons_killed),
                "grievously_injured": int(grievously_injured),
                "minor_injury":       int(minor_injury),
                "incident_id":        incident_id,
            },
            "severity":    severity,
            "description": desc,
            "reporter_id": "csv_import_ahmedabad",
        }
        write_json(out_dir / f"{file_index:03d}_manual_{slug}.json", manual)
        file_index += 1

        # ---- 2. SensorSpeedEvent (primary segment) -------------------------
        sensor1 = {
            "event_id":    str(uuid.uuid4()),
            "source":      "sensor",
            "event_time":  make_event_time(t0, 5),
            "corridor_id": corridor["id"],
            "lat":         corridor["lat"],
            "lon":         corridor["lon"],
            "payload":     {"incident_id": incident_id},
            "segment_id":  f"AMD-SEG-{corridor['id']}-001",
            "speed_kmh":   speed_kmh,
            "free_flow_kmh": free_flow_kmh,
            "occupancy_pct": occupancy_pct,
        }
        write_json(out_dir / f"{file_index:03d}_sensor_{slug}.json", sensor1)
        file_index += 1

        # ---- 3. RadioTranscriptEvent ---------------------------------------
        radio = {
            "event_id":    str(uuid.uuid4()),
            "source":      "radio",
            "event_time":  make_event_time(t0, 10),
            "corridor_id": corridor["id"],
            "lat":         corridor["lat"],
            "lon":         corridor["lon"],
            "payload":     {"incident_id": incident_id},
            "transcript":  radio_transcript,
            "unit_id":     f"AMD-UNIT-{(corridor_idx + 1):02d}",
        }
        write_json(out_dir / f"{file_index:03d}_radio_{slug}.json", radio)
        file_index += 1

        # ---- 4. SensorSpeedEvent (upstream segment, slightly different loc) -
        sensor2 = {
            "event_id":    str(uuid.uuid4()),
            "source":      "sensor",
            "event_time":  make_event_time(t0, 15),
            "corridor_id": corridor["id"],
            "lat":         round(corridor["lat"] + 0.002, 6),
            "lon":         round(corridor["lon"] + 0.002, 6),
            "payload":     {"incident_id": incident_id},
            "segment_id":  f"AMD-SEG-{corridor['id']}-002",
            "speed_kmh":   round(speed_kmh * 1.5, 1),   # upstream slightly faster
            "free_flow_kmh": free_flow_kmh,
            "occupancy_pct": round(occupancy_pct * 0.85, 1),
        }
        write_json(out_dir / f"{file_index:03d}_sensor2_{slug}.json", sensor2)
        file_index += 1

    total = file_index - 1
    print(f"\n✅  Generated {total} scenario files in {out_dir}")
    print(f"   Update REPLAY_SCENARIO_DIR in .env to:\n   {out_dir}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Loading CSV from {CSV_PATH} ...")
    ahmedabad_data = load_ahmedabad_data(CSV_PATH)
    print(f"Found {len(ahmedabad_data)} cause subcategories for {CITY_FILTER}:")
    for subcat, outcomes in ahmedabad_data.items():
        print(f"  {subcat}: {int(outcomes.get('Total number of Accidents', 0))} accidents")

    generate_scenario(ahmedabad_data, OUT_DIR)
