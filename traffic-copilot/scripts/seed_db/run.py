#!/usr/bin/env python3
"""Seed sop_chunks and alert_templates tables from data/seeds/ directory."""
import asyncio
import sys
sys.path.insert(0, "/app")

# Read all files from /app/data/seeds/sop_docs/ and /app/data/seeds/alert_templates/
# Call embedding_sync worker
async def main():
    from src.db.session import AsyncSessionLocal
    from src.workers.embedding_sync import run_embedding_sync
    from src.integrations.groq.client import get_groq_client
    async with AsyncSessionLocal() as session:
        await run_embedding_sync(session, get_groq_client())
    print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(main())
