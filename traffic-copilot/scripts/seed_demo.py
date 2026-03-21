"""
Seed demo data — creates 6 Ahmedabad incidents with full recommendations,
signal actions, diversion plans, and alert drafts directly in Postgres.
No Groq / LLM calls needed.

Usage:
    cd /Users/varunhotani/Desktop/proj/traffic-copilot
    PYTHONPATH=apps/api python3 scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://tc:tc_secret@localhost:5432/trafficcopilot")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GROQ_API_KEY", "dummy")
os.environ.setdefault("GROQ_MODEL", "llama-3.1-8b-instant")
os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
os.environ.setdefault("PROMPTS_DIR", "/Users/varunhotani/Desktop/proj/traffic-copilot/prompts")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

CORRIDORS = [
    {
        "corridor_id": "AMD-SPRR-01",
        "name": "SP Ring Road (West)",
        "lat": 23.0607, "lon": 72.5169,
        "osm_u": 992658057, "osm_v": 10216722860,
        "severity": "critical",
        "description": (
            "Multi-vehicle pile-up on SP Ring Road near Bopal Circle. "
            "Sunny/Clear conditions — 1185 recorded accidents on this stretch. "
            "Heavy vehicle involvement, 2 lanes blocked."
        ),
        "signal_actions": [
            {
                "intersection_id": "AMD-SPRR-01-JCT-BOPAL",
                "action": "Extend green phase by 20s on NH-48 approach; hold pedestrian phase",
                "expected_impact": "Reduces queue backup by ~35% within 10 min",
                "confidence": 0.85,
            },
            {
                "intersection_id": "AMD-SPRR-01-JCT-SARKHEJ",
                "action": "Switch to manual control; prioritise westbound exit from Ring Road",
                "expected_impact": "Clears cross-junction overflow in ~8 min",
                "confidence": 0.80,
            },
        ],
        "diversion": {
            "route_description": (
                "Divert NH-48 northbound traffic via Sarkhej–Gandhinagar Highway (SH-71) → "
                "Science City Road → rejoin SP Ring Road at Thaltej. "
                "Estimated extra travel time: 12 min. Avoid Bopal underpass entirely."
            ),
            "estimated_extra_minutes": 12.0,
            "traffic_redistribution_pct": 40.0,
            "confidence": 0.82,
            "waypoints": [
                {"name": "Incident — Bopal Circle", "lat": 23.0607, "lng": 72.5169},
                {"name": "Sarkhej Toll", "lat": 23.0481, "lng": 72.5053},
                {"name": "SH-71 Junction", "lat": 23.0550, "lng": 72.5320},
                {"name": "Science City Rd", "lat": 23.0630, "lng": 72.5450},
                {"name": "Thaltej Re-entry", "lat": 23.0700, "lng": 72.5200},
            ],
        },
        "alerts": [
            ("vms", "PILE-UP BOPAL CIRCLE. USE SH-71 VIA SARKHEJ."),
            ("radio", "Attention drivers: multi-vehicle accident on SP Ring Road near Bopal Circle. Please divert via Sarkhej-Gandhinagar Highway. Expect 12 minute delay."),
            ("social", "TRAFFIC ALERT: Accident on SP Ring Road (Bopal Circle). Divert via SH-71. 2 lanes blocked. #AhmedabadTraffic"),
        ],
        "narrative": (
            "Critical incident on AMD-SPRR-01 (SP Ring Road West) at Bopal Circle. "
            "Multi-vehicle pile-up in sunny/clear conditions — a historically high-risk stretch "
            "with 1,185 recorded accidents. Signal retiming at Bopal and Sarkhej junctions "
            "recommended immediately. Diversion via SH-71 will redistribute ~40% of traffic. "
            "Overall confidence: 0.85 based on sensor detection, historical pattern match, and SOP-2."
        ),
        "confidence": 0.85,
        "evidence_refs": ["SOP-2", "osm_way=AMD-SPRR-01", "historical_pattern:sunny_clear"],
    },
    {
        "corridor_id": "AMD-SGH-01",
        "name": "SG Highway",
        "lat": 23.0469, "lon": 72.5203,
        "osm_u": 486139732, "osm_v": 486139740,
        "severity": "critical",
        "description": (
            "Overturned truck blocking SG Highway near Pakwan Cross Roads. "
            "Over-speeding cause — 1149 accident records on this corridor. "
            "Emergency services on scene, right lane closed."
        ),
        "signal_actions": [
            {
                "intersection_id": "AMD-SGH-01-PAKWAN",
                "action": "Activate pre-timed congestion plan C-3; extend green by 25s for SB flow",
                "expected_impact": "Prevents queue spilling onto Pakwan flyover (~20% reduction)",
                "confidence": 0.88,
            },
            {
                "intersection_id": "AMD-SGH-01-JUDGES",
                "action": "Hold right-turn phase for SB → Judges Bungalow Road; reroute to ISKCON",
                "expected_impact": "Reduces conflict points at Pakwan by ~30%",
                "confidence": 0.75,
            },
        ],
        "diversion": {
            "route_description": (
                "Northbound SG Highway: exit at Judges Bungalow Road → ISKCON Cross Road → "
                "Sindhu Bhavan Road → rejoin SG Highway at Shilaj. "
                "Southbound: use Ambli–Bopal Road as parallel route."
            ),
            "estimated_extra_minutes": 8.0,
            "traffic_redistribution_pct": 35.0,
            "confidence": 0.87,
            "waypoints": [
                {"name": "Incident — Pakwan Cross Roads", "lat": 23.0469, "lng": 72.5203},
                {"name": "Judges Bungalow Rd Exit", "lat": 23.0530, "lng": 72.5160},
                {"name": "ISKCON Cross Road", "lat": 23.0590, "lng": 72.5090},
                {"name": "Sindhu Bhavan Rd", "lat": 23.0650, "lng": 72.5050},
                {"name": "Shilaj Re-entry", "lat": 23.0720, "lng": 72.5100},
            ],
        },
        "alerts": [
            ("vms", "TRUCK DOWN SG HWY/PAKWAN. DIVERT VIA JUDGES BUNGALOW RD."),
            ("radio", "SG Highway blocked near Pakwan Cross Roads — overturned truck. Use Judges Bungalow Road or Ambli-Bopal Road as alternate. 8 min extra travel time."),
            ("social", "SG Highway blocked at Pakwan! Overturned truck. Alternate: Judges Bungalow Rd → ISKCON → Sindhu Bhavan Rd. #AhmedabadTraffic"),
        ],
        "narrative": (
            "Critical incident on AMD-SGH-01 (SG Highway) at Pakwan Cross Roads. "
            "Overturned truck — over-speeding flagged as cause. Historical record shows 1,149 "
            "over-speed incidents on this stretch. Signal plan C-3 at Pakwan activated. "
            "Diversion via Judges Bungalow Road redistributes ~35% of northbound flow. "
            "Confidence 0.87 — sensor + camera + historical pattern alignment."
        ),
        "confidence": 0.87,
        "evidence_refs": ["SOP-1", "SOP-3", "osm_way=AMD-SGH-01", "historical_pattern:over_speed"],
    },
    {
        "corridor_id": "AMD-CGR-01",
        "name": "CG Road",
        "lat": 23.0269, "lon": 72.5855,
        "osm_u": 172932072, "osm_v": 186029622,
        "severity": "critical",
        "description": (
            "Pedestrian fatality at CG Road / Swastik Cross Roads intersection. "
            "Straight road accident — 1074 recorded accidents, 303 fatalities. "
            "Traffic halted for 300m in both directions."
        ),
        "signal_actions": [
            {
                "intersection_id": "AMD-CGR-01-SWASTIK",
                "action": "Extend pedestrian phase by 15s; add leading pedestrian interval (LPI) of 7s",
                "expected_impact": "Reduces pedestrian-vehicle conflicts by ~50%",
                "confidence": 0.90,
            },
            {
                "intersection_id": "AMD-CGR-01-NAVRANGPURA",
                "action": "Reduce green phase on CG Road NB by 20s; prioritise cross-street evacuation",
                "expected_impact": "Clears emergency vehicle path within 5 min",
                "confidence": 0.82,
            },
        ],
        "diversion": {
            "route_description": (
                "Both directions: divert via Navrangpura → C.U. Shah College Road → "
                "Usmanpura Link Road. Avoid CG Road between Swastik and "
                "Income Tax Cross Road entirely until cleared."
            ),
            "estimated_extra_minutes": 6.0,
            "traffic_redistribution_pct": 50.0,
            "confidence": 0.88,
            "waypoints": [
                {"name": "Incident — Swastik Cross Roads", "lat": 23.0269, "lng": 72.5855},
                {"name": "Navrangpura Diversion", "lat": 23.0310, "lng": 72.5810},
                {"name": "C.U. Shah College Rd", "lat": 23.0350, "lng": 72.5760},
                {"name": "Usmanpura Link", "lat": 23.0390, "lng": 72.5820},
                {"name": "Income Tax Re-entry", "lat": 23.0420, "lng": 72.5870},
            ],
        },
        "alerts": [
            ("vms", "FATAL ACCIDENT SWASTIK X-RD. CG RD CLOSED. USE NAVRANGPURA."),
            ("radio", "CG Road closed at Swastik Cross Roads following a serious pedestrian incident. Please use Navrangpura or C.U. Shah College Road as alternate routes."),
            ("social", "CG Road/Swastik closed — serious incident. AVOID area. Use Navrangpura → C.U. Shah College Rd → Usmanpura. #AhmedabadTraffic #CriticalAlert"),
        ],
        "narrative": (
            "Critical incident on AMD-CGR-01 (CG Road) at Swastik Cross Roads. "
            "Pedestrian fatality — straight road accident pattern. Historical record: 303 fatalities "
            "on this stretch. LPI signal phase added at Swastik; full diversion activated. "
            "50% traffic redistribution via Navrangpura. Confidence 0.88."
        ),
        "confidence": 0.88,
        "evidence_refs": ["SOP-2", "SOP-4", "osm_way=AMD-CGR-01", "historical_pattern:pedestrian"],
    },
    {
        "corridor_id": "AMD-ASH-01",
        "name": "Ashram Road",
        "lat": 23.0300, "lon": 72.5800,
        "osm_u": 287543210, "osm_v": 287543220,
        "severity": "high",
        "description": (
            "Two-wheeler collision chain at Ashram Road / Income Tax Cross Roads. "
            "562 recorded two-wheeler accidents on this corridor, 146 fatalities. "
            "Centre lane blocked; slow-moving traffic for 500m."
        ),
        "signal_actions": [
            {
                "intersection_id": "AMD-ASH-01-INCOME-TAX",
                "action": "Activate two-wheeler signal phase (TW-phase) — 5s head start before motor vehicles",
                "expected_impact": "Reduces two-wheeler conflict casualties by ~40%",
                "confidence": 0.83,
            },
        ],
        "diversion": {
            "route_description": (
                "Northbound Ashram Road: divert at Ellis Bridge → Relief Road → Nehru Bridge → "
                "rejoin Ashram Road at Gandhi Bridge. "
                "Southbound: use Khanpur Road as parallel route."
            ),
            "estimated_extra_minutes": 7.0,
            "traffic_redistribution_pct": 30.0,
            "confidence": 0.80,
            "waypoints": [
                {"name": "Incident — Income Tax X-Rd", "lat": 23.0300, "lng": 72.5800},
                {"name": "Ellis Bridge Exit", "lat": 23.0260, "lng": 72.5750},
                {"name": "Relief Road", "lat": 23.0220, "lng": 72.5700},
                {"name": "Nehru Bridge", "lat": 23.0190, "lng": 72.5680},
                {"name": "Gandhi Bridge Re-entry", "lat": 23.0230, "lng": 72.5760},
            ],
        },
        "alerts": [
            ("vms", "2-WHEELER CRASH INCOME TAX X-RD. USE RELIEF RD."),
            ("radio", "Two-wheeler collision on Ashram Road near Income Tax Cross Roads. Centre lane blocked. Divert via Ellis Bridge and Relief Road. Expect 7 minute delay."),
            ("social", "Ashram Road/Income Tax blocked — two-wheeler crash. Divert: Ellis Bridge → Relief Rd → Nehru Bridge. #AhmedabadTraffic"),
        ],
        "narrative": (
            "High severity incident on AMD-ASH-01 (Ashram Road) at Income Tax Cross Roads. "
            "Two-wheeler collision chain — historically the most dangerous mode on this corridor "
            "(562 accidents, 146 fatalities). Two-wheeler signal phase activated. "
            "Diversion via Relief Road absorbs ~30% northbound flow. Confidence 0.80."
        ),
        "confidence": 0.80,
        "evidence_refs": ["SOP-2", "osm_way=AMD-ASH-01", "historical_pattern:two_wheelers"],
    },
    {
        "corridor_id": "AMD-DIN-01",
        "name": "Drive-in Road",
        "lat": 23.0446, "lon": 72.5280,
        "osm_u": 391827465, "osm_v": 391827470,
        "severity": "high",
        "description": (
            "Uncontrolled intersection collision at Drive-in Road / Gurukul Road. "
            "434 recorded accidents, 141 fatalities at uncontrolled junctions on this corridor. "
            "Minor injuries reported; left turn lane blocked."
        ),
        "signal_actions": [
            {
                "intersection_id": "AMD-DIN-01-GURUKUL",
                "action": "Install temporary signal control (officer managed); prioritise Drive-in Road through movement",
                "expected_impact": "Eliminates uncontrolled conflict; restores flow within 15 min",
                "confidence": 0.78,
            },
        ],
        "diversion": {
            "route_description": (
                "Westbound Drive-in Road: divert at Memnagar Fire Station → "
                "Stadium Circle → Stadium Road → rejoin Drive-in Road at Gurukul crossover."
            ),
            "estimated_extra_minutes": 5.0,
            "traffic_redistribution_pct": 25.0,
            "confidence": 0.76,
            "waypoints": [
                {"name": "Incident — Gurukul Cross Roads", "lat": 23.0446, "lng": 72.5280},
                {"name": "Memnagar Fire Station", "lat": 23.0480, "lng": 72.5240},
                {"name": "Stadium Circle", "lat": 23.0510, "lng": 72.5200},
                {"name": "Stadium Rd", "lat": 23.0490, "lng": 72.5260},
                {"name": "Gurukul Re-entry", "lat": 23.0460, "lng": 72.5300},
            ],
        },
        "alerts": [
            ("vms", "CRASH DRIVE-IN RD/GURUKUL. DIVERT VIA STADIUM CIRCLE."),
            ("radio", "Collision at Drive-in Road and Gurukul Road intersection. Left lane blocked. Divert via Memnagar and Stadium Circle. 5 minute extra travel time."),
            ("social", "Drive-in Rd/Gurukul crash. Divert: Memnagar → Stadium Circle → Stadium Rd. #AhmedabadTraffic"),
        ],
        "narrative": (
            "High severity incident on AMD-DIN-01 (Drive-in Road) at Gurukul Cross Roads. "
            "Uncontrolled junction collision — 434 recorded accidents at similar points. "
            "Officer-managed temporary signal recommended. Stadium Circle diversion handles "
            "~25% westbound overflow. Confidence 0.76."
        ),
        "confidence": 0.76,
        "evidence_refs": ["SOP-1", "osm_way=AMD-DIN-01", "historical_pattern:uncontrolled"],
    },
    {
        "corridor_id": "AMD-NHW-08",
        "name": "NH-48 (Delhi-Mumbai Highway)",
        "lat": 22.9900, "lon": 72.5800,
        "osm_u": 502938471, "osm_v": 502938480,
        "severity": "critical",
        "description": (
            "Pedestrian fatality on NH-48 near Narol Naroda Road interchange. "
            "398 pedestrian accidents, 151 fatalities recorded on this highway stretch. "
            "Hard shoulder in use; all lanes slow."
        ),
        "signal_actions": [
            {
                "intersection_id": "AMD-NHW-08-NAROL",
                "action": "Activate variable message signs 2km ahead; reduce speed limit to 60 kph via dynamic signage",
                "expected_impact": "Reduces rear-end collision risk by ~45% in incident zone",
                "confidence": 0.91,
            },
            {
                "intersection_id": "AMD-NHW-08-VATVA",
                "action": "Open emergency shoulder lane for 3km; deploy traffic marshals at Vatva interchange",
                "expected_impact": "Maintains ~60% of normal capacity during clearance",
                "confidence": 0.85,
            },
        ],
        "diversion": {
            "route_description": (
                "NH-48 northbound: exit at Narol interchange → Narol-Naroda Road → "
                "GIDC Vatva Road → NH-48 re-entry at Odhav. "
                "Southbound: use Sardar Patel Ring Road (SPRR) as bypass."
            ),
            "estimated_extra_minutes": 15.0,
            "traffic_redistribution_pct": 45.0,
            "confidence": 0.89,
            "waypoints": [
                {"name": "Incident — Narol Interchange", "lat": 22.9900, "lng": 72.5800},
                {"name": "Narol-Naroda Rd", "lat": 22.9950, "lng": 72.5850},
                {"name": "GIDC Vatva Rd", "lat": 23.0000, "lng": 72.5900},
                {"name": "Odhav GIDC", "lat": 23.0100, "lng": 72.5950},
                {"name": "NH-48 Re-entry Odhav", "lat": 23.0150, "lng": 72.5800},
            ],
        },
        "alerts": [
            ("vms", "FATAL INCIDENT NH-48/NAROL. SPEED 60KPH. EXIT NAROL."),
            ("radio", "Serious incident on NH-48 near Narol. Speed limit reduced to 60 kph. All northbound traffic: exit at Narol interchange and use Narol-Naroda Road via GIDC Vatva. 15 minute delay expected."),
            ("social", "NH-48 CRITICAL: Fatal incident near Narol interchange. Speed limit 60kph. Divert: Narol exit → Narol-Naroda Rd → GIDC Vatva → Odhav. #AhmedabadTraffic #NH48"),
        ],
        "narrative": (
            "Critical incident on AMD-NHW-08 (NH-48) near Narol interchange. "
            "Pedestrian fatality — 398 pedestrian accidents on this highway, 151 fatal. "
            "Dynamic speed reduction to 60 kph activated; emergency shoulder opened. "
            "Diversion via Narol-Naroda Rd + GIDC Vatva redistributes 45% of traffic. "
            "Highest confidence recommendation: 0.89 — sensor + historical + SOP alignment."
        ),
        "confidence": 0.89,
        "evidence_refs": ["SOP-1", "SOP-3", "osm_way=AMD-NHW-08", "historical_pattern:pedestrian_highway"],
    },
]


async def clear_tables(session: AsyncSession) -> None:
    print("Clearing existing data…")
    await session.execute(text("DELETE FROM approvals"))
    await session.execute(text("DELETE FROM alerts"))
    await session.execute(text("DELETE FROM recommendations"))
    await session.execute(text("DELETE FROM incidents"))
    await session.commit()
    print("  ✓ Tables cleared")


async def seed_corridor(session: AsyncSession, c: dict) -> str:
    incident_id = str(uuid.uuid4())
    rec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # 1. Incident
    await session.execute(
        text("""
            INSERT INTO incidents
                (id, status, severity, description, location,
                 corridor_id, reporter_id, detection_confidence,
                 created_at, updated_at)
            VALUES
                (CAST(:id AS uuid), 'active', :severity, :desc,
                 ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                 :corridor_id, 'seed_demo', 0.92,
                 :now, :now)
        """),
        {
            "id": incident_id, "severity": c["severity"], "desc": c["description"],
            "lat": c["lat"], "lon": c["lon"], "corridor_id": c["corridor_id"],
            "now": now,
        },
    )

    # 2. Recommendation with full copilot_response JSON
    copilot_response = {
        "incident_summary": f"Active {c['severity']} incident on {c['corridor_id']} ({c['name']}). {c['description'][:120]}",
        "signal_actions": c["signal_actions"],
        "diversion_plan": {**c["diversion"], "evidence_refs": c["evidence_refs"]},
        "alert_drafts": [{"channel": ch, "message": msg, "char_count": len(msg)} for ch, msg in c["alerts"]],
        "narrative": c["narrative"],
        "conversational_answer": None,
        "overall_confidence": c["confidence"],
        "review_required": True,
        "blocked_reason": None,
        "evidence_refs": c["evidence_refs"],
        "emergency_controls": [],
    }

    await session.execute(
        text("""
            INSERT INTO recommendations
                (id, incident_id, rec_type, action, expected_impact,
                 evidence_refs, confidence, review_required, status,
                 copilot_response, created_at)
            VALUES
                (CAST(:id AS uuid), CAST(:incident_id AS uuid),
                 'composite', :action, :impact,
                 CAST(:evidence_refs AS jsonb), :confidence,
                 true, 'pending',
                 CAST(:copilot AS jsonb), :now)
        """),
        {
            "id": rec_id, "incident_id": incident_id,
            "action": c["narrative"][:500],
            "impact": c["diversion"]["route_description"],
            "evidence_refs": json.dumps(c["evidence_refs"]),
            "confidence": c["confidence"],
            "copilot": json.dumps(copilot_response),
            "now": now,
        },
    )

    # 3. Alerts
    for channel, draft_text in c["alerts"]:
        await session.execute(
            text("""
                INSERT INTO alerts (id, recommendation_id, channel, draft_text, status, created_at)
                VALUES (CAST(:id AS uuid), CAST(:rec_id AS uuid), :channel, :draft_text, 'draft', :now)
            """),
            {"id": str(uuid.uuid4()), "rec_id": rec_id, "channel": channel, "draft_text": draft_text, "now": now},
        )

    await session.commit()
    print(f"  ✓ {c['corridor_id']:15s}  incident={incident_id}  rec={rec_id}  alerts={len(c['alerts'])}")
    return incident_id


async def main() -> None:
    print("=" * 60)
    print("TrafficCopilot — Ahmedabad Demo Seed")
    print("=" * 60)
    async with AsyncSessionLocal() as session:
        await clear_tables(session)
        print("\nSeeding 6 Ahmedabad corridors…")
        ids = []
        for c in CORRIDORS:
            iid = await seed_corridor(session, c)
            ids.append((c["corridor_id"], iid))

    print("\n✅  Done! 6 incidents · 6 recommendations · 24 alerts seeded.")
    print("\n--- Quick test commands ---")
    cid, iid = ids[0]
    print(f"export INCIDENT_ID={iid}  # {cid}")
    print("curl http://localhost:8000/incidents/?limit=6 | python3 -m json.tool")
    print("curl http://localhost:8000/recommendations/$INCIDENT_ID | python3 -m json.tool")
    print("curl http://localhost:8000/alerts/$INCIDENT_ID | python3 -m json.tool")
    print("curl http://localhost:8000/incidents/$INCIDENT_ID/map-data | python3 -m json.tool")
    print(f'\ncurl -s -X POST http://localhost:8000/chat/ -H "Content-Type: application/json" \\')
    print(f'  -d \'{{"incident_id":"{iid}","question":"What alternative route should I take?","officer_id":"officer_01"}}\' | python3 -m json.tool')


if __name__ == "__main__":
    asyncio.run(main())
