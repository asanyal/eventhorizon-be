"""
Script to create database indexes for optimized query performance
Run this once to set up indexes on your MongoDB collections
"""

from database import db_config
from pymongo import ASCENDING, DESCENDING


def create_indexes():
    """Create indexes on MongoDB collections for better query performance"""

    print("🔧 Creating database indexes...")

    # Connect to database
    db = db_config.connect()

    # === TODOS COLLECTION INDEXES ===
    todos_collection = db_config.get_collection("todos")

    # Index for sorting by created_at (used in most queries)
    todos_collection.create_index([("created_at", DESCENDING)], name="idx_todos_created_at")
    print("✅ Created index: todos.created_at")

    # Index for filtering by urgency
    todos_collection.create_index([("urgency", ASCENDING)], name="idx_todos_urgency")
    print("✅ Created index: todos.urgency")

    # Index for filtering by priority
    todos_collection.create_index([("priority", ASCENDING)], name="idx_todos_priority")
    print("✅ Created index: todos.priority")

    # Compound index for filtering by urgency + priority (common query pattern)
    todos_collection.create_index(
        [("urgency", ASCENDING), ("priority", ASCENDING), ("created_at", DESCENDING)],
        name="idx_todos_urgency_priority_created"
    )
    print("✅ Created compound index: todos.urgency+priority+created_at")

    # === HORIZONS COLLECTION INDEXES ===
    horizons_collection = db_config.get_collection("horizon")

    # Index for sorting by created_at
    horizons_collection.create_index([("created_at", DESCENDING)], name="idx_horizon_created_at")
    print("✅ Created index: horizon.created_at")

    # Index for filtering by horizon_date
    horizons_collection.create_index([("horizon_date", ASCENDING)], name="idx_horizon_date")
    print("✅ Created index: horizon.horizon_date")

    # Compound index for horizon_date + created_at (common query pattern)
    horizons_collection.create_index(
        [("horizon_date", ASCENDING), ("created_at", DESCENDING)],
        name="idx_horizon_date_created"
    )
    print("✅ Created compound index: horizon.horizon_date+created_at")

    # Index for title search (supports regex queries)
    horizons_collection.create_index([("title", ASCENDING)], name="idx_horizon_title")
    print("✅ Created index: horizon.title")

    # Index for type filtering
    horizons_collection.create_index([("type", ASCENDING)], name="idx_horizon_type")
    print("✅ Created index: horizon.type")

    # === BOOKMARKED EVENTS COLLECTION INDEXES (if exists) ===
    try:
        bookmarked_collection = db_config.get_collection("bookmarked_events")

        # Index for sorting by created_at
        bookmarked_collection.create_index([("created_at", DESCENDING)], name="idx_bookmarked_created_at")
        print("✅ Created index: bookmarked_events.created_at")

        # Index for filtering by date
        bookmarked_collection.create_index([("date", ASCENDING)], name="idx_bookmarked_date")
        print("✅ Created index: bookmarked_events.date")

    except Exception as e:
        print(f"⚠️  Skipped bookmarked_events indexes: {e}")

    print("\n✨ All indexes created successfully!")
    print("\n📊 Index summary:")
    print("   Todos: 4 indexes (created_at, urgency, priority, compound)")
    print("   Horizons: 5 indexes (created_at, horizon_date, title, type, compound)")
    print("   Bookmarked Events: 2 indexes (created_at, date)")

    # Display existing indexes
    print("\n📋 Current indexes on 'todos' collection:")
    for index in todos_collection.list_indexes():
        print(f"   - {index['name']}: {index.get('key', {})}")

    print("\n📋 Current indexes on 'horizon' collection:")
    for index in horizons_collection.list_indexes():
        print(f"   - {index['name']}: {index.get('key', {})}")

    # Close connection
    db_config.disconnect()


if __name__ == "__main__":
    try:
        create_indexes()
    except Exception as e:
        print(f"❌ Error creating indexes: {e}")
        raise
