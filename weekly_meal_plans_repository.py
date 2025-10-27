"""
Repository for weekly_meal_plans collection operations
"""

from datetime import datetime
from typing import Optional
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
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

            # Check if plan exists
            existing_plan = self.collection.find_one({"week_start_date": plan_data.week_start_date})

            plan_doc = {
                "week_start_date": plan_data.week_start_date,
                "sunday_lunch": plan_data.sunday_lunch,
                "tuesday_lunch": plan_data.tuesday_lunch,
                "monday_dinner": plan_data.monday_dinner,
                "wednesday_dinner": plan_data.wednesday_dinner,
                "updated_at": now
            }

            if existing_plan:
                # Update existing plan
                self.collection.update_one(
                    {"week_start_date": plan_data.week_start_date},
                    {"$set": plan_doc}
                )
                updated_plan = self.collection.find_one({"week_start_date": plan_data.week_start_date})
                return WeeklyMealPlanResponse(**updated_plan)
            else:
                # Create new plan
                plan_doc["created_at"] = now
                result = self.collection.insert_one(plan_doc)
                created_plan = self.collection.find_one({"_id": result.inserted_id})

                if not created_plan:
                    raise RuntimeError("Failed to retrieve created weekly meal plan")

                return WeeklyMealPlanResponse(**created_plan)

        except PyMongoError as e:
            raise RuntimeError(f"Database error while upserting weekly meal plan: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error upserting weekly meal plan: {str(e)}")

    async def update_meal_slot(self, update_data: UpdateMealSlotRequest) -> WeeklyMealPlanResponse:
        """Update a specific meal slot in the weekly plan"""
        try:
            now = datetime.utcnow()

            # Check if plan exists
            existing_plan = self.collection.find_one({"week_start_date": update_data.week_start_date})

            update_doc = {
                update_data.day_field.value: update_data.meal_id,
                "updated_at": now
            }

            if existing_plan:
                # Update existing plan
                self.collection.update_one(
                    {"week_start_date": update_data.week_start_date},
                    {"$set": update_doc}
                )
            else:
                # Create new plan with only this slot filled
                new_plan_doc = {
                    "week_start_date": update_data.week_start_date,
                    "sunday_lunch": None,
                    "tuesday_lunch": None,
                    "monday_dinner": None,
                    "wednesday_dinner": None,
                    "created_at": now,
                    "updated_at": now
                }
                new_plan_doc[update_data.day_field.value] = update_data.meal_id
                self.collection.insert_one(new_plan_doc)

            # Retrieve and return updated/created plan
            updated_plan = self.collection.find_one({"week_start_date": update_data.week_start_date})

            if not updated_plan:
                raise RuntimeError("Failed to retrieve updated weekly meal plan")

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
