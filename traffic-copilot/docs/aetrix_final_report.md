# Page 1 — Cover Page

**PROJECT TITLE**  
TrafficCopilot: LLM Co-Pilot for Traffic Incident Command

**TEAM NAME**  
[Replace with Team Name]

**TEAM ID**  
[Replace with Team ID]

**ASSIGNED PROBLEM STATEMENT**  
Problem Statement 3: LLM Co-Pilot for Traffic Incident Command

**DOMAIN**  
Smart Transportation

**TEAM MEMBERS & ROLES**  
[Member 1] — Backend / Systems  
[Member 2] — AI / LLM / Retrieval  
[Member 3] — Data / OSM / Routing  
[Member 4] — Product / Demo / Presentation

**HACKATHON NAME & DATE**  
AETRIX 2026  
[Replace with event date if required]

\newpage

# Page 2 — Executive Summary + Problem Statement

## Section 1: Executive Summary

TrafficCopilot is an officer-in-the-loop incident command platform designed for high-pressure traffic emergencies. When a major collision occurs, traffic officers currently have to coordinate speed feeds, camera observations, radio updates, road-network knowledge, diversion decisions, and public communication across disconnected systems. Our solution fuses these signals into one live incident state, maps them onto a real road network, and generates grounded recommendations that are understandable, auditable, and actionable.

The implemented system ingests manual reports, sensor anomalies, camera metadata, and radio transcripts; stores them as structured incident events; snaps geolocated signals onto real roads using OSMnx; computes the affected corridor; retrieves relevant SOPs and templates using pgvector; and produces officer-facing recommendations, public alert drafts, and conversational answers through an LLM-backed co-pilot. Every approval and publication step is kept under human control.

The key differentiator is that this is not a generic chatbot layered onto traffic data. It is an event-driven traffic operations backend that combines deterministic road-network reasoning, live state tracking, retrieval-grounded LLM output, approval workflows, and real-time WebSocket updates. The measurable value is faster response coordination, shorter incident clearance time, and safer public communication during the most chaotic minutes of an emergency.

## Section 2: Problem Statement & Domain Relevance

Traffic management officers managing major incidents face a cognitive overload problem. Sensor feeds, field updates, radio transcripts, road-network constraints, and public-information decisions arrive simultaneously, but there is rarely one unified operational picture. This creates delayed decisions, inconsistent diversion planning, slow alert publishing, and increased risk of secondary accidents.

This problem is highly relevant in smart transportation because time-to-coordination directly affects:
- road clearance time
- secondary crash probability
- emergency vehicle access
- public trust in traffic management communications
- city-wide congestion spillover

The users affected most directly are:
- traffic control officers
- city traffic management centers
- public information officers
- field responders coordinating lane closures and reopening
- commuters impacted by avoidable delays and poor communication

Existing tools are fragmented. Dashboards show numbers, but not coordinated recommendations. Routing tools do not understand live incident context. Communication systems require manual message drafting. Generic LLMs are not grounded in traffic SOPs or live operational state. TrafficCopilot addresses these limitations by combining structured event ingestion, live road reasoning, SOP retrieval, and officer approval into one operational flow.

\newpage

# Page 3 — Proposed Solution + Tech Stack

## Section 3: Proposed Solution

TrafficCopilot is a backend-first command co-pilot for live traffic incident response. It receives incoming incident signals, creates or updates the incident state, computes affected road segments, and generates recommendations that officers can approve, reject, or publish.

### Key Features
- Multi-source incident ingestion from manual reports, speed/sensor events, camera metadata, and radio transcripts
- OSM-based map matching and corridor impact analysis on a real street graph
- SOP-grounded recommendation generation using pgvector retrieval plus LLM reasoning
- Public alert draft generation for VMS, radio, and social channels
- Conversational officer Q&A tied to the current incident state
- Approval, rejection, and audit logging for operational accountability
- WebSocket-based live event push for real-time dashboards

### Why It Is Innovative
- It combines deterministic traffic reasoning with LLM summarization instead of relying on the LLM to guess traffic logic
- It grounds recommendations in retrieved SOPs, prior incident context, and structured live state
- It preserves human control and does not directly actuate traffic infrastructure
- It is designed as an event-driven operations system, not just a chat interface

