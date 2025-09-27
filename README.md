# Event Horizon Calendar & Todos API

A FastAPI server that provides Google Calendar events and todo management through REST API endpoints.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Google Calendar API Setup:**
   - Make sure you have `credentials.json` file in the project root (same as used by `analyze_cal.py`)
   - The server will handle OAuth authentication on startup and save tokens to `token.json`

3. **MongoDB Setup:**
   - Make sure your `.env` file contains your MongoDB connection details:
   ```bash
   MONGO_USER=your_username
   MONGO_PASS=your_password
   MONGO_CLUSTER=cluster0.xxxxx.mongodb.net
   MONGO_DB_NAME=your_database_name
   ```
   - The server will automatically connect to your MongoDB instance and create the `todos` collection

4. **Run the server:**
   ```bash
   python main.py
   ```
   
   Or using uvicorn directly:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## API Endpoints

### GET `/get-events`

Retrieves Google Calendar events between specified dates (inclusive).

**Parameters:**
- `start` (required): Start date in YYYY-MM-DD format
- `end` (required): End date in YYYY-MM-DD format

**Example Request:**
```bash
curl "http://localhost:8000/get-events?start=2024-01-15&end=2024-01-16"
```

**Example Response:**
```json
[
  {
    "event": "Team Meeting",
    "date": "Jan 15",
    "start_time": "9:00 AM",
    "end_time": "10:00 AM",
    "duration_minutes": 60,
    "time_until": "In 2h 30m",
    "attendees": [
      "john@company.com",
      "jane@company.com",
      "you@company.com"
    ],
    "organizer_email": "john@company.com"
  },
  {
    "event": "1:1 with John",
    "date": "Jan 15",
    "start_time": "2:00 PM",
    "end_time": "2:30 PM",
    "duration_minutes": 30,
    "time_until": "In 7h",
    "attendees": [
      "john@company.com",
      "you@company.com"
    ],
    "organizer_email": "you@company.com"
  }
]
```

### GET `/`

Returns API information and available endpoints.

### GET `/excluded-titles`

Returns a summary of all event titles that are filtered out from calendar results.

**Example Response:**
```json
{
  "message": "Event titles that are filtered out from calendar results",
  "excluded_titles": {
    "exact_matches": ["Block", "Refrain from scheduling | Ask before scheduling"],
    "partial_matches": [],
    "case_insensitive_partial_matches": []
  }
}
```

## Todos API Endpoints

### GET `/get-todos`

Retrieves all todo items, with optional filtering by urgency or priority.

**Parameters (optional):**
- `urgency` (optional): Filter by urgency level (`high` or `low`)
- `priority` (optional): Filter by priority level (`high` or `low`)

**Example Requests:**
```bash
# Get all todos
curl "http://localhost:8000/get-todos"

# Filter by high urgency
curl "http://localhost:8000/get-todos?urgency=high"

# Filter by low priority
curl "http://localhost:8000/get-todos?priority=low"

# Filter by both urgency and priority
curl "http://localhost:8000/get-todos?urgency=high&priority=high"
```

**Example Response:**
```json
[
  {
    "id": "60d5ec49f1b2c8b1a8e4e123",
    "title": "Complete project documentation",
    "urgency": "high",
    "priority": "high",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  },
  {
    "id": "60d5ec49f1b2c8b1a8e4e124",
    "title": "Review pull requests",
    "urgency": "low",
    "priority": "high",
    "created_at": "2024-01-15T09:15:00Z",
    "updated_at": "2024-01-15T09:15:00Z"
  }
]
```

### POST `/add-todos`

Creates a new todo item.

**Request Body:**
```json
{
  "title": "Complete project documentation",
  "urgency": "high",
  "priority": "high"
}
```

**Example Request:**
```bash
curl -X POST "http://localhost:8000/add-todos" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Complete project documentation",
    "urgency": "high",
    "priority": "high"
  }'
```

**Example Response:**
```json
{
  "id": "60d5ec49f1b2c8b1a8e4e123",
  "title": "Complete project documentation",
  "urgency": "high",
  "priority": "high",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### GET `/get-todos/{todo_id}`

Retrieves a specific todo by its ID.

**Example Request:**
```bash
curl "http://localhost:8000/get-todos/60d5ec49f1b2c8b1a8e4e123"
```

### DELETE `/delete-todo/{todo_id}`

Deletes a specific todo by its ID.

**Example Request:**
```bash
curl -X DELETE "http://localhost:8000/delete-todo/60d5ec49f1b2c8b1a8e4e123"
```

**Example Response:**
```json
{
  "message": "Todo deleted successfully",
  "deleted_id": "60d5ec49f1b2c8b1a8e4e123"
}
```

## Features

- **Authentication**: Handles Google Calendar OAuth authentication at server startup
- **Timezone**: Uses Pacific timezone (same as `analyze_cal.py`)
- **Clean JSON**: Returns structured data without color formatting codes
- **Error Handling**: Proper HTTP error responses for invalid dates or API failures
- **Smart Event Filtering**: Automatically excludes unwanted events based on configurable title rules
- **Time Calculations**: Provides human-readable time until each event
- **Attendees Information**: Includes attendee email addresses and organizer information
- **Todo Management**: Full CRUD operations for todo items with urgency and priority levels
- **MongoDB Integration**: Persistent storage with MongoDB Atlas or local MongoDB
- **Filtering & Querying**: Filter todos by urgency, priority, or both
- **CORS Support**: Configured to allow requests from `localhost:8080` web applications

## Event Filtering

The API automatically filters out certain events based on their titles. The filtering rules are managed in `exceptions.py`:

- **Exact matches**: Events with titles that exactly match excluded titles
- **Partial matches**: Events containing specific substrings (case-sensitive)
- **Case-insensitive partial matches**: Events containing specific substrings (case-insensitive)

**Currently excluded events:**
- "Block"
- "Refrain from scheduling | Ask before scheduling"

To add more exclusions, edit the `exceptions.py` file and restart the server.

## Notes

- The server needs to authenticate with Google Calendar API on first run
- Events are returned in chronological order
- Only events with specific times are included (all-day events are excluded)
- Past events are marked with "Past" in the `time_until` field
- Excluded events can be viewed via the `/excluded-titles` endpoint
