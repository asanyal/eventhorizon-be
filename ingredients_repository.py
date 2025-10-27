"""
Repository for ingredients collection operations
"""

from datetime import datetime
from typing import List, Optional
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from bson import ObjectId

from database import db_config
from models import IngredientCreate, IngredientResponse

class IngredientsRepository:
    """Repository class for ingredients collection operations"""

    def __init__(self):
        self.collection_name = "ingredients"
        self._collection: Optional[Collection] = None

    @property
    def collection(self) -> Collection:
        """Get the ingredients collection"""
        if self._collection is None:
            if db_config.database is None:
                raise RuntimeError("Database not connected")
            self._collection = db_config.get_collection(self.collection_name)
        return self._collection

    async def create_ingredient(self, ingredient_data: IngredientCreate) -> IngredientResponse:
        """Create a new ingredient"""
        try:
            # Prepare document for insertion
            now = datetime.utcnow()
            ingredient_doc = {
                "name": ingredient_data.name,
                "quantity": ingredient_data.quantity,
                "unit": ingredient_data.unit,
                "created_at": now
            }

            # Insert into MongoDB
            result = self.collection.insert_one(ingredient_doc)

            # Retrieve the created document
            created_ingredient = self.collection.find_one({"_id": result.inserted_id})

            if not created_ingredient:
                raise RuntimeError("Failed to retrieve created ingredient")

            return IngredientResponse(**created_ingredient)

        except PyMongoError as e:
            raise RuntimeError(f"Database error while creating ingredient: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error creating ingredient: {str(e)}")

    async def get_all_ingredients(self) -> List[IngredientResponse]:
        """Get all ingredients"""
        try:
            # Retrieve ingredients sorted by created_at descending (newest first)
            cursor = self.collection.find({}).sort("created_at", -1)

            # Use list comprehension for better performance
            ingredients = [IngredientResponse(**ingredient_doc) for ingredient_doc in cursor]

            return ingredients

        except PyMongoError as e:
            raise RuntimeError(f"Database error while retrieving ingredients: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving ingredients: {str(e)}")

    async def delete_ingredient(self, ingredient_id: str) -> bool:
        """Delete an ingredient by ID"""
        try:
            if not ObjectId.is_valid(ingredient_id):
                return False

            result = self.collection.delete_one({"_id": ObjectId(ingredient_id)})
            return result.deleted_count > 0

        except PyMongoError as e:
            raise RuntimeError(f"Database error while deleting ingredient: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error deleting ingredient: {str(e)}")

# Global repository instance
ingredients_repo = IngredientsRepository()
