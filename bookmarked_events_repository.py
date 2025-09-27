"""
Repository for bookmarked_events collection operations
"""

from datetime import datetime
from typing import List, Optional
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from bson import ObjectId

from database import db_config
from models import BookmarkEventCreate, BookmarkEventResponse

class BookmarkedEventsRepository:
    """Repository class for bookmarked_events collection operations"""
    
    def __init__(self):
        self.collection_name = "bookmarked_events"
        self._collection: Optional[Collection] = None
    
    @property
    def collection(self) -> Collection:
        """Get the bookmarked_events collection"""
        if self._collection is None:
            if db_config.database is None:
                raise RuntimeError("Database not connected")
            self._collection = db_config.get_collection(self.collection_name)
        return self._collection
    
    async def create_bookmarked_event(self, event_data: BookmarkEventCreate) -> BookmarkEventResponse:
        """Create a new bookmarked event"""
        try:
            # Prepare document for insertion
            now = datetime.utcnow()
            event_doc = {
                "date": event_data.date,
                "time": event_data.time,
                "event_title": event_data.event_title,
                "duration": event_data.duration,
                "attendees": event_data.attendees,
                "created_at": now,
                "updated_at": now
            }
            
            # Insert into MongoDB
            result = self.collection.insert_one(event_doc)
            
            # Retrieve the created document
            created_event = self.collection.find_one({"_id": result.inserted_id})
            
            if not created_event:
                raise RuntimeError("Failed to retrieve created bookmarked event")
            
            return BookmarkEventResponse(**created_event)
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while creating bookmarked event: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error creating bookmarked event: {str(e)}")
    
    async def get_all_bookmarked_events(self) -> List[BookmarkEventResponse]:
        """Get all bookmarked events"""
        try:
            # Retrieve all bookmarked events, sorted by created_at descending (newest first)
            cursor = self.collection.find({}).sort("created_at", -1)
            events = []
            
            for event_doc in cursor:
                events.append(BookmarkEventResponse(**event_doc))
            
            return events
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while retrieving bookmarked events: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving bookmarked events: {str(e)}")
    
    async def get_bookmarked_event_by_id(self, event_id: str) -> Optional[BookmarkEventResponse]:
        """Get a specific bookmarked event by ID"""
        try:
            if not ObjectId.is_valid(event_id):
                return None
            
            event_doc = self.collection.find_one({"_id": ObjectId(event_id)})
            
            if not event_doc:
                return None
            
            return BookmarkEventResponse(**event_doc)
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while retrieving bookmarked event: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving bookmarked event: {str(e)}")
    
    async def delete_bookmarked_event(self, event_id: str) -> bool:
        """Delete a bookmarked event"""
        try:
            if not ObjectId.is_valid(event_id):
                return False
            
            result = self.collection.delete_one({"_id": ObjectId(event_id)})
            return result.deleted_count > 0
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while deleting bookmarked event: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error deleting bookmarked event: {str(e)}")
    
    async def delete_bookmarked_event_by_title(self, event_title: str) -> int:
        """Delete bookmarked events by title (returns count of deleted items)"""
        try:
            if not event_title or not event_title.strip():
                return 0
            
            result = self.collection.delete_many({"event_title": event_title.strip()})
            return result.deleted_count
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while deleting bookmarked events by title: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error deleting bookmarked events by title: {str(e)}")
    
    async def get_bookmarked_events_by_date(self, date: str) -> List[BookmarkEventResponse]:
        """Get bookmarked events by date"""
        try:
            if not date or not date.strip():
                return []
            
            cursor = self.collection.find({"date": date.strip()}).sort("created_at", -1)
            events = []
            
            for event_doc in cursor:
                events.append(BookmarkEventResponse(**event_doc))
            
            return events
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while retrieving bookmarked events by date: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving bookmarked events by date: {str(e)}")

# Global repository instance
bookmarked_events_repo = BookmarkedEventsRepository()
