"""
Pydantic models for API requests and responses
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field
from bson import ObjectId

class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic v2"""
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")
        return field_schema

class UrgencyLevel(str, Enum):
    """Urgency levels for todos"""
    HIGH = "high"
    LOW = "low"

class PriorityLevel(str, Enum):
    """Priority levels for todos"""
    HIGH = "high"
    LOW = "low"

class TodoCreate(BaseModel):
    """Model for creating a new todo"""
    title: str = Field(..., min_length=1, max_length=200, description="Todo title")
    urgency: UrgencyLevel = Field(..., description="Urgency level (high/low)")
    priority: PriorityLevel = Field(..., description="Priority level (high/low)")

class TodoResponse(BaseModel):
    """Model for todo response"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    title: str
    urgency: UrgencyLevel
    priority: PriorityLevel
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class TodoUpdate(BaseModel):
    """Model for updating a todo"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    urgency: Optional[UrgencyLevel] = None
    priority: Optional[PriorityLevel] = None

class HorizonCreate(BaseModel):
    """Model for creating a new horizon item"""
    title: str = Field(..., min_length=1, max_length=200, description="Horizon title")
    details: str = Field(..., min_length=1, max_length=2000, description="Horizon details")
    type: str = Field(default="none", max_length=100, description="Horizon type")
    horizon_date: Optional[str] = Field(default=None, description="Optional date for the horizon item (YYYY-MM-DD format)")

class HorizonResponse(BaseModel):
    """Model for horizon response"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    title: str
    details: str
    type: str = Field(default="none", description="Horizon type")
    horizon_date: Optional[str] = Field(default=None, description="Optional date for the horizon item (YYYY-MM-DD format)")
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class HorizonUpdate(BaseModel):
    """Model for updating a horizon item"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    details: Optional[str] = Field(None, min_length=1, max_length=2000)
    type: Optional[str] = Field(None, max_length=100)
    horizon_date: Optional[str] = Field(None, description="Optional date for the horizon item (YYYY-MM-DD format)")

class HorizonEdit(BaseModel):
    """Model for editing a horizon item by existing criteria"""
    # Existing values to find the horizon
    existing_title: Optional[str] = Field(None, min_length=1, max_length=200, description="Current title to match")
    existing_details: Optional[str] = Field(None, min_length=1, max_length=2000, description="Current details to match")
    existing_type: Optional[str] = Field(None, max_length=100, description="Current type to match")
    existing_horizon_date: Optional[str] = Field(None, description="Current horizon date to match")
    
    # New values to update
    new_title: Optional[str] = Field(None, min_length=1, max_length=200, description="New title to set")
    new_details: Optional[str] = Field(None, min_length=1, max_length=2000, description="New details to set")
    new_type: Optional[str] = Field(None, max_length=100, description="New type to set")
    new_horizon_date: Optional[str] = Field(None, description="New horizon date to set")

class BookmarkEventCreate(BaseModel):
    """Model for creating a new bookmarked event"""
    date: str = Field(..., description="Event date (YYYY-MM-DD format)")
    time: str = Field(..., description="Event time (e.g., '2:30 PM - 3:30 PM')")
    event_title: str = Field(..., min_length=1, max_length=500, description="Event title")
    duration: int = Field(..., gt=0, description="Event duration in minutes")
    attendees: List[str] = Field(default_factory=list, description="List of attendee email addresses")

class BookmarkEventResponse(BaseModel):
    """Model for bookmarked event response"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    date: str
    time: str
    event_title: str
    duration: int
    attendees: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
