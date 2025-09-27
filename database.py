"""
MongoDB database configuration and connection
"""

import os
from urllib.parse import quote_plus
from pymongo import MongoClient
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

# Global database instance
db_config = DatabaseConfig()
