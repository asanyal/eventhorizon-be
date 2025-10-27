"""
Repository for meals collection operations
"""

from datetime import datetime
from typing import List, Optional
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from bson import ObjectId

from database import db_config
from models import MealCreate, MealResponse

class MealsRepository:
    """Repository class for meals collection operations"""

    def __init__(self):
        self.collection_name = "meals"
        self._collection: Optional[Collection] = None

    @property
    def collection(self) -> Collection:
        """Get the meals collection"""
        if self._collection is None:
            if db_config.database is None:
                raise RuntimeError("Database not connected")
            self._collection = db_config.get_collection(self.collection_name)
        return self._collection

    async def create_meal(self, meal_data: MealCreate) -> MealResponse:
        """Create a new meal"""
        try:
            # Prepare document for insertion
            now = datetime.utcnow()
            meal_doc = {
                "name": meal_data.name,
                "ingredients": meal_data.ingredients,
                "created_at": now
            }

            # Insert into MongoDB
            result = self.collection.insert_one(meal_doc)

            # Retrieve the created document
            created_meal = self.collection.find_one({"_id": result.inserted_id})

            if not created_meal:
                raise RuntimeError("Failed to retrieve created meal")

            return MealResponse(**created_meal)

        except PyMongoError as e:
            raise RuntimeError(f"Database error while creating meal: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error creating meal: {str(e)}")

    async def get_all_meals(self) -> List[MealResponse]:
        """Get all meals"""
        try:
            # Retrieve meals sorted by created_at descending (newest first)
            cursor = self.collection.find({}).sort("created_at", -1)

            # Use list comprehension for better performance
            meals = [MealResponse(**meal_doc) for meal_doc in cursor]

            return meals

        except PyMongoError as e:
            raise RuntimeError(f"Database error while retrieving meals: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving meals: {str(e)}")

    async def delete_meal(self, meal_id: str) -> bool:
        """Delete a meal by ID"""
        try:
            if not ObjectId.is_valid(meal_id):
                return False

            result = self.collection.delete_one({"_id": ObjectId(meal_id)})
            return result.deleted_count > 0

        except PyMongoError as e:
            raise RuntimeError(f"Database error while deleting meal: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error deleting meal: {str(e)}")

# Global repository instance
meals_repo = MealsRepository()
