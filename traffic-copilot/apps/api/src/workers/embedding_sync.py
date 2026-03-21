"""
Runs once on startup if tables are empty.
1. Read data/seeds/sop_docs/*.txt files
2. Embed each via groq get_embedding()
3. Upsert into sop_chunks table
4. Read data/seeds/alert_templates/*.json files
5. Embed each template text
6. Upsert into alert_templates table
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from src.core.logging import get_logger

# Stable namespace for deterministic UUID5 generation.
# Using the same namespace means re-running the seed always produces the
# same UUIDs, so ON CONFLICT (id) DO UPDATE works correctly.
_SEED_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # uuid.NAMESPACE_URL


def _seed_uuid(key: str) -> str:
    """Return a stable UUID string derived from *key* via UUID5."""
    return str(uuid.uuid5(_SEED_NS, key))

logger = get_logger(__name__)

# Seed data paths (relative to the container or repo root).
_SOP_DOCS_DIR = Path("/app/data/seeds/sop_docs")
_ALERT_TEMPLATES_DIR = Path("/app/data/seeds/alert_templates")

# Fallback paths for local development outside Docker.
_SOP_DOCS_DIR_DEV = Path("data/seeds/sop_docs")
_ALERT_TEMPLATES_DIR_DEV = Path("data/seeds/alert_templates")


def _resolve_dir(primary: Path, fallback: Path) -> Path | None:
    """Return the first existing directory from the candidates."""
    if primary.exists():
        return primary
    if fallback.exists():
        return fallback
    return None


async def _table_is_empty(session, table: str) -> bool:
    """Return True if the given table has zero rows."""
    from sqlalchemy import text

    try:
        result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))  # noqa: S608
        count = result.scalar()
        return count == 0
    except Exception as exc:
        logger.warning("embedding_sync: could not query table", table=table, error=str(exc))
        # If the table doesn't exist yet, treat as empty so we attempt the sync.
        return True


async def _sync_sop_docs(session, groq_client: Any) -> int:
    """Embed SOP documents and upsert into sop_chunks. Returns number of upserted rows."""
    from sqlalchemy import text

    sop_dir = _resolve_dir(_SOP_DOCS_DIR, _SOP_DOCS_DIR_DEV)
    if sop_dir is None:
        logger.warning("embedding_sync: SOP docs directory not found, skipping", primary=str(_SOP_DOCS_DIR))
        return 0

    txt_files = sorted(sop_dir.glob("*.txt"))
    if not txt_files:
        logger.info("embedding_sync: no .txt files in SOP docs directory", dir=str(sop_dir))
        return 0

    count = 0
    for txt_file in txt_files:
        try:
            content = txt_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            logger.error("embedding_sync: could not read SOP file", file=str(txt_file), error=str(exc))
            continue

        if not content:
            continue

        # Chunk large documents by paragraph (double newline).
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        for idx, chunk_text in enumerate(paragraphs):
            # Deterministic UUID5 so upserts are idempotent across re-runs.
            chunk_key = f"{txt_file.stem}_{idx}"
            chunk_id = _seed_uuid(chunk_key)

            try:
                from src.integrations.groq.client import get_embedding
                embedding = await get_embedding(chunk_text)
            except Exception as exc:
                logger.warning(
                    "embedding_sync: embedding failed for SOP chunk",
                    chunk_key=chunk_key,
                    chunk_id=chunk_id,
                    error=str(exc),
                )
                continue

            try:
                # Savepoint per row — a bad vector won't abort the whole transaction.
                async with session.begin_nested():
                    await session.execute(
                        text(
                            """
                            INSERT INTO sop_chunks (id, title, source_file, content, embedding)
                            VALUES (:id, :title, :source_file, :content, CAST(:embedding AS vector))
                            ON CONFLICT (id) DO UPDATE
                                SET content    = EXCLUDED.content,
                                    embedding  = EXCLUDED.embedding
                            """
                        ),
                        {
                            "id": chunk_id,
                            "title": f"{txt_file.stem} (chunk {idx+1})",
                            "source_file": txt_file.name,
                            "content": chunk_text,
                            "embedding": json.dumps(embedding),
                        },
                    )
                count += 1
            except Exception as exc:
                logger.error(
                    "embedding_sync: upsert failed for SOP chunk",
                    chunk_id=chunk_id,
                    error=str(exc),
                )

    await session.commit()
    logger.info("embedding_sync: SOP chunks upserted", count=count)
    return count


async def _sync_alert_templates(session, groq_client: Any) -> int:
    """Embed alert templates and upsert into alert_templates. Returns number of upserted rows."""
    from sqlalchemy import text

    tmpl_dir = _resolve_dir(_ALERT_TEMPLATES_DIR, _ALERT_TEMPLATES_DIR_DEV)
    if tmpl_dir is None:
        logger.warning(
            "embedding_sync: alert_templates directory not found, skipping",
            primary=str(_ALERT_TEMPLATES_DIR),
        )
        return 0

    json_files = sorted(tmpl_dir.glob("*.json"))
    if not json_files:
        logger.info("embedding_sync: no .json files in alert_templates directory", dir=str(tmpl_dir))
        return 0

    count = 0
    for json_file in json_files:
        try:
            raw = json_file.read_text(encoding="utf-8")
            template_data: dict = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error(
                "embedding_sync: could not read/parse alert template",
                file=str(json_file),
                error=str(exc),
            )
            continue

        # Extract the text to embed — prefer "text", then "message", then full JSON.
        embed_text: str = (
            template_data.get("text")
            or template_data.get("message")
            or template_data.get("content")
            or json.dumps(template_data, default=str)
        )
        template_key = template_data.get("id") or json_file.stem
        template_id = _seed_uuid(template_key)
        channel = template_data.get("channel", "general")
        name = template_data.get("name") or json_file.stem

        try:
            from src.integrations.groq.client import get_embedding
            embedding = await get_embedding(embed_text)
        except Exception as exc:
            logger.warning(
                "embedding_sync: embedding failed for alert template",
                template_id=template_id,
                error=str(exc),
            )
            continue

        try:
            async with session.begin_nested():
                await session.execute(
                    text(
                        """
                        INSERT INTO alert_templates
                            (id, channel, incident_type, template_text, embedding)
                        VALUES
                            (:id, :channel, :incident_type, :template_text, CAST(:embedding AS vector))
                        ON CONFLICT (id) DO UPDATE
                            SET channel       = EXCLUDED.channel,
                                incident_type = EXCLUDED.incident_type,
                                template_text = EXCLUDED.template_text,
                                embedding     = EXCLUDED.embedding
                        """
                    ),
                    {
                        "id": template_id,
                        "channel": channel,
                        "incident_type": name,
                        "template_text": embed_text,
                        "embedding": json.dumps(embedding),
                    },
                )
            count += 1
        except Exception as exc:
            logger.error(
                "embedding_sync: upsert failed for alert template",
                template_id=template_id,
                error=str(exc),
            )

    await session.commit()
    logger.info("embedding_sync: alert templates upserted", count=count)
    return count


async def run_embedding_sync(session: Any, groq_client: Any) -> None:
    """
    One-shot sync. Safe to call multiple times (upserts, not inserts).

    Checks if tables are empty before embedding to avoid redundant work on
    repeated restarts.  Each seed section is independent — a failure in one
    does not prevent the other from running.
    """
    logger.info("embedding_sync: starting")

    # --- SOP docs -----------------------------------------------------------
    try:
        sop_empty = await _table_is_empty(session, "sop_chunks")
        if sop_empty:
            logger.info("embedding_sync: sop_chunks table is empty, seeding")
            await _sync_sop_docs(session, groq_client)
        else:
            logger.info("embedding_sync: sop_chunks already populated, skipping")
    except Exception as exc:
        logger.error("embedding_sync: SOP sync failed", error=str(exc), exc_info=True)

    # --- Alert templates ----------------------------------------------------
    try:
        tmpl_empty = await _table_is_empty(session, "alert_templates")
        if tmpl_empty:
            logger.info("embedding_sync: alert_templates table is empty, seeding")
            await _sync_alert_templates(session, groq_client)
        else:
            logger.info("embedding_sync: alert_templates already populated, skipping")
    except Exception as exc:
        logger.error("embedding_sync: alert template sync failed", error=str(exc), exc_info=True)

    logger.info("embedding_sync: complete")
