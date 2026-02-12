"""
OPTIMIZED Repository for horizon collection operations with pagination
Replace horizon_repository.py with this for better performance
"""

from datetime import datetime
from typing import List, Optional
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from pymongo import ReturnDocument
from bson import ObjectId
import time
import logging

from database import db_config
from models import HorizonCreate, HorizonResponse, HorizonUpdate, HorizonEdit

logger = logging.getLogger(__name__)

class HorizonRepository:
    """Repository class for horizon collection operations"""

    def __init__(self):
        self.collection_name = "horizon"
        self._collection: Optional[Collection] = None

    @property
    def collection(self) -> Collection:
        """Get the horizon collection"""
        if self._collection is None:
            if db_config.database is None:
                raise RuntimeError("Database not connected")
            self._collection = db_config.get_collection(self.collection_name)
        return self._collection

    async def create_horizon(self, horizon_data: HorizonCreate) -> HorizonResponse:
        """Create a new horizon item"""
        try:
            # Prepare document for insertion
            now = datetime.utcnow()
            horizon_doc = {
                "title": horizon_data.title,
                "details": horizon_data.details,
                "type": horizon_data.type,
                "horizon_date": horizon_data.horizon_date,
                "created_at": now,
                "updated_at": now
            }

            # Insert into MongoDB
            result = self.collection.insert_one(horizon_doc)

            # Return response directly without additional query
            horizon_doc["_id"] = result.inserted_id
            return HorizonResponse(**horizon_doc)

        except PyMongoError as e:
            raise RuntimeError(f"Database error while creating horizon: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error creating horizon: {str(e)}")

    async def get_all_horizons(
        self,
        horizon_date: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[HorizonResponse]:
        """
        Get horizon items with pagination, optionally filtered by horizon_date

        Args:
            horizon_date: Optional date filter
            limit: Maximum number of items to return (default 100)
            skip: Number of items to skip for pagination (default 0)
        """
        try:
            start_time = time.time()

            # Build query filter
            query = {}
            if horizon_date:
                query["horizon_date"] = horizon_date

            query_build_time = (time.time() - start_time) * 1000
            logger.info(f"⏱️  [Horizon] Query build: {query_build_time:.2f}ms")

            # Retrieve horizons with query, sorted by created_at descending (newest first)
            # Add limit and skip for pagination
            db_query_start = time.time()
            cursor = self.collection.find(query).sort("created_at", -1).limit(limit).skip(skip)

            # Fetch all documents from cursor
            fetch_start = time.time()
            horizon_docs = list(cursor)
            fetch_time = (time.time() - fetch_start) * 1000
            logger.info(f"⏱️  [Horizon] MongoDB fetch ({len(horizon_docs)} docs, limit={limit}, skip={skip}): {fetch_time:.2f}ms")

            # Use list comprehension for better performance
            serialize_start = time.time()
            horizons = [HorizonResponse(**horizon_doc) for horizon_doc in horizon_docs]
            serialize_time = (time.time() - serialize_start) * 1000
            logger.info(f"⏱️  [Horizon] Pydantic serialization: {serialize_time:.2f}ms")

            total_time = (time.time() - start_time) * 1000
            logger.info(f"⏱️  [Horizon] TOTAL get_all_horizons: {total_time:.2f}ms")

            return horizons

        except PyMongoError as e:
            raise RuntimeError(f"Database error while retrieving horizons: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving horizons: {str(e)}")

    async def count_horizons(self, horizon_date: Optional[str] = None) -> int:
        """Count total number of horizons (for pagination)"""
        try:
            query = {}
            if horizon_date:
                query["horizon_date"] = horizon_date
            return self.collection.count_documents(query)
        except PyMongoError as e:
            raise RuntimeError(f"Database error while counting horizons: {str(e)}")

    async def get_horizon_by_id(self, horizon_id: str) -> Optional[HorizonResponse]:
        """Get a specific horizon by ID"""
        try:
            if not ObjectId.is_valid(horizon_id):
                return None

            horizon_doc = self.collection.find_one({"_id": ObjectId(horizon_id)})

            if not horizon_doc:
                return None

            return HorizonResponse(**horizon_doc)

        except PyMongoError as e:
            raise RuntimeError(f"Database error while retrieving horizon: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving horizon: {str(e)}")

    async def update_horizon(self, horizon_id: str, horizon_data: HorizonUpdate) -> Optional[HorizonResponse]:
        """Update a horizon item"""
        try:
            if not ObjectId.is_valid(horizon_id):
                return None

            # Prepare update data
            update_data = {"updated_at": datetime.utcnow()}

            if horizon_data.title is not None:
                update_data["title"] = horizon_data.title
            if horizon_data.details is not None:
                update_data["details"] = horizon_data.details
            if horizon_data.type is not None:
                update_data["type"] = horizon_data.type
            if horizon_data.horizon_date is not None:
                update_data["horizon_date"] = horizon_data.horizon_date

            # Update and return document in single operation
            updated_horizon = self.collection.find_one_and_update(
                {"_id": ObjectId(horizon_id)},
                {"$set": update_data},
                return_document=ReturnDocument.AFTER
            )

            return HorizonResponse(**updated_horizon) if updated_horizon else None

        except PyMongoError as e:
            raise RuntimeError(f"Database error while updating horizon: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error updating horizon: {str(e)}")

    async def delete_horizon(self, horizon_id: str) -> bool:
        """Delete a horizon item"""
        try:
            if not ObjectId.is_valid(horizon_id):
                return False

            result = self.collection.delete_one({"_id": ObjectId(horizon_id)})
            return result.deleted_count > 0

        except PyMongoError as e:
            raise RuntimeError(f"Database error while deleting horizon: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error deleting horizon: {str(e)}")

    async def delete_horizon_by_title(self, title: str) -> int:
        """Delete horizon items by title (returns count of deleted items)"""
        try:
            if not title or not title.strip():
                return 0

            result = self.collection.delete_many({"title": title.strip()})
            return result.deleted_count

        except PyMongoError as e:
            raise RuntimeError(f"Database error while deleting horizons by title: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error deleting horizons by title: {str(e)}")

    async def search_horizons_by_title(self, title_query: str) -> List[HorizonResponse]:
        """Search horizons by partial title match"""
        try:
            if not title_query or not title_query.strip():
                return []

            # Use regex for case-insensitive partial matching
            cursor = self.collection.find({
                "title": {"$regex": title_query.strip(), "$options": "i"}
            }).sort("created_at", -1)

            return [HorizonResponse(**horizon_doc) for horizon_doc in cursor]

        except PyMongoError as e:
            raise RuntimeError(f"Database error while searching horizons: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error searching horizons: {str(e)}")

    async def edit_horizon_by_criteria(self, edit_data: HorizonEdit) -> List[HorizonResponse]:
        """Edit horizon items by matching existing criteria and updating with new values"""
        try:
            # Build the query to find horizons to update
            query = {}
            if edit_data.existing_title is not None:
                query["title"] = edit_data.existing_title.strip()
            if edit_data.existing_details is not None:
                query["details"] = edit_data.existing_details.strip()
            if edit_data.existing_type is not None:
                query["type"] = edit_data.existing_type.strip()
            if edit_data.existing_horizon_date is not None:
                query["horizon_date"] = edit_data.existing_horizon_date

            # If no existing criteria provided, can't proceed
            if not query:
                raise ValueError("At least one existing field (title or details) must be provided to identify the horizon(s) to edit")

            # Build the update data
            update_data = {"updated_at": datetime.utcnow()}
            if edit_data.new_title is not None:
                update_data["title"] = edit_data.new_title.strip()
            if edit_data.new_details is not None:
                update_data["details"] = edit_data.new_details.strip()
            if edit_data.new_type is not None:
                update_data["type"] = edit_data.new_type.strip()
            if edit_data.new_horizon_date is not None:
                update_data["horizon_date"] = edit_data.new_horizon_date

            # If no new data provided, can't proceed
            if len(update_data) == 1:  # Only has updated_at
                raise ValueError("At least one new field (title or details) must be provided to update")

            # Update matching documents
            result = self.collection.update_many(query, {"$set": update_data})

            if result.matched_count == 0:
                return []  # No horizons found matching the criteria

            # Retrieve and return updated documents
            updated_query = {}
            if edit_data.new_title is not None:
                updated_query["title"] = edit_data.new_title.strip()
            elif edit_data.existing_title is not None:
                updated_query["title"] = edit_data.existing_title.strip()

            if edit_data.new_details is not None:
                updated_query["details"] = edit_data.new_details.strip()
            elif edit_data.existing_details is not None and edit_data.new_title is None:
                updated_query["details"] = edit_data.existing_details.strip()

            cursor = self.collection.find(updated_query).sort("updated_at", -1)
            updated_horizons = []

            for horizon_doc in cursor:
                updated_horizons.append(HorizonResponse(**horizon_doc))

            return updated_horizons

        except ValueError as e:
            raise e
        except PyMongoError as e:
            raise RuntimeError(f"Database error while editing horizons: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error editing horizons: {str(e)}")

# Global repository instance
horizon_repo = HorizonRepository()
