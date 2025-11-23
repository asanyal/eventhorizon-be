#!/usr/bin/env python3

import os
import json
import datetime
import hashlib
from dotenv import load_dotenv
from dateutil import parser
import pytz
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from exceptions import should_exclude_event, get_excluded_titles_summary
from database import db_config
from models import (
    TodoCreate, TodoResponse, UrgencyLevel, PriorityLevel,
    HorizonCreate, HorizonResponse, HorizonEdit,
    BookmarkEventCreate, BookmarkEventResponse,
    IngredientCreate, IngredientResponse,
    MealCreate, MealResponse,
    WeeklyMealPlanCreate, WeeklyMealPlanResponse, UpdateMealSlotRequest
)
from todos_repository import todos_repo
from horizon_repository import horizon_repo
from bookmarked_events_repository import bookmarked_events_repo
from ingredients_repository import ingredients_repo
from meals_repository import meals_repo
from weekly_meal_plans_repository import weekly_meal_plans_repo

load_dotenv()

# Constants
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Global variable to store credentials
calendar_service = None

# In-memory cache for Google Calendar API responses
# Format: {cache_key: (response_data, expiry_timestamp)}
# Using string literal for forward reference since CalendarEvent is defined later
calendar_cache: Dict[str, tuple[List[Any], float]] = {}
CACHE_TTL_SECONDS = 60  # Cache for 60 seconds

def get_cache_key(start: str, end: str) -> str:
    """Generate a cache key from start and end dates"""
    return hashlib.md5(f"{start}:{end}".encode()).hexdigest()

def get_cached_events(start: str, end: str) -> Optional[List[Any]]:
    """Get cached events if available and not expired"""
    cache_key = get_cache_key(start, end)
    if cache_key in calendar_cache:
        cached_data, expiry = calendar_cache[cache_key]
        if datetime.datetime.now().timestamp() < expiry:
            return cached_data
        else:
            # Remove expired entry
            del calendar_cache[cache_key]
    return None

def cache_events(start: str, end: str, events: List[Any]):
    """Cache events with TTL"""
    cache_key = get_cache_key(start, end)
    expiry = datetime.datetime.now().timestamp() + CACHE_TTL_SECONDS
    calendar_cache[cache_key] = (events, expiry)

class CalendarEvent(BaseModel):
    event: str
    date: str
    start_time: str
    end_time: str
    duration_minutes: int
    time_until: str
    attendees: List[str] = []  # List of attendee email addresses
    organizer_email: Optional[str] = None
    all_day: bool = False  # Indicates if this is an all-day event
    notes: Optional[str] = None  # Event description/notes from Google Calendar
    
    class Config:
        # Ensure all fields are included in JSON output, even if empty
        exclude_none = False

class HolidayEvent(BaseModel):
    name: str
    date: str
    time_until: str
    
    class Config:
        # Ensure all fields are included in JSON output, even if empty
        exclude_none = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    global calendar_service
    
    try:
        if os.getenv('GOOGLE_CREDENTIALS_JSON'):
            calendar_service = authenticate_google_calendar_envvars()
            print("✅ Google Calendar API: Successful Authentication (envvars)")
        else:
            calendar_service = authenticate_google_calendar()
            print("✅ Google Calendar API: Successful Authentication (JSON File)")
    except Exception as e:
        print(f"❌ Failed to authenticate Google Calendar API: {e}")
        raise e
    
    try:
        db_config.connect()
        print("✅ MongoDB connected successfully")
        # Ensure indexes are created for optimal query performance
        db_config.ensure_indexes()
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        raise e

    yield
    
    db_config.disconnect()
    print("🔄 Shutting down...")

app = FastAPI(
    title="Event Horizon Calendar API", 
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://eventhorizon-ui.replit.app",  # Production frontend
        "https://eventhorizon-api.replit.app"  # Production backend (for self-calls if needed)
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Add custom exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: FastAPIRequest, exc: RequestValidationError):
    """Custom handler for request validation errors to provide better error messages"""
    error_details = []
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        error_details.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"],
            "input": error.get("input")
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "errors": error_details,
            "hint": "For /add-horizon endpoint, make sure to include 'title' in the request body (details is optional)"
        }
    )

