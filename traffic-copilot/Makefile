.PHONY: up down logs migrate seed graph embeddings replay smoke topics test shell bootstrap

# ── Compose lifecycle ─────────────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

# ── Database / schema ─────────────────────────────────────────────────────────
migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api python /app/scripts/seed_db/run.py

# ── OSM graph ─────────────────────────────────────────────────────────────────
graph:
	docker compose exec api python /app/scripts/import_osm/run.py

# ── Embeddings ────────────────────────────────────────────────────────────────
embeddings:
	docker compose exec api python /app/scripts/generate_embeddings/run.py

# ── Feed replay ───────────────────────────────────────────────────────────────
replay:
	docker compose exec api python /app/scripts/replay_feeds/run.py

# ── Smoke tests ───────────────────────────────────────────────────────────────
smoke:
	docker compose exec api python /app/scripts/smoke_tests/run.py

# ── Kafka introspection ───────────────────────────────────────────────────────
topics:
	docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# ── Unit / integration tests ──────────────────────────────────────────────────
test:
	docker compose exec api pytest src/tests/ -v

# ── Interactive shell ─────────────────────────────────────────────────────────
shell:
	docker compose exec api bash

# ── One-shot bootstrap ────────────────────────────────────────────────────────
bootstrap: up
	@echo "Waiting 15s for services to become healthy..."
	sleep 15
	$(MAKE) migrate
	$(MAKE) seed
	$(MAKE) graph
	$(MAKE) embeddings
