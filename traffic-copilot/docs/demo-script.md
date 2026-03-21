# TrafficCopilot — 8-Minute Judge Demo Script

Version 1.0 | Last Updated: 2026-03-21
Presenter: [Your Name] | Role: Lead Engineer

---

## Pre-Demo Checklist (Run 10 Minutes Before)

```bash
# 1. Verify all services are up
docker compose ps

# Expected: all containers show "Up" status
# trafficcopilot-api-1       Up   0.0.0.0:8000->8000/tcp
# trafficcopilot-web-1       Up   0.0.0.0:3000->3000/tcp
# trafficcopilot-postgres-1  Up   0.0.0.0:5432->5432/tcp
# trafficcopilot-redis-1     Up   0.0.0.0:6379->6379/tcp
# trafficcopilot-kafka-1     Up   0.0.0.0:9092->9092/tcp
# trafficcopilot-grafana-1   Up   0.0.0.0:3001->3001/tcp

# 2. Verify DB is seeded
docker compose exec api python /app/scripts/seed_db/run.py
# Expected: "Seeding complete."

# 3. Clear any stale incident state from a prior run
docker compose exec api python -c "
import asyncio
from src.db.session import AsyncSessionLocal
from sqlalchemy import text
async def clean():
    async with AsyncSessionLocal() as s:
        await s.execute(text('TRUNCATE incidents, recommendations, audit_log, raw_events CASCADE'))
        await s.commit()
asyncio.run(clean())
"

# 4. Open browser tabs (pre-loaded):
#   Tab 1: http://localhost:3000        (Dashboard)
#   Tab 2: http://localhost:3001        (Grafana)
#   Tab 3: http://localhost:8000/docs   (API docs — fallback demo)

# 5. Open terminal split: left = replay runner, right = API logs
```

---

## T+0:00 — Introduction (45 seconds)

**Say:** "Traffic management centres handle hundreds of incidents a day. Officers juggle live sensor feeds, radio calls, camera footage, and must respond within minutes to prevent cascade congestion. Today I'm going to show you TrafficCopilot — an AI copilot that fuses all those signals in real time, retrieves the relevant SOP, and hands the officer a ranked, actionable recommendation — in under 30 seconds. The human is always in the loop: the AI recommends, the officer decides."

**Point at the dashboard:** "This is the live TMC dashboard. It's empty right now. Watch what happens in the next 30 seconds."

---

## T+0:45 — Start the Feed Replay (30 seconds)

**In the terminal (left pane), run:**

```bash
docker compose exec api python /app/scripts/replay_feeds/run.py \
  --scenario data/replays/scenario_1 \
  --speed 1.0
```

**Expected terminal output:**
```
[14:00:00Z] Replaying: 001_manual_incident.json  → published to raw.traffic_events
[14:00:05Z] Replaying: 002_sensor_speed.json     → published to raw.traffic_events
[14:00:10Z] Replaying: 003_camera_meta.json      → published to raw.traffic_events
[14:00:15Z] Replaying: 004_radio_transcript.json → published to raw.traffic_events
[14:00:20Z] Replaying: 005_sensor_upstream.json  → published to raw.traffic_events
Scenario replay complete (5 events).
```

**Say while events stream:** "We're replaying a real-world scenario: a multi-vehicle collision on I-5 Southbound at Exit 42. Five data sources confirming the incident within 20 seconds — a manual officer report, two sensor readings showing speed down to 12 km/h from an 80 km/h free flow, a camera detecting a blocked lane with 91% confidence, and a radio transcript from Unit 7 on scene."

---

## T+1:15 — Watch the Dashboard React (45 seconds)

**Switch focus to Tab 1 (Dashboard).**

**Expected on screen within ~5 seconds of replay start:**
- A red incident marker appears on the map at I-5 SB Exit 42.
- Incident card in the left panel shows: "HIGH severity — Multi-vehicle collision, 3 vehicles, left lane blocked."
- Sensor timeline shows speed drop from 80 → 12 km/h on segment S-042.
- Status badge: "Detection confidence: 94% | Sources: manual, sensor(×2), camera, radio"

**Say:** "The detection layer fused all five signals and opened an incident record with 94% confidence in under 3 seconds. Note the sources badge — it's not just one data point. The camera, the sensor, the officer on the ground, and the radio call all agree."

**Point to the status bar:** "The recommendation engine has been triggered. It's now building context: pulling the incident snapshot, running pgvector search over our SOP library, computing alternative routes with OSMnx, and assembling the LLM prompt."

---

## T+2:00 — First Recommendation Arrives (45 seconds)

**Expected on screen (target: before T+2:00, definitely before T+2:30):**
- "Recommendation Ready" notification appears (toast + panel update).
- Recommendations panel shows a bundle with 4–5 ranked actions.
- Confidence badge: ~0.87
- "Generated in 18s" timer shown.

**Say:** "There it is — first recommendation in 18 seconds. Well under our 30-second target."

**Walk through the recommendation panel:**