### Direct Users and Benefits
- Traffic officers get a single operational view and faster recommendations
- Control-room supervisors get live incident tracking and explainable actions
- Public information officers get ready-to-publish drafts during high-pressure conditions

## Section 4: Tech Stack & Architecture

### Frontend / Interface
- Current build is API-first and WebSocket-ready
- Map-ready GeoJSON and live incident updates are exposed for operator dashboards
- The architecture is ready for a React / MapLibre command console

### Backend
- FastAPI for REST APIs, health endpoints, and WebSocket connections
- Async worker architecture for ingestion, incident processing, recommendation generation, and socket fanout
- Structured schemas using Pydantic
- Human approval workflow for recommendations and alerts

### Database
- PostgreSQL as the source of truth
- PostGIS for geospatial incident and road-segment representation
- pgvector for SOP and template retrieval

### Other Tools
- Kafka for event-driven ingestion and worker decoupling
- Redis for hot incident snapshots and fast operational reads
- OSMnx + NetworkX for road graph loading, map matching, corridor reasoning, and diversion support
- Groq LLM for structured recommendation generation and chat
- Hugging Face local embeddings for pgvector retrieval
- Docker Compose for local orchestration

### Architecture Diagram

```text
Manual Report / Sensor Feed / Camera Metadata / Radio Transcript
                           |
                           v
                  FastAPI Ingest Endpoints
                           |
                           v
                     Kafka Event Backbone
                           |
                           v
                 Incident Processor Worker
          - normalize events
          - score confidence
          - create/update incidents
          - map-match to OSM road graph
          - compute affected corridor
                           |
             +-------------+--------------+
             |                            |
             v                            v
   PostgreSQL + PostGIS            Redis Snapshot Cache
             |                            |
             +-------------+--------------+
                           v
                 Context Builder + pgvector
          - retrieve SOP chunks
          - retrieve alert templates
          - retrieve similar incidents
                           |
                           v
                    LLM Recommendation Layer
                           |
                           v
              Recommendations / Alerts / Audit Log
                           |
                           v
                WebSocket Fanout to Operator UI
```

\newpage

# Page 4 — Implementation Details

## Section 5: Implementation Details

### Development Process

The project was built as a modular, event-driven backend to prioritize correctness under live incident conditions. The team first defined the incident lifecycle and data contracts, then implemented ingestion routes, incident persistence, OSM-based corridor analysis, recommendation generation, approval flows, and finally replay/smoke-test scripts for end-to-end validation.

### Key Implementation Highlights
- Unified event model for `manual`, `sensor`, `camera`, and `radio` inputs
- Incident persistence and correlation in PostgreSQL
- OSM-based snapping of geolocated signals to real road segments
- Affected corridor generation with delay and congestion estimates
- pgvector retrieval over SOP chunks and alert templates
- LLM-backed recommendations with structured outputs and policy validation
- Approval and publish flows with audit logging
- WebSocket fanout from Kafka topics for real-time incident rooms

### Challenges & Solutions

**Challenge 1: Schema drift between runtime SQL and database migrations**  
During implementation, the code evolved faster than the schema, causing recommendations, alerts, and audit writes to fail. This was resolved by aligning table definitions, route SQL, worker inserts, and migration files into a single consistent contract.

**Challenge 2: Running PostGIS and pgvector together in local development**  
The default database image supported PostGIS but not pgvector. This broke database initialization. The solution was to create a custom PostgreSQL image that installs both extensions so geospatial and vector retrieval workloads work in the same database.

**Challenge 3: Embedding reliability for retrieval**  
The initial embedding path depended on a Groq embedding model that was unavailable. This was replaced with local Hugging Face embeddings, making retrieval deterministic, cheaper, and more suitable for hackathon development without paid vector services.

### Scalability Measures
- Kafka decouples event ingestion from downstream processing
- Redis reduces repeated heavy reads for live incident state
- PostgreSQL stores the authoritative incident and approval history
- pgvector supports in-database retrieval without introducing a separate vector database
- WebSocket fanout supports multiple operator clients subscribed to the same incident room

