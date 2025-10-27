"""
MongoDB database configuration and connection
"""

import os
from urllib.parse import quote_plus
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.collection import Collection
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DatabaseConfig:
    """Database configuration and connection management"""
    
    def __init__(self):
        self.client: MongoClient = None
        self.database: Database = None
        
    def connect(self) -> Database:
        """Connect to MongoDB and return database instance"""
        try:
            # Get MongoDB credentials from environment
            mongo_user = os.getenv("MONGO_USER")
            mongo_pass = os.getenv("MONGO_PASS")
            mongo_cluster = os.getenv("MONGO_CLUSTER")
            mongo_db_name = os.getenv("MONGO_DB_NAME")
            
            if not all([mongo_user, mongo_pass, mongo_cluster, mongo_db_name]):
                raise ValueError("Missing MongoDB environment variables: MONGO_USER, MONGO_PASS, MONGO_CLUSTER, MONGO_DB_NAME")
            
            # URL-encode username and password to handle special characters
            escaped_user = quote_plus(mongo_user)
            escaped_pass = quote_plus(mongo_pass)
            
            # Construct MongoDB connection string with escaped credentials
            mongodb_url = f"mongodb+srv://{escaped_user}:{escaped_pass}@{mongo_cluster}/?retryWrites=true&w=majority"
            
            # Connect to MongoDB
            self.client = MongoClient(mongodb_url)
            
            # Use the database name from environment
            self.database = self.client[mongo_db_name]
            
            # Test the connection
            self.client.admin.command('ismaster')
            print(f"✅ Connected to MongoDB database: {mongo_db_name}")
            
            return self.database
            
        except Exception as e:
            print(f"❌ Failed to connect to MongoDB: {e}")
            raise e
    
    def disconnect(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            print("🔄 MongoDB connection closed")
    
    def get_collection(self, collection_name: str) -> Collection:
        """Get a specific collection"""
        if self.database is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.database[collection_name]

    def ensure_indexes(self):
        """Ensure all necessary indexes exist for optimal query performance"""
        if self.database is None:
            raise RuntimeError("Database not connected. Call connect() first.")

        try:
            print("🔍 Ensuring database indexes exist...")

            # === TODOS COLLECTION INDEXES ===
            todos_collection = self.get_collection("todos")
            todos_collection.create_index([("created_at", DESCENDING)], name="idx_todos_created_at", background=True)
            todos_collection.create_index([("urgency", ASCENDING)], name="idx_todos_urgency", background=True)
            todos_collection.create_index([("priority", ASCENDING)], name="idx_todos_priority", background=True)
            todos_collection.create_index(
                [("urgency", ASCENDING), ("priority", ASCENDING), ("created_at", DESCENDING)],
                name="idx_todos_urgency_priority_created",
                background=True
            )

            # === HORIZONS COLLECTION INDEXES ===
            horizons_collection = self.get_collection("horizon")
            horizons_collection.create_index([("created_at", DESCENDING)], name="idx_horizon_created_at", background=True)
            horizons_collection.create_index([("horizon_date", ASCENDING)], name="idx_horizon_date", background=True)
            horizons_collection.create_index(
                [("horizon_date", ASCENDING), ("created_at", DESCENDING)],
                name="idx_horizon_date_created",
                background=True
            )
            horizons_collection.create_index([("title", ASCENDING)], name="idx_horizon_title", background=True)
            horizons_collection.create_index([("type", ASCENDING)], name="idx_horizon_type", background=True)

            # === BOOKMARKED EVENTS COLLECTION INDEXES ===
            try:
                bookmarked_collection = self.get_collection("bookmarked_events")
                bookmarked_collection.create_index([("created_at", DESCENDING)], name="idx_bookmarked_created_at", background=True)
                bookmarked_collection.create_index([("date", ASCENDING)], name="idx_bookmarked_date", background=True)
            except Exception:
                pass  # Collection might not exist yet

            # === MEAL PREP COLLECTIONS INDEXES ===
            # Ingredients collection
            try:
                ingredients_collection = self.get_collection("ingredients")
                ingredients_collection.create_index([("created_at", DESCENDING)], name="idx_ingredients_created_at", background=True)
                ingredients_collection.create_index([("name", ASCENDING)], name="idx_ingredients_name", background=True)
            except Exception:
                pass  # Collection might not exist yet

            # Meals collection
            try:
                meals_collection = self.get_collection("meals")
                meals_collection.create_index([("created_at", DESCENDING)], name="idx_meals_created_at", background=True)
                meals_collection.create_index([("name", ASCENDING)], name="idx_meals_name", background=True)
            except Exception:
                pass  # Collection might not exist yet

            # Weekly meal plans collection
            try:
                weekly_plans_collection = self.get_collection("weekly_meal_plans")
                weekly_plans_collection.create_index([("week_start_date", ASCENDING)], name="idx_weekly_plans_date", unique=True, background=True)
                weekly_plans_collection.create_index([("created_at", DESCENDING)], name="idx_weekly_plans_created_at", background=True)
            except Exception:
                pass  # Collection might not exist yet

            print("✅ Database indexes verified/created successfully")

        except Exception as e:
            print(f"⚠️  Warning: Could not ensure indexes: {e}")
            # Don't fail the application if indexes can't be created

# Global database instance
db_config = DatabaseConfig()