"Action 1 — highest priority: Activate VMS boards upstream. The system has pre-drafted the message: 'ACCIDENT I-5 SB EXIT 42. USE HWY 101 N. EXPECT 25 MIN DELAY.' This is sourced from our VMS alert template and grounded in SOP-005, which mandates VMS activation within 3 minutes of a Tier 1 incident. The SOP reference is right here — the officer can click it to read the exact clause."

"Action 2: Activate diversion via Highway 101 North. The routing module computed three alternatives and ranked this one best — 8 km longer, but current Level of Service B versus the blocked primary. Queue length estimate: 2.1 km."

"Action 3: Request signal retiming on the diversion route. Three intersections flagged. Recommended green extension: 20 seconds on the critical approach at each. SOP-004 compliance: Tier A — TMO can approve directly, no supervisor needed."

"Action 4: Dispatch a TIR vehicle if not already on scene. Action 5: Issue radio broadcast bulletin — draft already written."

---

## T+2:45 — Approve Actions (60 seconds)

**Say:** "The officer reviews and approves. They agree with all five. Let's do it."

**In the dashboard, click "Approve All" button on the recommendation panel.**

**Expected behavior:**
- Each action card flips to "Approved" state with a green checkmark.
- A confirmation dialog appears: "You are about to dispatch 3 public alerts and 1 signal plan change. Confirm?" — click "Confirm".
- Toast notifications: "VMS boards activated", "Radio bulletin queued", "Signal plan submitted to TSMS", "TIR dispatch request sent".
- Audit log panel (bottom of screen) shows 5 new entries with timestamp and officer ID.

**Say:** "Every approval is written to an immutable audit log. Timestamp, officer, action, rationale — all of it. If an inquiry happens 6 months later, we have the full decision trail."

**Point to the map:** "The diversion route is now shown on the map in orange. The VMS boards upstream are highlighted as active."

---

## T+3:45 — Chat Q&A with the Copilot (60 seconds)

**Switch to the chat panel on the right side of the dashboard.**

**Type and submit the following question:**
```
What is the expected clearance time and should I close the ramp at Exit 44?
```

**Expected response (within ~8 seconds):**
```
Based on the current incident data:

Estimated clearance time: 14:45 UTC (approximately 45 minutes from now).
This assumes the heavy recovery vehicle arrives within 15 minutes — Unit 7
reported requesting tow support at 14:00:15Z.

Regarding ramp closure at Exit 44: I recommend monitoring but not yet
closing. Current queue length is 2.1 km, which has not yet reached the
Exit 44 entry point (approximately 3.2 km upstream). Per SOP-001, ramp
metering should be considered if queue exceeds 5 km. I will flag this
for review if queue grows beyond 4 km.

Reference: SOP-001 §4 (Opening/Closing Ramps), SOP-003 §3c (Corridor
Management — Upstream Ramp Actions).
```

**Say:** "The officer can ask follow-up questions in natural language. The answer cites the specific SOP sections. This isn't a generic chatbot — it's grounded in the actual procedures this agency uses. The intent classifier understood this was a two-part operational question and gave a two-part answer with specific thresholds."

---

## T+4:45 — Fallback Mode Demo (45 seconds)

**Say:** "What happens if the AI goes down? Let's find out."

**In the terminal (right pane), run:**

```bash
# Temporarily disable Groq API connectivity
docker compose exec api python -c "
import os
os.environ['GROQ_API_KEY'] = 'INVALID_KEY_DEMO'
print('Groq key invalidated for fallback demo')
"

# Trigger a new incident manually via the API
curl -s -X POST http://localhost:8000/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "severity": "medium",
    "description": "Vehicle breakdown blocking right shoulder, Exit 38",
    "lat": 40.7640,
    "lon": -73.9810,
    "corridor_id": "I5-SB-38",
    "reporter_id": "unit_12"
  }' | python -m json.tool
```

**Expected dashboard behavior within ~5 seconds:**
- New incident card appears with an amber "Fallback Mode" badge.
- Recommendation panel shows deterministic actions based on severity=medium rule table.
- Banner at top of recommendation: "AI engine unavailable — recommendations generated by rule-based fallback. Human review is especially important."

**Say:** "The system degrades gracefully. Officers still get actionable recommendations — they're just based on our hardcoded decision tables rather than contextual AI reasoning. The fallback badge makes this transparent. The officer knows to apply more judgment."

**Restore Groq connectivity:**

```bash
docker compose restart api
# Wait 10 seconds for restart
```

---

## T+5:30 — Grafana Metrics (45 seconds)