### Security Considerations
- Officer-in-the-loop control: recommendations are advisory, not autonomous
- Audit logging for critical actions
- Strict schema validation at input boundaries
- Environment-based secret handling
- Clean separation between incident generation, approval, and publish stages

## Section 6: Future Scope & Enhancements

- Live camera-frame analytics using the Hugging Face vision integration path
- Better multi-signal confidence fusion over sliding time windows
- Historical incident learning and improved few-shot retrieval
- Role-based access control for city operations staff
- Production dashboard with role-specific views
- Integration with CAD, VMS, SMS, and city signal systems

\newpage

# Page 5 — UX + Market Viability

## Section 7: User Experience & Interface

The intended operator journey is simple and pressure-aware. An officer or incoming feed creates an incident. As new signals arrive, the incident state updates in real time. The operator sees the incident summary, affected corridor, recommendation cards, and alert drafts in one place. Instead of interpreting raw data across multiple systems, the officer reviews proposed actions, asks follow-up questions in plain language, and approves or rejects outputs.

The UX is designed around:
- low cognitive load
- rapid situational understanding
- explainable recommendations
- minimal typing under emergency conditions
- live updates without manual refresh

Accessibility and usability considerations include:
- support for low-bandwidth, event-driven updates
- text-first recommendations that can be consumed quickly
- role-based clarity for traffic officers versus public information staff
- architecture that supports mobile, laptop, or control-room deployment

One important UX decision is that the system does not directly control signals or publish automatically by default. This is intentional. In emergency transportation systems, clarity and accountability matter more than aggressive automation.

## Section 8: Market Viability & Business Model

### Target Users
- city traffic management centers
- highway operators
- smart city command centers
- public safety and emergency coordination teams

### Monetisation / Sustainability
- enterprise SaaS licensing for municipal deployments
- annual support and integration contracts
- deployment and customization fees for specific cities or corridors
- premium modules for advanced analytics, historical prediction, and compliance reporting

### Compliance / Legal / Ethical Considerations
- recommendations remain human-reviewed to reduce operational liability
- incident records and approvals are auditable
- sensitive camera or transcript inputs can be stored as metadata instead of raw media
- deployment can align with transport authority SOPs and retention policies

### Real-World Use Cases
- **Urban corridor collision response:** A multi-vehicle crash triggers sensor slowdown, camera metadata, and radio updates. TrafficCopilot unifies the incident, highlights the impacted corridor, generates detour advice, and drafts public messaging.
- **Highway lane reopening decision support:** As clearance progresses, officers ask whether a lane can be reopened safely. The co-pilot answers using recent state, evidence, and SOP-based guidance instead of guesswork.

\newpage

# Page 6 — Conclusion + Appendix

## Section 9: Conclusion

TrafficCopilot demonstrates how an LLM becomes genuinely useful in transportation operations only when it is grounded in structured live data, real road context, and operational policy. The project moves beyond dashboard overload by turning fragmented signals into coherent incident intelligence that officers can act on quickly and safely.

The team’s strongest achievement is not just building an AI layer, but integrating event ingestion, OSM road reasoning, pgvector retrieval, recommendation generation, approval workflows, and live push infrastructure into one incident-response system. That makes the project both technically credible and operationally relevant.

**Vision Statement**  
TrafficCopilot turns traffic incident response from reactive manual coordination into a fast, explainable, human-guided command workflow.

## Section 10: Appendix

### References
- OpenStreetMap / OSMnx documentation
- FastAPI documentation
- PostgreSQL, PostGIS, and pgvector documentation
- Groq API documentation
- Hugging Face sentence-transformers / BGE model documentation

### APIs / Libraries Used
- FastAPI
- SQLAlchemy
- PostgreSQL
- PostGIS
- pgvector
- Redis
- Apache Kafka
- OSMnx
- NetworkX
- Groq
- Hugging Face sentence-transformers

### Acknowledgements
- Hackathon mentors and domain reviewers
- Open-source contributors behind the routing, database, and AI tooling used in the project

### Submission Reminder
- GitHub repository link
- LinkedIn post link
- Final PDF export of this report
