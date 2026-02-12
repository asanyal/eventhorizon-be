"""
MongoDB performance diagnostics
"""

import time
import logging
from database import db_config

logger = logging.getLogger(__name__)

def diagnose_mongodb_performance():
    """Run diagnostics on MongoDB connection and query performance"""
    if db_config.database is None:
        logger.error("❌ Database not connected")
        return

    try:
        logger.info("🔍 Running MongoDB performance diagnostics...")

        # Test 1: Simple ping
        start = time.time()
        db_config.client.admin.command('ping')
        ping_time = (time.time() - start) * 1000
        logger.info(f"⏱️  Ping: {ping_time:.2f}ms")

        # Test 2: Server status
        start = time.time()
        status = db_config.client.admin.command('serverStatus')
        status_time = (time.time() - start) * 1000
        logger.info(f"⏱️  Server status: {status_time:.2f}ms")

        # Test 3: Database stats
        start = time.time()
        db_stats = db_config.database.command('dbStats')
        dbstats_time = (time.time() - start) * 1000
        logger.info(f"⏱️  Database stats: {dbstats_time:.2f}ms")

        # Test 4: Collection count
        try:
            horizon_collection = db_config.get_collection("horizon")
            start = time.time()
            count = horizon_collection.count_documents({})
            count_time = (time.time() - start) * 1000
            logger.info(f"⏱️  Count horizons ({count} docs): {count_time:.2f}ms")

            # Test 5: Simple query
            start = time.time()
            list(horizon_collection.find({}).limit(10))
            query_time = (time.time() - start) * 1000
            logger.info(f"⏱️  Query 10 horizons: {query_time:.2f}ms")

            # Test 6: Query with sort (like actual endpoint)
            start = time.time()
            list(horizon_collection.find({}).sort("created_at", -1).limit(10))
            sorted_query_time = (time.time() - start) * 1000
            logger.info(f"⏱️  Query 10 horizons with sort: {sorted_query_time:.2f}ms")

            # Test 7: Full collection scan (what endpoint does)
            start = time.time()
            docs = list(horizon_collection.find({}).sort("created_at", -1))
            full_scan_time = (time.time() - start) * 1000
            logger.info(f"⏱️  Full collection scan ({len(docs)} docs): {full_scan_time:.2f}ms")

        except Exception as e:
            logger.warning(f"⚠️  Could not test horizon collection: {e}")

        # Connection info
        logger.info(f"📊 Connection pool size: {len(db_config.client.nodes)}")
        logger.info(f"📊 Database: {db_config.database.name}")

        # Network latency assessment
        if ping_time > 100:
            logger.warning(f"⚠️  HIGH NETWORK LATENCY: {ping_time:.2f}ms - Consider moving MongoDB closer to Replit region")
        elif ping_time > 50:
            logger.info(f"⚠️  Moderate network latency: {ping_time:.2f}ms")
        else:
            logger.info(f"✅ Good network latency: {ping_time:.2f}ms")

        logger.info("✅ MongoDB diagnostics complete")

    except Exception as e:
        logger.error(f"❌ Diagnostics failed: {e}")