**Switch to Tab 2 (Grafana — http://localhost:3001). Dashboard: "TrafficCopilot Operations".**

**Point to each panel while speaking:**

"Recommendation latency — P50 is 16 seconds, P95 is 24 seconds. We're comfortably under the 30-second SLA across all incidents replayed today."

"LLM token usage — this tracks our Groq API consumption. Each recommendation costs roughly 3,200 tokens. At Groq's inference speeds, that's about 1.2 seconds of actual inference time within our 18-second end-to-end window."

"Kafka consumer lag — near-zero on both the `raw.traffic_events` and `detected.incidents` topics. No backpressure."

"Approval rate — 100% for this demo scenario, as expected. In a production deployment you'd see some rejected recommendations and the edit-then-approve flow. The recommendation quality score (operator feedback) is tracked here as a long-term model evaluation metric."

"Incident detection confidence distribution — most incidents are being detected above 0.85. The multi-signal fusion approach is paying off."

---

## T+6:15 — Incident Resolution (30 seconds)

**Back in Tab 1 (Dashboard). In the terminal, run the clearance event:**

```bash
curl -s -X PATCH http://localhost:8000/incidents/$(curl -s http://localhost:8000/incidents?corridor_id=I5-SB-42 | python -m json.tool | python -c "import sys,json; data=json.load(sys.stdin); print(data[0]['id'])") \
  -H "Content-Type: application/json" \
  -d '{"status": "cleared", "cleared_by": "unit_7"}' | python -m json.tool
```

**Expected dashboard behavior:**
- Incident marker turns green on the map.
- Recommendation panel shows new auto-generated deactivation actions: "Deactivate diversion — confirm queue dissipating", "Update VMS to LANES CLEAR for 10 min", "Issue all-clear radio bulletin".
- Audit log records the clearance event.

**Say:** "Unit 7 calls clear. The system immediately generates a deactivation checklist: remove the diversion, update VMS to all-clear for at least 10 minutes as SOP-002 requires, and issue the radio all-clear. The officer clicks approve and the incident is closed."

---

## T+6:45 — Architecture Summary (45 seconds)

**Say:** "Let me quickly summarise the stack. Five data streams converge at a Kafka ingest layer. The detection engine does multi-signal fusion and writes to Postgres and Redis. The recommendation engine does RAG over pgvector — our SOP library is embedded and stored in Postgres, no separate vector database needed. OSMnx computes routing alternatives from open map data. Groq's Llama 70B does the reasoning, targeting sub-5-second LLM inference. The whole pipeline delivers a recommendation in under 30 seconds."

"Everything is containerised in Docker Compose for the demo. The same architecture deploys to Kubernetes — we have the manifests in the k8s directory."

---

## T+7:30 — Closing Statement (30 seconds)

**Say:** "TrafficCopilot demonstrates that AI can genuinely augment traffic management — not by replacing officers, but by eliminating the cognitive load of synthesising dozens of simultaneous data streams and cross-referencing the SOP manual under pressure. The officer stays in control. The AI does the synthesis, the retrieval, and the drafting. The result is faster, more consistent, SOP-aligned responses to incidents — and a complete audit trail for every decision."

"Happy to take questions."

---

## Backup Commands (If Something Goes Wrong)

**If the dashboard is blank / WebSocket not connecting:**
```bash
docker compose restart api web
# Wait 15 seconds, then refresh browser
```

**If recommendations aren't appearing:**
```bash
# Check copilot_trigger worker logs
docker compose logs api --tail=50 | grep copilot_trigger

# Check Kafka topic has events
docker compose exec kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic detected.incidents \
  --from-beginning \
  --max-messages 5
```

**If Postgres is unreachable:**
```bash
docker compose restart postgres
sleep 10
docker compose restart api
```

**If you need to fully reset and re-run:**
```bash
docker compose down -v
docker compose up -d
sleep 30
docker compose exec api python /app/scripts/seed_db/run.py
# Then restart the demo from T+0:45
```

**Manual recommendation trigger (if feed replay fails):**
```bash
curl -s -X POST http://localhost:8000/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "severity": "high",
    "description": "Multi-vehicle collision, 3 vehicles involved, left lane blocked. Unit 7 on scene.",
    "lat": 40.7580,
    "lon": -73.9855,
    "corridor_id": "I5-SB-42",
    "reporter_id": "unit_7"
  }' | python -m json.tool
```

**Direct API docs demo (if dashboard fails entirely):**
- Navigate to http://localhost:8000/docs
- Use the Swagger UI to demonstrate POST /incidents and GET /recommendations/{id}
- This demonstrates the same backend capability without the frontend

---

## Timing Summary

| Segment | Start | Duration | Key Point |
|---------|-------|----------|-----------|
| Introduction | T+0:00 | 45s | Problem statement |
| Feed replay | T+0:45 | 30s | 5 data streams in 20 seconds |
| Dashboard reaction | T+1:15 | 45s | Multi-signal fusion, 94% confidence |
| First recommendation | T+2:00 | 45s | **< 30 second target demonstrated** |
| Approval flow | T+2:45 | 60s | Human-in-the-loop, audit trail |
| Chat Q&A | T+3:45 | 60s | SOP-grounded natural language |
| Fallback mode | T+4:45 | 45s | Graceful degradation |
| Grafana metrics | T+5:30 | 45s | P50 latency, Kafka lag, approval rate |
| Incident resolution | T+6:15 | 30s | Clearance flow end-to-end |
| Architecture summary | T+6:45 | 45s | Stack overview |
| Closing | T+7:30 | 30s | Value proposition |
| **Total** | | **8:00** | |
