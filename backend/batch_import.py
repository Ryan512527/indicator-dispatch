
import asyncio
import glob
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("batch_import")

DATA_DIR = "/data/2026-06"
PATTERN = "*无线退服清单*.xlsx"


async def main():
    from app.core.database import init_db, async_session, engine, Base
    from app.core.models import IndicatorDefinition, IndicatorEvent
    from app.parser.service import parse_file
    from app.classifier.service import classify_and_store

    # Drop and recreate tables to match current model schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables recreated with current schema")

    # Find matching files
    files = sorted(glob.glob(os.path.join(DATA_DIR, PATTERN)))
    logger.info(f"Found {len(files)} files matching '{PATTERN}' in {DATA_DIR}")

    total_stored = 0
    total_skipped = 0

    for filepath in files:
        fname = os.path.basename(filepath)
        try:
            records = parse_file(filepath)
            if not records:
                logger.info(f"  SKIP {fname}: no records parsed")
                total_skipped += 1
                continue

            n = await classify_and_store(records)
            logger.info(f"  OK   {fname}: {n} records stored (from {len(records)} parsed)")
            total_stored += n
        except Exception as e:
            logger.error(f"  FAIL {fname}: {e}", exc_info=True)
            total_skipped += 1

    logger.info(f"=== Done: {total_stored} records stored, {total_skipped} files skipped ===")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
