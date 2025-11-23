"""
Repository for weekly_meal_plans collection operations
"""

from datetime import datetime
from typing import Optional
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from pymongo import ReturnDocument
from bson import ObjectId

from database import db_config
from models import WeeklyMealPlanCreate, WeeklyMealPlanResponse, UpdateMealSlotRequest

class WeeklyMealPlansRepository:
    """Repository class for weekly_meal_plans collection operations"""

    def __init__(self):
        self.collection_name = "weekly_meal_plans"
        self._collection: Optional[Collection] = None

    @property
    def collection(self) -> Collection:
        """Get the weekly_meal_plans collection"""
        if self._collection is None:
            if db_config.database is None:
                raise RuntimeError("Database not connected")
            self._collection = db_config.get_collection(self.collection_name)
        return self._collection

    async def get_weekly_meal_plan(self, week_start_date: str) -> Optional[WeeklyMealPlanResponse]:
        """Get a weekly meal plan by week start date"""
        try:
            plan_doc = self.collection.find_one({"week_start_date": week_start_date})

            if not plan_doc:
                return None

            return WeeklyMealPlanResponse(**plan_doc)

        except PyMongoError as e:
            raise RuntimeError(f"Database error while retrieving weekly meal plan: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving weekly meal plan: {str(e)}")

    async def upsert_weekly_meal_plan(self, plan_data: WeeklyMealPlanCreate) -> WeeklyMealPlanResponse:
        """Create or update a weekly meal plan (upsert operation)"""
        try:
            now = datetime.utcnow()

            plan_doc = {
                "week_start_date": plan_data.week_start_date,
                "sunday_lunch": plan_data.sunday_lunch,
                "tuesday_lunch": plan_data.tuesday_lunch,
                "monday_dinner": plan_data.monday_dinner,
                "wednesday_dinner": plan_data.wednesday_dinner,
                "updated_at": now
            }

            # Use find_one_and_update with upsert=True to handle both create and update in single operation
            updated_plan = self.collection.find_one_and_update(
                {"week_start_date": plan_data.week_start_date},
                {
                    "$set": plan_doc,
                    "$setOnInsert": {"created_at": now}  # Only set created_at if inserting new document
                },
                upsert=True,
                return_document=ReturnDocument.AFTER
            )

            if not updated_plan:
                raise RuntimeError("Failed to upsert weekly meal plan")

            return WeeklyMealPlanResponse(**updated_plan)

        except PyMongoError as e:
            raise RuntimeError(f"Database error while upserting weekly meal plan: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error upserting weekly meal plan: {str(e)}")

    async def update_meal_slot(self, update_data: UpdateMealSlotRequest) -> WeeklyMealPlanResponse:
        """Update a specific meal slot in the weekly plan"""
        try:
            now = datetime.utcnow()

            update_doc = {
                update_data.day_field.value: update_data.meal_id,
                "updated_at": now
            }

            # Use find_one_and_update with upsert to handle both update and create in single operation
            updated_plan = self.collection.find_one_and_update(
                {"week_start_date": update_data.week_start_date},
                {
                    "$set": update_doc,
                    "$setOnInsert": {
                        "week_start_date": update_data.week_start_date,
                        "sunday_lunch": None,
                        "tuesday_lunch": None,
                        "monday_dinner": None,
                        "wednesday_dinner": None,
                        "created_at": now
                    }
                },
                upsert=True,
                return_document=ReturnDocument.AFTER
            )

            if not updated_plan:
                raise RuntimeError("Failed to update meal slot")

            return WeeklyMealPlanResponse(**updated_plan)

        except PyMongoError as e:
            raise RuntimeError(f"Database error while updating meal slot: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error updating meal slot: {str(e)}")

    async def delete_weekly_meal_plan(self, week_start_date: str) -> bool:
        """Delete a weekly meal plan by week start date"""
        try:
            result = self.collection.delete_one({"week_start_date": week_start_date})
            return result.deleted_count > 0

        except PyMongoError as e:
            raise RuntimeError(f"Database error while deleting weekly meal plan: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error deleting weekly meal plan: {str(e)}")

# Global repository instance
weekly_meal_plans_repo = WeeklyMealPlansRepository()
