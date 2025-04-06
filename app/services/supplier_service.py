# File: services/supplier_service.py

from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    DuplicateEntityException,
    SupplierNotFoundException,
)
from app.core.validation import validate_input, validate_entity
from app.db.models.enums import SupplierStatus
from app.db.models.supplier import Supplier
from app.db.models.supplier_history import SupplierHistory
from app.db.models.supplier_rating import SupplierRating
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.supplier_history_repository import SupplierHistoryRepository
from app.repositories.supplier_rating_repository import SupplierRatingRepository
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class SupplierDeleted(DomainEvent):
    """Event emitted when a supplier is deleted."""

    def __init__(
        self,
        supplier_id: int,
        supplier_name: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize supplier deleted event.

        Args:
            supplier_id: ID of the deleted supplier
            supplier_name: Name of the supplier
            user_id: Optional ID of the user who deleted the supplier
        """
        super().__init__()
        self.supplier_id = supplier_id
        self.supplier_name = supplier_name
        self.user_id = user_id

class SupplierCreated(DomainEvent):
    """Event emitted when a supplier is created."""

    def __init__(
        self,
        supplier_id: int,
        supplier_name: str,
        category: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize supplier created event.

        Args:
            supplier_id: ID of the created supplier
            supplier_name: Name of the supplier
            category: Optional supplier category
            user_id: Optional ID of the user who created the supplier
        """
        super().__init__()
        self.supplier_id = supplier_id
        self.supplier_name = supplier_name
        self.category = category
        self.user_id = user_id


class SupplierUpdated(DomainEvent):
    """Event emitted when a supplier is updated."""

    def __init__(
        self, supplier_id: int, changes: Dict[str, Any], user_id: Optional[int] = None
    ):
        """
        Initialize supplier updated event.

        Args:
            supplier_id: ID of the updated supplier
            changes: Dictionary of changed fields with old and new values
            user_id: Optional ID of the user who updated the supplier
        """
        super().__init__()
        self.supplier_id = supplier_id
        self.changes = changes
        self.user_id = user_id


class SupplierStatusChanged(DomainEvent):
    """Event emitted when a supplier's status is changed."""

    def __init__(
        self,
        supplier_id: int,
        previous_status: str,
        new_status: str,
        reason: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize supplier status changed event.

        Args:
            supplier_id: ID of the supplier
            previous_status: Previous status of the supplier
            new_status: New status of the supplier
            reason: Optional reason for the status change
            user_id: Optional ID of the user who changed the status
        """
        super().__init__()
        self.supplier_id = supplier_id
        self.previous_status = previous_status
        self.new_status = new_status
        self.reason = reason
        self.user_id = user_id


class SupplierRatingChanged(DomainEvent):
    """Event emitted when a supplier's rating is changed."""

    def __init__(
        self,
        supplier_id: int,
        previous_rating: int,
        new_rating: int,
        comments: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize supplier rating changed event.

        Args:
            supplier_id: ID of the supplier
            previous_rating: Previous rating of the supplier
            new_rating: New rating of the supplier
            comments: Optional comments explaining the rating change
            user_id: Optional ID of the user who changed the rating
        """
        super().__init__()
        self.supplier_id = supplier_id
        self.previous_rating = previous_rating
        self.new_rating = new_rating
        self.comments = comments
        self.user_id = user_id


# Validation functions
validate_supplier = validate_entity(Supplier)




class SupplierService(BaseService[Supplier]):
    """
    Service for managing suppliers in the HideSync system.

    Provides functionality for:
    - Supplier creation and management
    - Supplier categorization and status tracking
    - Supplier rating and evaluation
    - Integration with purchase and material services
    """

    def __init__(
            self,
            session: Session,
            repository=None,
            security_context=None,
            event_bus=None,
            cache_service=None,
            purchase_service=None,
            material_service=None,
            supplier_history_repository=None,
            supplier_rating_repository=None,
    ):
        """
        Initialize SupplierService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for suppliers (defaults to SupplierRepository)
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            purchase_service: Optional purchase service for order history
            material_service: Optional material service for related materials
            supplier_history_repository: Optional repository for supplier history (status changes)
            supplier_rating_repository: Optional repository for supplier ratings
        """
        # Initialize the base service first
        super().__init__(
            session=session,
            repository_class=None,  # We'll set repository directly
            security_context=security_context,
            event_bus=event_bus,
            cache_service=cache_service,
        )

        # Set our specific repository
        self.repository = repository or SupplierRepository(session)

        # Set additional service-specific dependencies
        self.purchase_service = purchase_service
        self.material_service = material_service
        self.supplier_history_repository = supplier_history_repository
        self.supplier_rating_repository = supplier_rating_repository

    @validate_input(validate_supplier)
    def create_supplier(self, data: Dict[str, Any], user_id: Optional[int] = None) -> Supplier:
        """
        Create a new supplier.

        Args:
            data: Supplier data containing name, contact info, and other details
            user_id: Optional ID of the user creating the supplier (for auditing)
        """
        with self.transaction():
            # Check for duplicate name
            if self._supplier_exists_by_name(data.get("name", "")):
                raise DuplicateEntityException(
                    f"Supplier with name '{data.get('name')}' already exists",
                    "SUPPLIER_001",
                    {"field": "name", "value": data.get("name")},
                )

            # Remove any fields not in the model
            if "created_by" in data:
                data.pop("created_by")

            # Create supplier
            supplier = self.repository.create(data)

            # Use user_id for events or logging
            if self.event_bus and user_id:
                self.event_bus.publish(
                    SupplierCreated(
                        supplier_id=supplier.id,
                        supplier_name=supplier.name,
                        category=supplier.category,
                        user_id=user_id,
                    )
                )

            return supplier

    def update_supplier(self, supplier_id: int, data: Dict[str, Any]) -> Supplier:
        """
        Update an existing supplier.

        Args:
            supplier_id: ID of the supplier to update
            data: Updated supplier data (expected in snake_case)

        Returns:
            Updated supplier entity

        Raises:
            SupplierNotFoundException: If supplier not found
            ValidationException: If validation fails
            DuplicateEntityException: If changes would create a duplicate
        """
        with self.transaction():
            # Check if supplier exists
            supplier = self.get_by_id(supplier_id)
            if not supplier:
                # Explicitly raise the correct exception if needed
                # from app.core.exceptions import SupplierNotFoundException
                raise SupplierNotFoundException(supplier_id=supplier_id) # Pass keyword argument

            # Validate input data keys against model fields if needed (optional enhancement)
            valid_keys = {c.name for c in Supplier.__table__.columns}
            invalid_keys = set(data.keys()) - valid_keys - {'id'} # Allow 'id' temporarily if present
            if invalid_keys:
                 logger.warning(f"Received unexpected keys in update data for supplier {supplier_id}: {invalid_keys}")
                 # Optionally remove invalid keys or raise an error
                 # for key in invalid_keys:
                 #     data.pop(key, None)


            # Check for duplicate name if changing name
            if "name" in data and data["name"] != supplier.name:
                if self._supplier_exists_by_name(data["name"]):
                    raise DuplicateEntityException(
                        f"Supplier with name '{data['name']}' already exists",
                        "SUPPLIER_001",
                        {"field": "name", "value": data["name"]},
                    )

            # Check for duplicate email if changing email
            if "email" in data and data["email"] != supplier.email and data["email"]:
                if self._supplier_exists_by_email(data["email"]):
                    raise DuplicateEntityException(
                        f"Supplier with email '{data['email']}' already exists",
                        "SUPPLIER_002",
                        {"field": "email", "value": data["email"]},
                    )

            # REMOVED THESE HELPER CALLS - Frontend service and Pydantic ensure snake_case
            # self._handle_field_variations(data, "payment_terms", "paymentTerms")
            # self._handle_field_variations(data, "min_order_amount", "minOrderAmount")
            # self._handle_field_variations(data, "lead_time", "leadTime")
            # self._handle_field_variations(data, "last_order_date", "lastOrderDate")
            # self._handle_field_variations(data, "material_categories", "materialCategories")

            # Log the data being processed for debugging - BEFORE calculating changes
            logger.debug(f"Processing update for supplier {supplier_id} with snake_case data: {data}")

            # Capture changes for event (based on snake_case keys)
            changes = {}
            for key, new_value in data.items():
                # Check against the supplier model's attributes
                if hasattr(supplier, key):
                    old_value = getattr(supplier, key)
                    # Handle potential type differences (e.g., enum vs string)
                    if isinstance(old_value, SupplierStatus):
                         old_value_cmp = old_value.value
                    else:
                         old_value_cmp = old_value

                    if isinstance(new_value, SupplierStatus):
                         new_value_cmp = new_value.value
                    else:
                         new_value_cmp = new_value

                    if old_value_cmp != new_value_cmp:
                        changes[key] = {"old": old_value_cmp, "new": new_value_cmp}
                elif key != 'id': # Ignore 'id' if it sneaks in
                     logger.warning(f"Key '{key}' from update data not found in Supplier model.")


            # Set updated timestamp
            data["updated_at"] = datetime.now()

            # Update supplier using the repository
            # The repository's update method should handle setting attributes based on the 'data' dict keys
            updated_supplier = self.repository.update(supplier_id, data)

            # Publish event if event bus exists and there are changes
            if self.event_bus and changes:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    SupplierUpdated(
                        supplier_id=supplier_id, changes=changes, user_id=user_id
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Supplier:{supplier_id}")
                self.cache_service.invalidate(f"Supplier:detail:{supplier_id}")

            return updated_supplier

    # REMOVE or comment out the _handle_field_variations method as it's no longer needed here
    # def _handle_field_variations(self, data: Dict[str, Any], snake_case: str, camel_case: str) -> None:
    #     """
    #     (No longer used in update_supplier)
    #     Handle variations in field naming between snake_case and camelCase.
    #     Ensures that the snake_case version is always present in data if either variant exists.
    #
    #     Args:
    #         data: The data dictionary to modify
    #         snake_case: The snake_case field name
    #         camel_case: The camelCase field name
    #     """
    #     # If camelCase exists but snake_case doesn't, copy the value
    #     if camel_case in data and snake_case not in data:
    #         data[snake_case] = data[camel_case]
    #         logger.debug(f"Copied value from {camel_case} to {snake_case}: {data[camel_case]}")
    #
    #     # Remove the camelCase version to avoid confusion
    #     if camel_case in data:
    #         data.pop(camel_case)

    def _handle_field_variations(self, data: Dict[str, Any], snake_case: str, camel_case: str) -> None:
        """
        Handle variations in field naming between snake_case and camelCase.
        Ensures that the snake_case version is always present in data if either variant exists.

        Args:
            data: The data dictionary to modify
            snake_case: The snake_case field name
            camel_case: The camelCase field name
        """
        # If camelCase exists but snake_case doesn't, copy the value
        if camel_case in data and snake_case not in data:
            data[snake_case] = data[camel_case]
            logger.debug(f"Copied value from {camel_case} to {snake_case}: {data[camel_case]}")

        # Remove the camelCase version to avoid confusion
        if camel_case in data:
            data.pop(camel_case)

    def change_supplier_status(
        self,
        supplier_id: int,
        new_status: Union[SupplierStatus, str],
        reason: Optional[str] = None,
    ) -> Supplier:
        """
        Change the status of a supplier.

        Args:
            supplier_id: ID of the supplier
            new_status: New status for the supplier
            reason: Optional reason for the status change

        Returns:
            Updated supplier entity

        Raises:
            SupplierNotFoundException: If supplier not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if supplier exists
            supplier = self.get_by_id(supplier_id)
            if not supplier:
                from app.core.exceptions import SupplierNotFoundException

                raise SupplierNotFoundException(supplier_id)

            # Convert string status to enum if needed
            if isinstance(new_status, str):
                try:
                    new_status = SupplierStatus(new_status)
                except ValueError:
                    raise ValidationException(
                        f"Invalid supplier status: {new_status}",
                        {
                            "status": [
                                f"Must be one of: {', '.join([s.value for s in SupplierStatus])}"
                            ]
                        },
                    )

            # Store previous status for event
            previous_status = supplier.status

            # No change if status is the same
            if previous_status == new_status.value:
                return supplier

            # Validate status transition
            self._validate_status_transition(previous_status, new_status.value)

            # Update supplier
            updated_supplier = self.repository.update(
                supplier_id, {"status": new_status.value}
            )

            # Record status change
            self._record_status_change(
                supplier_id=supplier_id,
                previous_status=previous_status,
                new_status=new_status.value,
                reason=reason,
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    SupplierStatusChanged(
                        supplier_id=supplier_id,
                        previous_status=previous_status,
                        new_status=new_status.value,
                        reason=reason,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Supplier:{supplier_id}")
                self.cache_service.invalidate(f"Supplier:detail:{supplier_id}")

            return updated_supplier

    def update_supplier_rating(
        self, supplier_id: int, rating: int, comments: Optional[str] = None
    ) -> Supplier:
        """
        Update the rating of a supplier.

        Args:
            supplier_id: ID of the supplier
            rating: New rating value (1-5)
            comments: Optional comments explaining the rating

        Returns:
            Updated supplier entity

        Raises:
            SupplierNotFoundException: If supplier not found
            ValidationException: If rating is invalid
        """
        # Validate rating range
        if not 1 <= rating <= 5:
            raise ValidationException(
                "Rating must be between 1 and 5",
                {"rating": ["Must be between 1 and 5"]},
            )

        with self.transaction():
            # Check if supplier exists
            supplier = self.get_by_id(supplier_id)
            if not supplier:
                from app.core.exceptions import SupplierNotFoundException

                raise SupplierNotFoundException(supplier_id)

            # Store previous rating for event
            previous_rating = supplier.rating

            # No change if rating is the same
            if previous_rating == rating:
                return supplier

            # Update supplier
            updated_supplier = self.repository.update(supplier_id, {"rating": rating})

            # Record rating change
            self._record_rating_change(
                supplier_id=supplier_id,
                previous_rating=previous_rating,
                new_rating=rating,
                comments=comments,
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    SupplierRatingChanged(
                        supplier_id=supplier_id,
                        previous_rating=previous_rating,
                        new_rating=rating,
                        comments=comments,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Supplier:{supplier_id}")
                self.cache_service.invalidate(f"Supplier:detail:{supplier_id}")

            return updated_supplier

    def get_supplier_with_details(self, supplier_id: int) -> Dict[str, Any]:
        """
        Get a supplier with comprehensive details including purchase history.

        Args:
            supplier_id: ID of the supplier

        Returns:
            Supplier with detailed information

        Raises:
            SupplierNotFoundException: If supplier not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"Supplier:detail:{supplier_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get supplier
        supplier = self.get_by_id(supplier_id)
        if not supplier:
            from app.core.exceptions import SupplierNotFoundException

            raise SupplierNotFoundException(supplier_id)

        # Convert to dict and add related data
        result = supplier.to_dict()

        # Add purchase history if purchase service is available
        if self.purchase_service:
            result["purchase_history"] = self._get_purchase_history(supplier_id)

            # Calculate purchase metrics
            purchase_metrics = self._calculate_purchase_metrics(supplier_id)
            result["purchase_metrics"] = purchase_metrics

        # Add supplied materials if material service is available
        if self.material_service:
            result["materials"] = self._get_supplied_materials(supplier_id)

        # Add status history
        result["status_history"] = self._get_status_history(supplier_id)

        # Add rating history and detailed metrics
        result["rating_history"] = self._get_rating_history(supplier_id)
        result["rating_metrics"] = self._get_supplier_rating_metrics(supplier_id)

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    def _get_supplier_rating_metrics(self, supplier_id: int) -> Dict[str, Any]:
        """
        Get detailed rating metrics for a supplier.

        Args:
            supplier_id: ID of the supplier

        Returns:
            Dictionary with rating metrics
        """
        if not self.supplier_rating_repository:
            # Return basic metrics if no rating repository
            supplier = self.get_by_id(supplier_id)
            if not supplier:
                return {"average_rating": 0, "rating_count": 0}

            return {
                "average_rating": supplier.rating or 0,
                "rating_count": 0,  # Cannot determine count without repository
                "distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            }

        # Get detailed metrics from repository
        average = self.supplier_rating_repository.get_average_rating(supplier_id)
        distribution = self.supplier_rating_repository.get_rating_distribution(
            supplier_id
        )

        # Calculate total ratings
        total_ratings = sum(distribution.values())

        # Calculate rating percentages
        percentages = {}
        for rating, count in distribution.items():
            percentages[rating] = round(
                (count / total_ratings * 100) if total_ratings > 0 else 0, 1
            )

        # Get recent trends (last 3 months vs previous 3 months)
        now = datetime.now()
        recent_cutoff = now - timedelta(days=90)
        previous_cutoff = recent_cutoff - timedelta(days=90)

        # Get recent ratings
        recent_ratings = (
            self.session.query(SupplierRating)
            .filter(
                SupplierRating.supplier_id == supplier_id,
                SupplierRating.rating_date >= recent_cutoff,
            )
            .all()
        )

        # Get previous period ratings
        previous_ratings = (
            self.session.query(SupplierRating)
            .filter(
                SupplierRating.supplier_id == supplier_id,
                SupplierRating.rating_date >= previous_cutoff,
                SupplierRating.rating_date < recent_cutoff,
            )
            .all()
        )

        # Calculate averages for trend analysis
        recent_avg = (
            sum(r.new_rating for r in recent_ratings) / len(recent_ratings)
            if recent_ratings
            else 0
        )
        previous_avg = (
            sum(r.new_rating for r in previous_ratings) / len(previous_ratings)
            if previous_ratings
            else 0
        )

        trend = "stable"
        if recent_avg > previous_avg:
            trend = "improving"
        elif recent_avg < previous_avg:
            trend = "declining"

        # Return comprehensive metrics
        return {
            "average_rating": round(average, 1),
            "rating_count": total_ratings,
            "distribution": distribution,
            "percentages": percentages,
            "trend": trend,
            "recent_average": round(recent_avg, 1),
            "previous_average": round(previous_avg, 1),
            "recent_count": len(recent_ratings),
            "previous_count": len(previous_ratings),
        }

    def search_suppliers(
        self,
        query: str,
        category: Optional[str] = None,
        status: Optional[Union[SupplierStatus, str]] = None,
        min_rating: Optional[int] = None,
    ) -> List[Supplier]:
        """
        Search for suppliers based on name, category, status, and rating.

        Args:
            query: Search query for supplier name or contact
            category: Optional category to filter by
            status: Optional status to filter by
            min_rating: Optional minimum rating to filter by

        Returns:
            List of matching suppliers
        """
        # Convert string status to enum value if needed
        if isinstance(status, SupplierStatus):
            status = status.value

        # Construct search parameters
        search_params = {"search": query}

        if category:
            search_params["category"] = category

        if status:
            search_params["status"] = status

        if min_rating is not None:
            search_params["rating_gte"] = min_rating

        return self.repository.search(**search_params)

    # Add this method to your SupplierService class in app/services/supplier_service.py

    def count_suppliers(self, **filters) -> int:
        """
        Count total number of suppliers matching the given filters.

        Args:
            **filters: Optional filters to apply

        Returns:
            int: Total count of suppliers
        """
        try:
            # Get count from repository
            if hasattr(self.repository, 'count'):
                # Use repository's count method if available
                return self.repository.count(**filters)
            else:
                # Fallback to manual counting if repository doesn't have count method
                # This is less efficient but works as a fallback
                all_suppliers = self.repository.list(**filters)
                return len(all_suppliers)

        except Exception as e:
            logger.error(f"Error counting suppliers: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Return a default value instead of raising an exception
            # This makes the API more resilient
            return 0

    def get_suppliers(self, skip: int = 0, limit: int = 100, **filters) -> List[Any]:
        """
        Get a list of suppliers with pagination.

        This version ensures proper handling of NULL datetime fields.

        Args:
            skip: Number of suppliers to skip (pagination offset)
            limit: Maximum number of suppliers to return
            **filters: Additional filters to apply

        Returns:
            List of supplier objects with properly formatted fields
        """
        try:
            # Get suppliers from repository
            suppliers = self.repository.list(skip=skip, limit=limit, **filters)

            # Process each supplier to ensure datetime fields are properly formatted
            processed_suppliers = []
            for supplier in suppliers:
                # Convert to dict to make field manipulation easier
                supplier_dict = supplier.__dict__ if hasattr(supplier, '__dict__') else supplier

                # Ensure created_at and updated_at are either valid datetime objects or None
                if 'created_at' in supplier_dict and supplier_dict['created_at'] is not None:
                    # If it's a string, try to parse it to datetime
                    if isinstance(supplier_dict['created_at'], str):
                        try:
                            from datetime import datetime
                            supplier_dict['created_at'] = datetime.fromisoformat(supplier_dict['created_at'])
                        except ValueError:
                            supplier_dict['created_at'] = None

                if 'updated_at' in supplier_dict and supplier_dict['updated_at'] is not None:
                    # If it's a string, try to parse it to datetime
                    if isinstance(supplier_dict['updated_at'], str):
                        try:
                            from datetime import datetime
                            supplier_dict['updated_at'] = datetime.fromisoformat(supplier_dict['updated_at'])
                        except ValueError:
                            supplier_dict['updated_at'] = None

                # If using SQLAlchemy models, recreate the model instance
                if hasattr(supplier, '__class__'):
                    from app.db.models.supplier import Supplier
                    processed_supplier = Supplier()
                    for key, value in supplier_dict.items():
                        # Skip SQLAlchemy internal attributes
                        if not key.startswith('_'):
                            setattr(processed_supplier, key, value)
                    processed_suppliers.append(processed_supplier)
                else:
                    # Otherwise just use the dict
                    processed_suppliers.append(supplier_dict)

            logger.info(f"Retrieved and processed {len(processed_suppliers)} suppliers")
            return processed_suppliers

        except Exception as e:
            logger.error(f"Error getting suppliers: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def get_suppliers_by_category(self, category: str) -> List[Supplier]:
        """
        Get all suppliers in a specific category.

        Args:
            category: Category to filter by

        Returns:
            List of suppliers in the category
        """
        return self.repository.list(category=category)

    def get_suppliers_by_status(
        self, status: Union[SupplierStatus, str]
    ) -> List[Supplier]:
        """
        Get all suppliers with a specific status.

        Args:
            status: Status to filter by

        Returns:
            List of suppliers with the status
        """
        # Convert string status to enum value if needed
        if isinstance(status, SupplierStatus):
            status = status.value

        return self.repository.list(status=status)

    def get_top_suppliers(
        self, category: Optional[str] = None, limit: int = 5, min_ratings: int = 3
    ) -> List[Supplier]:
        """
        Get top-rated suppliers, optionally filtered by category.

        Args:
            category: Optional category to filter by
            limit: Maximum number of suppliers to return
            min_ratings: Minimum number of ratings required (if using rating repository)

        Returns:
            List of top-rated suppliers
        """
        # If we have the supplier rating repository, use its advanced functionality
        if self.supplier_rating_repository:
            # Get top rated supplier IDs with their average ratings
            top_rated = self.supplier_rating_repository.get_top_rated_suppliers(
                min_ratings=min_ratings, limit=limit
            )

            if not top_rated:
                return []

            # Extract IDs and fetch suppliers
            supplier_ids = [supplier_id for supplier_id, _ in top_rated]

            # Apply category filter if needed
            suppliers = []
            for supplier_id in supplier_ids:
                if category:
                    supplier = self.repository.get_by_id(supplier_id)
                    if supplier and supplier.category == category:
                        suppliers.append(supplier)
                else:
                    supplier = self.repository.get_by_id(supplier_id)
                    if supplier:
                        suppliers.append(supplier)

                # Honor the limit
                if len(suppliers) >= limit:
                    break

            return suppliers
        else:
            # Fall back to simple ordering by the rating field
            filters = {"order_by": "rating", "order_dir": "desc", "limit": limit}

            if category:
                filters["category"] = category

            return self.repository.list(**filters)

    def get_supplier_statistics(self) -> Dict[str, Any]:
        """
        Get statistical information about suppliers.

        Returns:
            Dictionary with supplier statistics
        """
        # Count suppliers by status
        status_counts = {}
        for status in SupplierStatus:
            count = len(self.get_suppliers_by_status(status))
            status_counts[status.value] = count

        # Get category distribution
        category_counts = self._get_category_distribution()

        # Get rating distribution
        rating_counts = self._get_rating_distribution()

        # Get status change trends if history repository available
        status_trends = (
            self._get_status_change_trends() if self.supplier_history_repository else {}
        )

        # Get rating trends if rating repository available
        rating_trends = (
            self._get_rating_trends() if self.supplier_rating_repository else {}
        )

        return {
            "total_suppliers": sum(status_counts.values()),
            "status_distribution": status_counts,
            "category_distribution": category_counts,
            "rating_distribution": rating_counts,
            "active_suppliers": status_counts.get(SupplierStatus.ACTIVE.value, 0),
            "inactive_suppliers": status_counts.get(SupplierStatus.INACTIVE.value, 0),
            "average_rating": self._calculate_average_rating(),
            "status_trends": status_trends,
            "rating_trends": rating_trends,
        }

    def _supplier_exists_by_name(self, name: str) -> bool:
        """
        Check if a supplier with the given name already exists.

        Args:
            name: Supplier name to check

        Returns:
            True if supplier exists, False otherwise
        """
        # Add a specific method to the repository for this common operation
        return self.repository.exists_by_name(name)

    def _supplier_exists_by_email(self, email: str) -> bool:
        """
        Check if a supplier with the given email already exists.

        Args:
            email: Supplier email to check

        Returns:
            True if supplier exists, False otherwise
        """
        return len(self.repository.list(email=email)) > 0

    def delete_supplier(self, supplier_id: int) -> bool:
        """
        Delete a supplier by ID.

        Args:
            supplier_id: ID of the supplier to delete

        Returns:
            True if deletion was successful

        Raises:
            EntityNotFoundException: If supplier not found
            BusinessRuleException: If supplier cannot be deleted (e.g., has active purchases)
        """
        with self.transaction():
            # Check if supplier exists
            supplier = self.get_by_id(supplier_id)
            if not supplier:
                from app.core.exceptions import EntityNotFoundException
                raise EntityNotFoundException(f"Supplier with ID {supplier_id} not found")

            # Check if supplier can be deleted (e.g., no active purchases)
            # This would be a business rule validation
            if self.purchase_service:
                active_purchases = self._check_active_purchases(supplier_id)
                if active_purchases:
                    from app.core.exceptions import BusinessRuleException
                    raise BusinessRuleException(
                        f"Cannot delete supplier with {len(active_purchases)} active purchases",
                        "SUPPLIER_DELETE_001",
                        {"active_purchases": len(active_purchases)}
                    )

            # Get user ID for events
            user_id = self.security_context.current_user.id if self.security_context else None

            # Delete the supplier
            result = self.repository.delete(supplier_id)

            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish(
                    SupplierDeleted(
                        supplier_id=supplier_id,
                        supplier_name=supplier.name,
                        user_id=user_id
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Supplier:{supplier_id}")
                self.cache_service.invalidate(f"Supplier:detail:{supplier_id}")

            return result

    def _check_active_purchases(self, supplier_id: int) -> list:
        """
        Check if supplier has any active purchases that would prevent deletion.

        Args:
            supplier_id: ID of the supplier

        Returns:
            List of active purchase IDs, empty if none
        """
        if not self.purchase_service:
            return []

        try:
            # This would call a method on the purchase service
            return self.purchase_service.get_active_purchases_by_supplier(supplier_id)
        except Exception as e:
            logger.warning(f"Error checking active purchases for supplier {supplier_id}: {str(e)}")
            return []

    def _validate_status_transition(self, current_status: str, new_status: str) -> None:
        """
        Validate that a status transition is allowed based on business rules.

        Args:
            current_status: Current status
            new_status: Proposed new status

        Raises:
            InvalidStatusTransitionException: If transition is not allowed
        """
        # Define allowed transitions
        allowed_transitions = {
            SupplierStatus.ACTIVE.value: [
                SupplierStatus.PREFERRED.value,
                SupplierStatus.INACTIVE.value,
                SupplierStatus.SUSPENDED.value,
                SupplierStatus.UNDER_EVALUATION.value,
            ],
            SupplierStatus.PREFERRED.value: [
                SupplierStatus.ACTIVE.value,
                SupplierStatus.INACTIVE.value,
                SupplierStatus.SUSPENDED.value,
            ],
            SupplierStatus.INACTIVE.value: [
                SupplierStatus.ACTIVE.value,
                SupplierStatus.BANNED.value,
            ],
            SupplierStatus.SUSPENDED.value: [
                SupplierStatus.ACTIVE.value,
                SupplierStatus.INACTIVE.value,
                SupplierStatus.BANNED.value,
            ],
            SupplierStatus.BANNED.value: [SupplierStatus.INACTIVE.value],
            SupplierStatus.NEW.value: [
                SupplierStatus.ACTIVE.value,
                SupplierStatus.PENDING_APPROVAL.value,
                SupplierStatus.INACTIVE.value,
            ],
            SupplierStatus.PENDING_APPROVAL.value: [
                SupplierStatus.ACTIVE.value,
                SupplierStatus.INACTIVE.value,
                SupplierStatus.REJECTED.value,
            ],
            SupplierStatus.REJECTED.value: [
                SupplierStatus.PENDING_APPROVAL.value,
                SupplierStatus.INACTIVE.value,
            ],
            SupplierStatus.UNDER_EVALUATION.value: [
                SupplierStatus.ACTIVE.value,
                SupplierStatus.PREFERRED.value,
                SupplierStatus.INACTIVE.value,
            ],
        }

        # Allow transition to same status
        if current_status == new_status:
            return

        # Check if transition is allowed
        if new_status not in allowed_transitions.get(current_status, []):
            from app.core.exceptions import InvalidStatusTransitionException

            raise InvalidStatusTransitionException(
                f"Cannot transition from {current_status} to {new_status}",
                allowed_transitions=allowed_transitions.get(current_status, []),
            )

    def _record_status_change(
        self,
        supplier_id: int,
        previous_status: str,
        new_status: str,
        reason: Optional[str] = None,
    ) -> None:
        """
        Record a status change in the supplier history.

        Args:
            supplier_id: Supplier ID
            previous_status: Previous status
            new_status: New status
            reason: Optional reason for the change
        """
        # This method would use a SupplierHistoryRepository to record the change
        # For now, just logging the change
        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        logger.info(
            f"Supplier {supplier_id} status changed from {previous_status} to {new_status} by user {user_id}",
            extra={
                "supplier_id": supplier_id,
                "previous_status": previous_status,
                "new_status": new_status,
                "user_id": user_id,
                "reason": reason,
            },
        )

    def _record_rating_change(
        self,
        supplier_id: int,
        previous_rating: int,
        new_rating: int,
        comments: Optional[str] = None,
    ) -> None:
        """
        Record a rating change in the supplier history.

        Args:
            supplier_id: Supplier ID
            previous_rating: Previous rating
            new_rating: New rating
            comments: Optional comments explaining the change
        """
        # Get user ID from security context if available
        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )

        # Log the change
        logger.info(
            f"Supplier {supplier_id} rating changed from {previous_rating} to {new_rating} by user {user_id}",
            extra={
                "supplier_id": supplier_id,
                "previous_rating": previous_rating,
                "new_rating": new_rating,
                "user_id": user_id,
                "comments": comments,
            },
        )

        # Record in repository if available
        if self.supplier_rating_repository:
            rating_data = {
                "supplier_id": supplier_id,
                "previous_rating": previous_rating,
                "new_rating": new_rating,
                "comments": comments,
                "rated_by": user_id,
                "rating_date": datetime.now(),
            }
            self.supplier_rating_repository.create(rating_data)

    def _get_purchase_history(self, supplier_id: int) -> List[Dict[str, Any]]:
        """
        Get purchase history for a supplier.

        Args:
            supplier_id: Supplier ID

        Returns:
            List of purchases from the supplier
        """
        if not self.purchase_service:
            return []

        # Get purchases from the supplier
        purchases = self.purchase_service.get_purchases_by_supplier(supplier_id)

        # Convert to list of dictionaries with simplified data
        return [
            {
                "id": purchase.id,
                "date": purchase.date.isoformat() if purchase.date else None,
                "delivery_date": (
                    purchase.delivery_date.isoformat()
                    if purchase.delivery_date
                    else None
                ),
                "status": purchase.status,
                "total": purchase.total,
                "payment_status": purchase.payment_status,
                "items_count": len(purchase.items) if hasattr(purchase, "items") else 0,
            }
            for purchase in purchases
        ]

    def _calculate_purchase_metrics(self, supplier_id: int) -> Dict[str, Any]:
        """
        Calculate purchase metrics for a supplier.

        Args:
            supplier_id: Supplier ID

        Returns:
            Dictionary with purchase metrics
        """
        if not self.purchase_service:
            return {}

        # Get purchases from the supplier
        purchases = self.purchase_service.get_purchases_by_supplier(supplier_id)

        if not purchases:
            return {
                "total_purchases": 0,
                "total_spend": 0,
                "average_order_value": 0,
                "first_purchase_date": None,
                "last_purchase_date": None,
                "on_time_delivery_rate": 0,
                "quality_issues": 0,
            }

        # Calculate metrics
        total_purchases = len(purchases)
        total_spend = sum(purchase.total for purchase in purchases if purchase.total)
        average_order_value = (
            total_spend / total_purchases if total_purchases > 0 else 0
        )

        # Get first and last purchase dates
        purchase_dates = [purchase.date for purchase in purchases if purchase.date]
        first_purchase_date = min(purchase_dates) if purchase_dates else None
        last_purchase_date = max(purchase_dates) if purchase_dates else None

        # Calculate on-time delivery rate
        delivered_purchases = [
            p for p in purchases if p.status == "DELIVERED" and p.delivery_date
        ]
        on_time_deliveries = [
            p
            for p in delivered_purchases
            if p.delivery_date
            and p.expected_delivery_date
            and p.delivery_date <= p.expected_delivery_date
        ]
        on_time_delivery_rate = (
            len(on_time_deliveries) / len(delivered_purchases) * 100
            if delivered_purchases
            else 0
        )

        # Calculate quality issues (this would use a more sophisticated approach in a real system)
        quality_issues = len(
            [p for p in purchases if hasattr(p, "quality_issue") and p.quality_issue]
        )

        return {
            "total_purchases": total_purchases,
            "total_spend": round(total_spend, 2),
            "average_order_value": round(average_order_value, 2),
            "first_purchase_date": (
                first_purchase_date.isoformat() if first_purchase_date else None
            ),
            "last_purchase_date": (
                last_purchase_date.isoformat() if last_purchase_date else None
            ),
            "on_time_delivery_rate": round(on_time_delivery_rate, 1),
            "quality_issues": quality_issues,
        }

    def _get_supplied_materials(self, supplier_id: int) -> List[Dict[str, Any]]:
        """
        Get materials supplied by a supplier.

        Args:
            supplier_id: Supplier ID

        Returns:
            List of materials from the supplier
        """
        if not self.material_service:
            return []

        # Get materials from the supplier
        materials = self.material_service.get_materials_by_supplier(supplier_id)

        # Convert to list of dictionaries with simplified data
        return [
            {
                "id": material.id,
                "name": material.name,
                "material_type": material.material_type,
                "status": material.status,
                "quantity": material.quantity,
                "unit": material.unit,
                "cost": material.cost,
            }
            for material in materials
        ]

    def _get_status_history(self, supplier_id: int) -> List[Dict[str, Any]]:
        """
        Get status change history for a supplier.

        Args:
            supplier_id: Supplier ID

        Returns:
            List of status changes
        """
        if not self.supplier_history_repository:
            return []

        # Get history records from repository
        history_records = self.supplier_history_repository.get_history_by_supplier(
            supplier_id
        )

        # Convert to list of dictionaries
        return [
            {
                "id": record.id,
                "previous_status": record.previous_status,
                "new_status": record.new_status,
                "reason": record.reason,
                "changed_by": record.changed_by,
                "timestamp": (
                    record.change_date.isoformat() if record.change_date else None
                ),
            }
            for record in history_records
        ]

    def _get_rating_history(self, supplier_id: int) -> List[Dict[str, Any]]:
        """
        Get rating change history for a supplier.

        Args:
            supplier_id: Supplier ID

        Returns:
            List of rating changes
        """
        if not self.supplier_rating_repository:
            return []

        # Get rating records from repository
        rating_records = self.supplier_rating_repository.get_ratings_by_supplier(
            supplier_id
        )

        # Convert to list of dictionaries
        return [
            {
                "id": record.id,
                "previous_rating": record.previous_rating,
                "new_rating": record.new_rating,
                "comments": record.comments,
                "rated_by": record.rated_by,
                "timestamp": (
                    record.rating_date.isoformat() if record.rating_date else None
                ),
            }
            for record in rating_records
        ]

    def _get_category_distribution(self) -> Dict[str, int]:
        """
        Get distribution of suppliers by category.

        Returns:
            Dictionary with category counts
        """
        # Get all suppliers
        suppliers = self.repository.list()

        # Count by category
        category_counts = {}
        for supplier in suppliers:
            category = supplier.category or "UNCATEGORIZED"
            if category in category_counts:
                category_counts[category] += 1
            else:
                category_counts[category] = 1

        return category_counts

    def _get_rating_distribution(self) -> Dict[str, int]:
        """
        Get distribution of suppliers by rating.

        Returns:
            Dictionary with rating counts
        """
        # If rating repository is available, get more accurate distribution
        if self.supplier_rating_repository:
            suppliers = self.repository.list(fields=["id"])

            # Aggregate results across all suppliers
            result = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

            for supplier in suppliers:
                # Get distribution for this supplier
                dist = self.supplier_rating_repository.get_rating_distribution(
                    supplier.id
                )

                # Add to overall counts
                for rating, count in dist.items():
                    result[rating] += count

            return result
        else:
            # Fall back to using suppliers' current rating
            suppliers = self.repository.list()

            # Count by rating
            rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for supplier in suppliers:
                if supplier.rating and 1 <= supplier.rating <= 5:
                    rating_counts[supplier.rating] += 1

            return rating_counts

    def _get_status_change_trends(self) -> Dict[str, Any]:
        """
        Get trends in supplier status changes.

        Returns:
            Dictionary with status change trends
        """
        if not self.supplier_history_repository:
            return {}

        # Get recent status changes
        recent_changes = self.supplier_history_repository.get_recent_history(days=90)

        # Count by new status and month
        status_by_month = {}
        month_format = "%Y-%m"

        for change in recent_changes:
            month = change.change_date.strftime(month_format)
            status = change.new_status

            if month not in status_by_month:
                status_by_month[month] = {}

            if status not in status_by_month[month]:
                status_by_month[month][status] = 0

            status_by_month[month][status] += 1

        # Get counts for specific important statuses
        preferred_counts = {}
        inactive_counts = {}
        suspended_counts = {}

        for month, statuses in status_by_month.items():
            preferred_counts[month] = statuses.get(SupplierStatus.PREFERRED.value, 0)
            inactive_counts[month] = statuses.get(SupplierStatus.INACTIVE.value, 0)
            suspended_counts[month] = statuses.get(SupplierStatus.SUSPENDED.value, 0)

        return {
            "preferred_trend": preferred_counts,
            "inactive_trend": inactive_counts,
            "suspended_trend": suspended_counts,
            "total_changes": len(recent_changes),
        }

    def _get_rating_trends(self) -> Dict[str, Any]:
        """
        Get trends in supplier ratings.

        Returns:
            Dictionary with rating trends
        """
        if not self.supplier_rating_repository:
            return {}

        # Get recent ratings
        recent_ratings = self.supplier_rating_repository.get_recent_ratings(days=180)

        # Calculate average by month
        ratings_by_month = {}
        month_format = "%Y-%m"

        for rating in recent_ratings:
            month = rating.rating_date.strftime(month_format)

            if month not in ratings_by_month:
                ratings_by_month[month] = {"count": 0, "total": 0}

            ratings_by_month[month]["count"] += 1
            ratings_by_month[month]["total"] += rating.new_rating

        # Calculate monthly averages
        monthly_averages = {}
        for month, data in ratings_by_month.items():
            if data["count"] > 0:
                monthly_averages[month] = round(data["total"] / data["count"], 1)

        # Get overall trend (positive/negative)
        months = sorted(monthly_averages.keys())

        trend = "stable"
        if len(months) >= 2:
            first_month = months[0]
            last_month = months[-1]

            if monthly_averages[last_month] > monthly_averages[first_month]:
                trend = "improving"
            elif monthly_averages[last_month] < monthly_averages[first_month]:
                trend = "declining"

        return {
            "monthly_averages": monthly_averages,
            "trend": trend,
            "total_ratings": len(recent_ratings),
        }

    def _calculate_average_rating(self) -> float:
        """
        Calculate average rating across all suppliers.

        Returns:
            Average rating
        """
        # If we have the rating repository with aggregation capabilities, use it
        if self.supplier_rating_repository:
            # Get supplier IDs
            suppliers = self.repository.list(fields=["id"])
            supplier_ids = [s.id for s in suppliers]

            if not supplier_ids:
                return 0.0

            # Calculate average rating across all ratings
            ratings = (
                self.session.query(func.avg(SupplierRating.new_rating))
                .filter(SupplierRating.supplier_id.in_(supplier_ids))
                .scalar()
            )

            return round(float(ratings) if ratings is not None else 0.0, 1)
        else:
            # Use the supplier.rating field if no rating repository
            suppliers = self.repository.list()

            # Calculate average rating
            rated_suppliers = [s for s in suppliers if s.rating is not None]
            if not rated_suppliers:
                return 0.0

            total_rating = sum(s.rating for s in rated_suppliers)
            average_rating = total_rating / len(rated_suppliers)

            return round(average_rating, 1)
