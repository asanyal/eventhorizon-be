"""
Pydantic models for API requests and responses
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, validator
from bson import ObjectId
import re

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
    details: Optional[str] = Field(default="", max_length=2000, description="Horizon details (optional)")
    type: str = Field(default="none", max_length=100, description="Horizon type")
    horizon_date: Optional[str] = Field(default=None, description="Optional date for the horizon item (YYYY-MM-DD format)")
    
    @validator('horizon_date')
    def validate_horizon_date(cls, v):
        if v is None:
            return v
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError('horizon_date must be in YYYY-MM-DD format')
        # Try to parse the date to ensure it's valid
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('horizon_date must be a valid date in YYYY-MM-DD format')
        return v

class HorizonResponse(BaseModel):
    """Model for horizon response"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    title: str
    details: Optional[str] = Field(default="", description="Horizon details (optional)")
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
    details: Optional[str] = Field(None, max_length=2000)
    type: Optional[str] = Field(None, max_length=100)
    horizon_date: Optional[str] = Field(None, description="Optional date for the horizon item (YYYY-MM-DD format)")

class HorizonEdit(BaseModel):
    """Model for editing a horizon item by existing criteria"""
    # Existing values to find the horizon
    existing_title: Optional[str] = Field(None, min_length=1, max_length=200, description="Current title to match")
    existing_details: Optional[str] = Field(None, max_length=2000, description="Current details to match")
    existing_type: Optional[str] = Field(None, max_length=100, description="Current type to match")
    existing_horizon_date: Optional[str] = Field(None, description="Current horizon date to match")
    
    # New values to update
    new_title: Optional[str] = Field(None, min_length=1, max_length=200, description="New title to set")
    new_details: Optional[str] = Field(None, max_length=2000, description="New details to set")
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

# ========== MEAL PREP MODELS ==========

class IngredientCreate(BaseModel):
    """Model for creating a new ingredient"""
    name: str = Field(..., min_length=1, max_length=200, description="Ingredient name")
    quantity: Optional[str] = Field(default=None, max_length=50, description="Quantity (optional)")
    unit: Optional[str] = Field(default=None, max_length=50, description="Unit (optional)")

class IngredientResponse(BaseModel):
    """Model for ingredient response"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str
    quantity: Optional[str] = None
    unit: Optional[str] = None
    created_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class MealCreate(BaseModel):
    """Model for creating a new meal"""
    name: str = Field(..., min_length=1, max_length=200, description="Meal name")
    ingredients: List[str] = Field(default_factory=list, description="List of ingredient names")

class MealResponse(BaseModel):
    """Model for meal response"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str
    ingredients: List[str]
    created_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class DayField(str, Enum):
    """Valid day fields for weekly meal plan"""
    SUNDAY_LUNCH = "sunday_lunch"
    TUESDAY_LUNCH = "tuesday_lunch"
    MONDAY_DINNER = "monday_dinner"
    WEDNESDAY_DINNER = "wednesday_dinner"

class WeeklyMealPlanCreate(BaseModel):
    """Model for creating/updating a weekly meal plan"""
    week_start_date: str = Field(..., description="Monday of the week in YYYY-MM-DD format")
    sunday_lunch: Optional[str] = Field(default=None, description="Meal ID for Sunday lunch")
    tuesday_lunch: Optional[str] = Field(default=None, description="Meal ID for Tuesday lunch")
    monday_dinner: Optional[str] = Field(default=None, description="Meal ID for Monday dinner")
    wednesday_dinner: Optional[str] = Field(default=None, description="Meal ID for Wednesday dinner")

    @validator('week_start_date')
    def validate_week_start_date(cls, v):
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError('week_start_date must be in YYYY-MM-DD format')
        try:
            date_obj = datetime.strptime(v, '%Y-%m-%d')
            # Verify it's a Monday (weekday() returns 0 for Monday)
            if date_obj.weekday() != 0:
                raise ValueError('week_start_date must be a Monday')
        except ValueError as e:
            if 'Monday' in str(e):
                raise
            raise ValueError('week_start_date must be a valid date in YYYY-MM-DD format')
        return v

class WeeklyMealPlanResponse(BaseModel):
    """Model for weekly meal plan response"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    week_start_date: str
    sunday_lunch: Optional[str] = None
    tuesday_lunch: Optional[str] = None
    monday_dinner: Optional[str] = None
    wednesday_dinner: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class UpdateMealSlotRequest(BaseModel):
    """Model for updating a specific meal slot"""
    week_start_date: str = Field(..., description="Monday of the week in YYYY-MM-DD format")
    day_field: DayField = Field(..., description="The day/meal field to update")
    meal_id: Optional[str] = Field(default=None, description="Meal ID or null to clear the slot")

    @validator('week_start_date')
    def validate_week_start_date(cls, v):
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError('week_start_date must be in YYYY-MM-DD format')
        try:
            date_obj = datetime.strptime(v, '%Y-%m-%d')
            if date_obj.weekday() != 0:
                raise ValueError('week_start_date must be a Monday')
        except ValueError as e:
            if 'Monday' in str(e):
                raise
            raise ValueError('week_start_date must be a valid date in YYYY-MM-DD format')
        return v