def authenticate_google_calendar():
    creds = None
    script_dir = os.path.dirname(os.path.abspath(__file__))
    token_json = os.path.join(script_dir, "token.json")
    api_credentials_json = os.path.join(script_dir, "credentials.json")
    
    if os.path.exists(token_json):
        creds = Credentials.from_authorized_user_file(token_json, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(api_credentials_json):
                raise FileNotFoundError("credentials.json file not found. Please add your Google Calendar API credentials.")
            flow = InstalledAppFlow.from_client_secrets_file(api_credentials_json, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(token_json, 'w') as token:
            token.write(creds.to_json())
    
    return googleapiclient.discovery.build('calendar', 'v3', credentials=creds)

def authenticate_google_calendar_envvars():
    """
    Handle Google Calendar API authentication using environment variables
    Secure for deployment on platforms like Replit without storing files in repo
    
    Required Environment Variables:
    - GOOGLE_CREDENTIALS_JSON: Content of credentials.json file
    - GOOGLE_TOKEN_JSON: Content of token.json file (optional, will be created)
    - GOOGLE_AUTH_CODE: Authorization code from OAuth flow (for initial setup)
    """
    google_credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
    google_token_json = os.getenv('GOOGLE_TOKEN_JSON')
    
    if not google_credentials_json:
        raise ValueError("GOOGLE_CREDENTIALS_JSON environment variable not found. Please set it with your credentials.json content.")
    
    creds = None
    
    if google_token_json:
        try:
            token_info = json.loads(google_token_json)
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Could not parse GOOGLE_TOKEN_JSON: {e}")
            creds = None
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("✅ Google Calendar token refreshed successfully")
                
                os.environ['GOOGLE_TOKEN_JSON'] = creds.to_json()
                
            except Exception as e:
                print(f"❌ Failed to refresh token: {e}")
                creds = None
        
        if not creds or not creds.valid:
            try:
                credentials_info = json.loads(google_credentials_json)
                
                flow = InstalledAppFlow.from_client_config(credentials_info, SCOPES)
                
                print("🔗 Please visit this URL to authorize the application:")
                auth_url, _ = flow.authorization_url(prompt='consent')
                print(auth_url)
                print("\nAfter authorization, you'll get a code. Please set it as GOOGLE_AUTH_CODE environment variable and restart.")
                
                # Check if auth code is provided
                auth_code = os.getenv('GOOGLE_AUTH_CODE')
                if auth_code:
                    # Exchange auth code for credentials
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                    
                    os.environ['GOOGLE_TOKEN_JSON'] = creds.to_json()
                    print("✅ Google Calendar authenticated successfully with auth code")
                else:
                    raise ValueError("GOOGLE_AUTH_CODE environment variable not found. Please complete OAuth flow first.")
                    
            except json.JSONDecodeError:
                raise ValueError("GOOGLE_CREDENTIALS_JSON contains invalid JSON. Please check the format.")
            except Exception as e:
                raise RuntimeError(f"Failed to authenticate with Google Calendar: {str(e)}")
    
    return googleapiclient.discovery.build('calendar', 'v3', credentials=creds)

def format_date(date_str: str) -> str:
    """Format date to a readable format"""
    datetime_obj = parser.isoparse(date_str)
    return datetime_obj.strftime("%b %-d")

def get_start_end_times(start_str: str, end_str: str) -> tuple:
    """Get formatted start and end times in Pacific timezone"""
    start_date = parser.isoparse(start_str)
    end_date = parser.isoparse(end_str)
    pacific_tz = pytz.timezone('US/Pacific')
    
    start_pacific = start_date.astimezone(pacific_tz)
    end_pacific = end_date.astimezone(pacific_tz)
    
    start_time = start_pacific.strftime('%I:%M %p').lstrip('0').replace(' 0', ' ')
    end_time = end_pacific.strftime('%I:%M %p').lstrip('0').replace(' 0', ' ')
    
    return start_time, end_time

def calculate_duration_in_minutes(start_str: str, end_str: str) -> int:
    """Calculate duration between two dates in minutes"""
    start_date = parser.isoparse(start_str)
    end_date = parser.isoparse(end_str)
    duration = abs(end_date - start_date)
    return int(duration.total_seconds() // 60)

def get_time_until_event(event_time: str) -> str:
    """Calculate time until event in a human-readable format"""
    now = datetime.datetime.now(pytz.UTC)
    event_datetime = parser.isoparse(event_time)
    time_diff = event_datetime - now
    
    # If event is in the past, return "Past"
    if time_diff.total_seconds() < 0:
        return "Past"
    
    days = time_diff.days
    hours = time_diff.seconds // 3600
    minutes = (time_diff.seconds % 3600) // 60
    
    if days > 0:
        return f"In {days}d {hours}h"
    elif hours > 0:
        return f"In {hours}h {minutes}m"
    else:
        return f"In {minutes}m"

def parse_date_string(date_str: str) -> datetime.datetime:
    """Parse simple date string (YYYY-MM-DD) to datetime with Pacific timezone"""
    try:
        # Parse the date string
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        # Set timezone to Pacific
        pacific_tz = pytz.timezone('US/Pacific')
        return pacific_tz.localize(date_obj)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Expected format: YYYY-MM-DD")

def format_all_day_date(date_str: str) -> str:
    """Format all-day event date to a readable format"""
    try:
        # Parse the date string (format: YYYY-MM-DD)
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%b %-d")
    except ValueError:
        # Fallback to original string if parsing fails
        return date_str

def get_time_until_all_day_event(date_str: str) -> str:
    """Calculate time until all-day event"""
    try:
        # Parse the date and set to start of day in Pacific timezone
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        pacific_tz = pytz.timezone('US/Pacific')
        event_date = pacific_tz.localize(date_obj)
        
        # Compare with current time
        now = datetime.datetime.now(pytz.UTC)
        time_diff = event_date.astimezone(pytz.UTC) - now
        
        # If event is in the past, return "Past"
        if time_diff.total_seconds() < 0:
            return "Past"
        
        days = time_diff.days
        hours = time_diff.seconds // 3600
        
        if days > 0:
            return f"In {days}d {hours}h"
        elif hours > 0:
            return f"In {hours}h"
        else:
            return "Today"
    except ValueError:
        return "Unknown"


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Event Horizon Calendar & Todos API",
        "version": "1.0.0",
        "endpoints": {
            "get-events": "/get-events?start=YYYY-MM-DD&end=YYYY-MM-DD",
            "get-holidays": "/get-holidays?date=YYYY-MM-DD",
            "excluded-titles": "/excluded-titles",
            "get-todos": "/get-todos",
            "add-todos": "/add-todos",
            "delete-todo-by-title": "/delete-todo-by-title?title=TITLE",
            "get-horizon": "/get-horizon?horizon_date=YYYY-MM-DD",
            "add-horizon": "/add-horizon?type=TYPE&horizon_date=YYYY-MM-DD",
            "edit-horizon": "/edit-horizon",
            "delete-horizon-by-title": "/delete-horizon-by-title?title=TITLE",
            "get-bookmark-events": "/get-bookmark-events?date=YYYY-MM-DD",
            "add-bookmark-event": "/add-bookmark-event",
            "delete-bookmark-event-by-title": "/delete-bookmark-event-by-title?event_title=TITLE"
        }
    }

@app.get("/excluded-titles")
async def get_excluded_titles():
    """Get a summary of all excluded event titles"""
    return {
        "message": "Event titles that are filtered out from calendar results",
        "excluded_titles": get_excluded_titles_summary()
    }

@app.get("/get-events", response_model=List[CalendarEvent])
async def get_events(
    start: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end: str = Query(..., description="End date in YYYY-MM-DD format")
) -> List[CalendarEvent]:
    """
    Get Google Calendar events between start and end dates (inclusive)

    Args:
        start: Start date in YYYY-MM-DD format
        end: End date in YYYY-MM-DD format

    Returns:
        List of calendar events with event details, timing, and duration
    """
    global calendar_service

    if not calendar_service:
        raise HTTPException(status_code=500, detail="Google Calendar service not initialized")

    # Check cache first
    cached_events = get_cached_events(start, end)
    if cached_events is not None:
        return cached_events

    # Parse and validate dates
    start_datetime = parse_date_string(start)
    end_datetime = parse_date_string(end)
    
    # Set start to beginning of day and end to end of day
    start_datetime = start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    end_datetime = end_datetime.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Validate date range
    if start_datetime > end_datetime:
        raise HTTPException(status_code=400, detail="Start date must be before or equal to end date")
    
    try:
        # Fetch events from Google Calendar
        events_result = calendar_service.events().list(
            calendarId='primary',
            timeMin=start_datetime.isoformat(),
            timeMax=end_datetime.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        # Helper function to extract attendees efficiently
        def extract_attendees(event):
            return [
                attendee.get('email', '')
                for attendee in event.get('attendees', [])
                if attendee.get('email', '')
            ]

        # Helper function to process a single event
        def process_event(event):
            # Skip events based on exclusion rules
            event_title = event.get('summary', '')
            if should_exclude_event(event_title):
                return None

            # Extract common information
            attendees_list = extract_attendees(event)
            organizer_email = event.get('organizer', {}).get('email')
            notes = event.get('description', None)

            # Process regular events with dateTime
            if 'dateTime' in event['start']:
                start_dt = event['start']['dateTime']
                end_dt = event['end']['dateTime']
                start_time, end_time = get_start_end_times(start_dt, end_dt)

                return CalendarEvent(
                    event=event_title,
                    date=format_date(start_dt),
                    start_time=start_time,
                    end_time=end_time,
                    duration_minutes=calculate_duration_in_minutes(start_dt, end_dt),
                    time_until=get_time_until_event(start_dt),
                    attendees=attendees_list,
                    organizer_email=organizer_email,
                    all_day=False,
                    notes=notes
                )

            # Process all-day events with date only
            elif 'date' in event['start']:
                start_date_str = event['start']['date']
                end_date_str = event['end']['date']

                # Calculate duration for multi-day events
                start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
                end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
                duration_days = (end_date - start_date).days
                duration_minutes = duration_days * 24 * 60 if duration_days > 0 else 24 * 60

                return CalendarEvent(
                    event=event_title,
                    date=format_all_day_date(start_date_str),
                    start_time="All Day",
                    end_time="All Day",
                    duration_minutes=duration_minutes,
                    time_until=get_time_until_all_day_event(start_date_str),
                    attendees=attendees_list,
                    organizer_email=organizer_email,
                    all_day=True,
                    notes=notes
                )

            return None

        # Process all events and filter out None values (excluded events)
        formatted_events = [
            processed_event
            for event in events
            if (processed_event := process_event(event)) is not None
        ]

        # Cache the results before returning
        cache_events(start, end, formatted_events)

        return formatted_events
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch calendar events: {str(e)}")

@app.get("/get-holidays", response_model=List[HolidayEvent])
async def get_holidays(
    date: str = Query(..., description="Start date in YYYY-MM-DD format to get holidays on or after this date")
) -> List[HolidayEvent]:
    """
    Get US holidays from the "Holidays in United States" calendar on or after the specified date,
    limited to the next 12 months (365 days) from the start date
    
    Args:
        date: Start date in YYYY-MM-DD format
    
    Returns:
        List of holiday events with name, date, and time until (within next 365 days)
    """
    global calendar_service
    
    if not calendar_service:
        raise HTTPException(status_code=500, detail="Google Calendar service not initialized")
    
    # Parse and validate date
    start_datetime = parse_date_string(date)
    
    # Set start to beginning of day
    start_datetime = start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate end date (365 days from start date)
    end_datetime = start_datetime + datetime.timedelta(days=365)
    end_datetime = end_datetime.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    try:
        # Fetch holidays from the US Holidays calendar
        # Calendar ID for "Holidays in United States"
        holidays_calendar_id = 'en.usa#holiday@group.v.calendar.google.com'
        
        events_result = calendar_service.events().list(
            calendarId=holidays_calendar_id,
            timeMin=start_datetime.isoformat(),
            timeMax=end_datetime.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        formatted_holidays = []
        for event in events:
            holiday_name = event.get('summary', '')
            
            # Process all-day holiday events (holidays are typically all-day events)
            if 'date' in event['start']:
                holiday_date = format_all_day_date(event['start']['date'])
                time_until = get_time_until_all_day_event(event['start']['date'])
                
                formatted_holidays.append(HolidayEvent(
                    name=holiday_name,
                    date=holiday_date,
                    time_until=time_until
                ))
            # Handle regular events with dateTime (just in case)
            elif 'dateTime' in event['start']:
                holiday_date = format_date(event['start']['dateTime'])
                time_until = get_time_until_event(event['start']['dateTime'])
                
                formatted_holidays.append(HolidayEvent(
                    name=holiday_name,
                    date=holiday_date,
                    time_until=time_until
                ))
        
        return formatted_holidays
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch holidays: {str(e)}")

# Todos API Endpoints

@app.get("/get-todos", response_model=List[TodoResponse])
async def get_todos(
    urgency: Optional[UrgencyLevel] = Query(None, description="Filter by urgency level"),
    priority: Optional[PriorityLevel] = Query(None, description="Filter by priority level")
):
    """
    Get all todos, optionally filtered by urgency or priority
    
    Args:
        urgency: Optional urgency filter (high/low)
        priority: Optional priority filter (high/low)
    
    Returns:
        List of todos matching the filters
    """
    try:
        # Pass filters directly to repository for database-level filtering
        urgency_value = urgency.value if urgency else None
        priority_value = priority.value if priority else None
        return await todos_repo.get_all_todos(urgency=urgency_value, priority=priority_value)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve todos: {str(e)}")

@app.post("/add-todos", response_model=TodoResponse)
async def add_todo(todo_data: TodoCreate):
    """
    Add a new todo item
    
    Args:
        todo_data: Todo information including title, urgency, and priority
    
    Returns:
        The created todo with generated ID and timestamps
    """
    try:
        return await todos_repo.create_todo(todo_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create todo: {str(e)}")

@app.get("/get-todos/{todo_id}", response_model=TodoResponse)
async def get_todo_by_id(todo_id: str):
    """
    Get a specific todo by ID
    
    Args:
        todo_id: The MongoDB ObjectId of the todo
    
    Returns:
        The todo item if found
    """
    try:
        todo = await todos_repo.get_todo_by_id(todo_id)
        if not todo:
            raise HTTPException(status_code=404, detail="Todo not found")
        return todo
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve todo: {str(e)}")

@app.delete("/delete-todo/{todo_id}")
async def delete_todo(todo_id: str):
    """
    Delete a todo item by ID
    
    Args:
        todo_id: The MongoDB ObjectId of the todo to delete
    
    Returns:
        Success message
    """
    try:
        success = await todos_repo.delete_todo(todo_id)
        if not success:
            raise HTTPException(status_code=404, detail="Todo not found")
        
        return {"message": "Todo deleted successfully", "deleted_id": todo_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete todo: {str(e)}")

@app.delete("/delete-todo-by-title")
async def delete_todo_by_title(title: str = Query(..., description="Title of the todo(s) to delete")):
    """
    Delete todo items by title
    
    Args:
        title: The title of the todo(s) to delete (query parameter)
    
    Returns:
        Success message with count of deleted items
    """
    try:
        deleted_count = await todos_repo.delete_todo_by_title(title)
        
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"No todos found with title: '{title}'")
        
        return {
            "message": f"Successfully deleted {deleted_count} todo(s)",
            "deleted_count": deleted_count,
            "title": title
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete todos by title: {str(e)}")

# Horizon API Endpoints

@app.get("/get-horizon", response_model=List[HorizonResponse])
async def get_horizons(
    horizon_date: Optional[str] = Query(default=None, description="Filter by horizon date (YYYY-MM-DD format)")
):
    """
    Get all horizon items, optionally filtered by horizon date
    
    Args:
        horizon_date: Optional date filter (YYYY-MM-DD format)
    
    Returns:
        List of horizon items sorted by creation date (newest first)
    """
    try:
        # Pass horizon_date filter directly to repository for database-level filtering
        return await horizon_repo.get_all_horizons(horizon_date=horizon_date)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve horizons: {str(e)}")

@app.post("/add-horizon", response_model=HorizonResponse)
async def add_horizon(
    horizon_data: HorizonCreate,
    type: str = Query(default="none", description="Horizon type", max_length=100),
    horizon_date: Optional[str] = Query(default=None, description="Optional date for the horizon item (YYYY-MM-DD format)")
):
    """
    Add a new horizon item
    
    Args:
        horizon_data: Request body containing title (required) and details (optional)
        type: Horizon type (query parameter)
        horizon_date: Optional date in YYYY-MM-DD format (query parameter)
    
    Request body example:
        {
            "title": "My horizon title",
            "details": "Detailed description of the horizon"
        }
    
    Returns:
        The created horizon with generated ID and timestamps
    """
    try:
        # Override the type and horizon_date from query parameters
        horizon_data.type = type
        
        # Handle the case where horizon_date is passed as string "null" or other null-like values
        if horizon_date in ["null", "None", "undefined", ""] or horizon_date is None:
            horizon_data.horizon_date = None
        else:
            horizon_data.horizon_date = horizon_date
        
        return await horizon_repo.create_horizon(horizon_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create horizon: {str(e)}")

@app.get("/get-horizon/{horizon_id}", response_model=HorizonResponse)
async def get_horizon_by_id(horizon_id: str):
    """
    Get a specific horizon by ID
    
    Args:
        horizon_id: The MongoDB ObjectId of the horizon
    
    Returns:
        The horizon item if found
    """
    try:
        horizon = await horizon_repo.get_horizon_by_id(horizon_id)
        if not horizon:
            raise HTTPException(status_code=404, detail="Horizon not found")
        return horizon
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve horizon: {str(e)}")

@app.delete("/delete-horizon-by-title")
async def delete_horizon_by_title(title: str = Query(..., description="Title of the horizon(s) to delete")):
    """
    Delete horizon items by title
    
    Args:
        title: The title of the horizon(s) to delete (query parameter)
    
    Returns:
        Success message with count of deleted items
    """
    try:
        deleted_count = await horizon_repo.delete_horizon_by_title(title)
        
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"No horizons found with title: '{title}'")
        
        return {
            "message": f"Successfully deleted {deleted_count} horizon(s)",
            "deleted_count": deleted_count,
            "title": title
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete horizons by title: {str(e)}")

@app.delete("/delete-horizon/{horizon_id}")
async def delete_horizon(horizon_id: str):
    """
    Delete a horizon item by ID
    
    Args:
        horizon_id: The MongoDB ObjectId of the horizon to delete
    
    Returns:
        Success message
    """
    try:
        success = await horizon_repo.delete_horizon(horizon_id)
        if not success:
            raise HTTPException(status_code=404, detail="Horizon not found")
        
        return {"message": "Horizon deleted successfully", "deleted_id": horizon_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete horizon: {str(e)}")

@app.put("/edit-horizon", response_model=List[HorizonResponse])
async def edit_horizon(edit_data: HorizonEdit):
    """
    Edit horizon items by existing criteria
    
    Args:
        edit_data: Contains existing criteria to match and new values to update
        
    Request body should include:
        - existing_title and/or existing_details: to identify which horizon(s) to edit
        - new_title and/or new_details: the new values to set
    
    Returns:
        List of updated horizon items
    """
    try:
        updated_horizons = await horizon_repo.edit_horizon_by_criteria(edit_data)
        
        if not updated_horizons:
            raise HTTPException(
                status_code=404, 
                detail="No horizons found matching the provided existing criteria"
            )
        
        return updated_horizons
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to edit horizon: {str(e)}")

# Bookmarked Events API Endpoints

@app.get("/get-bookmark-events", response_model=List[BookmarkEventResponse])
async def get_bookmarked_events(
    date: Optional[str] = Query(default=None, description="Filter by event date (YYYY-MM-DD format)")
):
    """
    Get all bookmarked events, optionally filtered by date
    
    Args:
        date: Optional date filter (YYYY-MM-DD format)
    
    Returns:
        List of bookmarked events sorted by creation date (newest first)
    """
    try:
        if date:
            return await bookmarked_events_repo.get_bookmarked_events_by_date(date)
        else:
            return await bookmarked_events_repo.get_all_bookmarked_events()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve bookmarked events: {str(e)}")

@app.post("/add-bookmark-event", response_model=BookmarkEventResponse)
async def add_bookmarked_event(event_data: BookmarkEventCreate):
    """
    Add a new bookmarked event
    
    Args:
        event_data: Bookmarked event information including date, time, title, duration, and attendees
    
    Returns:
        The created bookmarked event with generated ID and timestamps
    """
    try:
        return await bookmarked_events_repo.create_bookmarked_event(event_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create bookmarked event: {str(e)}")

@app.get("/get-bookmark-event/{event_id}", response_model=BookmarkEventResponse)
async def get_bookmarked_event_by_id(event_id: str):
    """
    Get a specific bookmarked event by ID
    
    Args:
        event_id: The MongoDB ObjectId of the bookmarked event
    
    Returns:
        The bookmarked event if found
    """
    try:
        event = await bookmarked_events_repo.get_bookmarked_event_by_id(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Bookmarked event not found")
        return event
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve bookmarked event: {str(e)}")

@app.delete("/delete-bookmark-event/{event_id}")
async def delete_bookmarked_event(event_id: str):
    """
    Delete a bookmarked event by ID
    
    Args:
        event_id: The MongoDB ObjectId of the bookmarked event to delete
    
    Returns:
        Success message
    """
    try:
        success = await bookmarked_events_repo.delete_bookmarked_event(event_id)
        if not success:
            raise HTTPException(status_code=404, detail="Bookmarked event not found")
        
        return {"message": "Bookmarked event deleted successfully", "deleted_id": event_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete bookmarked event: {str(e)}")

@app.delete("/delete-bookmark-event-by-title")
async def delete_bookmarked_event_by_title(event_title: str = Query(..., description="Title of the bookmarked event(s) to delete")):
    """
    Delete bookmarked events by title
    
    Args:
        event_title: The title of the bookmarked event(s) to delete (query parameter)
    
    Returns:
        Success message with count of deleted items
    """
    try:
        deleted_count = await bookmarked_events_repo.delete_bookmarked_event_by_title(event_title)
        
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"No bookmarked events found with title: '{event_title}'")
        
        return {
            "message": f"Successfully deleted {deleted_count} bookmarked event(s)",
            "deleted_count": deleted_count,
            "event_title": event_title
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete bookmarked events by title: {str(e)}")

# ========== MEAL PREP API ENDPOINTS ==========

# Ingredients API Endpoints

@app.get("/get-ingredients", response_model=List[IngredientResponse])
async def get_ingredients():
    """
    Get all ingredients

    Returns:
        List of all ingredients
    """
    try:
        return await ingredients_repo.get_all_ingredients()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve ingredients: {str(e)}")

@app.post("/add-ingredient", response_model=IngredientResponse)
async def add_ingredient(ingredient_data: IngredientCreate):
    """
    Add a new ingredient

    Args:
        ingredient_data: Ingredient information including name, quantity, and unit

    Returns:
        The created ingredient with generated ID and timestamp
    """
    try:
        return await ingredients_repo.create_ingredient(ingredient_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create ingredient: {str(e)}")

@app.delete("/delete-ingredient/{ingredient_id}")
async def delete_ingredient(ingredient_id: str):
    """
    Delete an ingredient by ID

    Args:
        ingredient_id: The MongoDB ObjectId of the ingredient to delete

    Returns:
        Success message
    """
    try:
        success = await ingredients_repo.delete_ingredient(ingredient_id)
        if not success:
            raise HTTPException(status_code=404, detail="Ingredient not found")

        return {"message": "Ingredient deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete ingredient: {str(e)}")

# Meals API Endpoints

@app.get("/get-meals", response_model=List[MealResponse])
async def get_meals():
    """
    Get all meals

    Returns:
        List of all meals with their ingredients
    """
    try:
        return await meals_repo.get_all_meals()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve meals: {str(e)}")

@app.post("/add-meal", response_model=MealResponse)
async def add_meal(meal_data: MealCreate):
    """
    Add a new meal

    Args:
        meal_data: Meal information including name and ingredients list

    Returns:
        The created meal with generated ID and timestamp
    """
    try:
        return await meals_repo.create_meal(meal_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create meal: {str(e)}")

@app.delete("/delete-meal/{meal_id}")
async def delete_meal(meal_id: str):
    """
    Delete a meal by ID

    Args:
        meal_id: The MongoDB ObjectId of the meal to delete

    Returns:
        Success message
    """
    try:
        success = await meals_repo.delete_meal(meal_id)
        if not success:
            raise HTTPException(status_code=404, detail="Meal not found")

        return {"message": "Meal deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete meal: {str(e)}")

# Weekly Meal Plan API Endpoints

@app.get("/get-weekly-meal-plan", response_model=WeeklyMealPlanResponse)
async def get_weekly_meal_plan(week_start_date: str = Query(..., description="Monday of the week in YYYY-MM-DD format")):
    """
    Get a weekly meal plan by week start date

    Args:
        week_start_date: Monday of the week in YYYY-MM-DD format

    Returns:
        The weekly meal plan (creates empty plan if none exists)
    """
    try:
        plan = await weekly_meal_plans_repo.get_weekly_meal_plan(week_start_date)
        if not plan:
            # Return empty meal plan structure instead of 404
            from datetime import datetime
            now = datetime.utcnow()
            return WeeklyMealPlanResponse(
                week_start_date=week_start_date,
                sunday_lunch=None,
                tuesday_lunch=None,
                monday_dinner=None,
                wednesday_dinner=None,
                created_at=now,
                updated_at=now
            )
        return plan
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve weekly meal plan: {str(e)}")

@app.post("/upsert-weekly-meal-plan", response_model=WeeklyMealPlanResponse)
async def upsert_weekly_meal_plan(plan_data: WeeklyMealPlanCreate):
    """
    Create or update a weekly meal plan (upsert operation)

    Args:
        plan_data: Weekly meal plan data including week_start_date and meal slots

    Returns:
        The created or updated weekly meal plan
    """
    try:
        return await weekly_meal_plans_repo.upsert_weekly_meal_plan(plan_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upsert weekly meal plan: {str(e)}")

@app.patch("/update-meal-slot", response_model=WeeklyMealPlanResponse)
async def update_meal_slot(update_data: UpdateMealSlotRequest):
    """
    Update a specific meal slot in the weekly plan

    Args:
        update_data: Update data including week_start_date, day_field, and meal_id

    Returns:
        The updated weekly meal plan
    """
    try:
        return await weekly_meal_plans_repo.update_meal_slot(update_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update meal slot: {str(e)}")

@app.delete("/delete-weekly-meal-plan")
async def delete_weekly_meal_plan(week_start_date: str = Query(..., description="Monday of the week in YYYY-MM-DD format")):
    """
    Delete a weekly meal plan by week start date

    Args:
        week_start_date: Monday of the week in YYYY-MM-DD format

    Returns:
        Success message
    """
    try:
        success = await weekly_meal_plans_repo.delete_weekly_meal_plan(week_start_date)
        if not success:
            raise HTTPException(status_code=404, detail="Weekly meal plan not found")

        return {"message": "Weekly meal plan deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete weekly meal plan: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
