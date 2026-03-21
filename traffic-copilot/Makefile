.PHONY: up down logs seed graph embeddings replay smoke topics test shell dev bootstrap reset

# ── Dev: start infra + api (no observability) ─────────────────────────────────
up:
	docker compose up -d

dev: up
	@echo "Waiting 30s for postgres/kafka to become healthy..."
	@sleep 30
	@echo "Seeding database..."
	$(MAKE) seed
	@echo ""
	@echo "TrafficCopilot API is running at http://localhost:8000"
	@echo "  Swagger docs : http://localhost:8000/docs"
	@echo "  Health check : http://localhost:8000/health"
	@echo "  Live logs    : make logs"

down:
	docker compose down

# Hard reset: wipe volumes and rebuild from scratch
reset:
	docker compose down -v
	docker compose up -d --build
	@sleep 30
	$(MAKE) seed

logs:
	docker compose logs -f api

# ── Database seed (SOP chunks + intersections + alert templates) ──────────────
seed:
	docker compose exec api python /app/scripts/seed_db/run.py

# ── OSM graph download (run once, takes ~2 min) ───────────────────────────────
graph:
	docker compose exec api python /app/scripts/import_osm/run.py

# ── Generate pgvector embeddings for SOP chunks ───────────────────────────────
embeddings:
	docker compose exec api python /app/scripts/generate_embeddings/run.py

# ── Feed replay: replay scenario_1 against live API ──────────────────────────
replay:
	docker compose exec api python /app/scripts/replay_feeds/run.py --scenario scenario_1

# ── Smoke tests ───────────────────────────────────────────────────────────────
smoke:
	bash scripts/smoke_tests/run.sh

# ── Kafka topic list ──────────────────────────────────────────────────────────
topics:
	docker compose exec kafka /opt/kafka/bin/kafka-topics.sh \
	  --bootstrap-server localhost:9092 --list

# ── Run tests ─────────────────────────────────────────────────────────────────
test:
	docker compose exec api pytest src/tests/ -v

# ── Interactive shell inside API container ────────────────────────────────────
shell:
	docker compose exec api bash

# ── Observability stack (Prometheus + Grafana, opt-in) ───────────────────────
observe:
	docker compose --profile observability up -d prometheus grafana
	@echo "Prometheus : http://localhost:9090"
	@echo "Grafana    : http://localhost:3001  (admin/admin)"

# ── Full one-shot bootstrap (first time) ──────────────────────────────────────
bootstrap: up
	@echo "Waiting 30s for services..."
	@sleep 30
	$(MAKE) seed
	@echo ""
	@echo "Optional next steps:"
	@echo "  make graph       — download OSMnx road graph (~2 min)"
	@echo "  make embeddings  — generate pgvector embeddings"
	@echo "  make replay      — replay scenario_1 incident feed"
