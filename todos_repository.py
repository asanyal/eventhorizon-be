"""
Repository for todos collection operations
"""

from datetime import datetime
from typing import List, Optional
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from bson import ObjectId

from database import db_config
from models import TodoCreate, TodoResponse, TodoUpdate

class TodosRepository:
    """Repository class for todos collection operations"""
    
    def __init__(self):
        self.collection_name = "todos"
        self._collection: Optional[Collection] = None
    
    @property
    def collection(self) -> Collection:
        """Get the todos collection"""
        if self._collection is None:
            if db_config.database is None:
                raise RuntimeError("Database not connected")
            self._collection = db_config.get_collection(self.collection_name)
        return self._collection
    
    async def create_todo(self, todo_data: TodoCreate) -> TodoResponse:
        """Create a new todo item"""
        try:
            # Prepare document for insertion
            now = datetime.utcnow()
            todo_doc = {
                "title": todo_data.title,
                "urgency": todo_data.urgency.value,
                "priority": todo_data.priority.value,
                "created_at": now,
                "updated_at": now
            }
            
            # Insert into MongoDB
            result = self.collection.insert_one(todo_doc)
            
            # Retrieve the created document
            created_todo = self.collection.find_one({"_id": result.inserted_id})
            
            if not created_todo:
                raise RuntimeError("Failed to retrieve created todo")
            
            return TodoResponse(**created_todo)
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while creating todo: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error creating todo: {str(e)}")
    
    async def get_all_todos(self) -> List[TodoResponse]:
        """Get all todo items"""
        try:
            # Retrieve all todos, sorted by created_at descending (newest first)
            cursor = self.collection.find({}).sort("created_at", -1)
            todos = []
            
            for todo_doc in cursor:
                todos.append(TodoResponse(**todo_doc))
            
            return todos
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while retrieving todos: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving todos: {str(e)}")
    
    async def get_todo_by_id(self, todo_id: str) -> Optional[TodoResponse]:
        """Get a specific todo by ID"""
        try:
            if not ObjectId.is_valid(todo_id):
                return None
            
            todo_doc = self.collection.find_one({"_id": ObjectId(todo_id)})
            
            if not todo_doc:
                return None
            
            return TodoResponse(**todo_doc)
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while retrieving todo: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving todo: {str(e)}")
    
    async def update_todo(self, todo_id: str, todo_data: TodoUpdate) -> Optional[TodoResponse]:
        """Update a todo item"""
        try:
            if not ObjectId.is_valid(todo_id):
                return None
            
            # Prepare update data
            update_data = {"updated_at": datetime.utcnow()}
            
            if todo_data.title is not None:
                update_data["title"] = todo_data.title
            if todo_data.urgency is not None:
                update_data["urgency"] = todo_data.urgency.value
            if todo_data.priority is not None:
                update_data["priority"] = todo_data.priority.value
            
            # Update the document
            result = self.collection.update_one(
                {"_id": ObjectId(todo_id)},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                return None
            
            # Retrieve and return updated document
            updated_todo = self.collection.find_one({"_id": ObjectId(todo_id)})
            return TodoResponse(**updated_todo) if updated_todo else None
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while updating todo: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error updating todo: {str(e)}")
    
    async def delete_todo(self, todo_id: str) -> bool:
        """Delete a todo item by ID"""
        try:
            if not ObjectId.is_valid(todo_id):
                return False
            
            result = self.collection.delete_one({"_id": ObjectId(todo_id)})
            return result.deleted_count > 0
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while deleting todo: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error deleting todo: {str(e)}")
    
    async def delete_todo_by_title(self, title: str) -> int:
        """Delete todo items by title (returns count of deleted items)"""
        try:
            if not title or not title.strip():
                return 0
            
            result = self.collection.delete_many({"title": title.strip()})
            return result.deleted_count
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while deleting todos by title: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error deleting todos by title: {str(e)}")
    
    async def get_todos_by_urgency(self, urgency: str) -> List[TodoResponse]:
        """Get todos filtered by urgency level"""
        try:
            cursor = self.collection.find({"urgency": urgency}).sort("created_at", -1)
            todos = []
            
            for todo_doc in cursor:
                todos.append(TodoResponse(**todo_doc))
            
            return todos
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while retrieving todos by urgency: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving todos by urgency: {str(e)}")
    
    async def get_todos_by_priority(self, priority: str) -> List[TodoResponse]:
        """Get todos filtered by priority level"""
        try:
            cursor = self.collection.find({"priority": priority}).sort("created_at", -1)
            todos = []
            
            for todo_doc in cursor:
                todos.append(TodoResponse(**todo_doc))
            
            return todos
            
        except PyMongoError as e:
            raise RuntimeError(f"Database error while retrieving todos by priority: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving todos by priority: {str(e)}")

# Global repository instance
todos_repo = TodosRepository()
