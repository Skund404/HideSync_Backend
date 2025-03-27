# File: app/services/supplier_rating_service.py
"""
Service for supplier rating management in the HideSync system.

This module provides functionality for managing supplier ratings,
analyzing rating trends, and maintaining rating history.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.events import DomainEvent
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.supplier_rating_repository import SupplierRatingRepository
from app.db.models.supplier_rating import SupplierRating
from app.services.base_service import BaseService


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


class SupplierRatingService(BaseService[SupplierRating]):
    """
    Service for managing supplier ratings in the HideSync system.

    Provides functionality for:
    - Recording supplier ratings
    - Calculating average ratings and metrics
    - Analyzing rating trends
    """

    def __init__(
        self,
        session: Session,
        supplier_repository=None,
        supplier_rating_repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
    ):
        """
        Initialize SupplierRatingService with dependencies.

        Args:
            session: Database session for persistence operations
            supplier_repository: Optional repository for suppliers
            supplier_rating_repository: Optional repository for supplier ratings
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
        """
        self.session = session
        self.supplier_repository = supplier_repository or SupplierRepository(session)
        self.repository = supplier_rating_repository or SupplierRatingRepository(
            session
        )
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service

    def record_rating(
        self, supplier_id: int, rating: int, comments: Optional[str] = None
    ) -> SupplierRating:
        """
        Record a rating for a supplier.

        Args:
            supplier_id: ID of the supplier
            rating: New rating value (1-5)
            comments: Optional comments explaining the rating

        Returns:
            Created supplier rating entry

        Raises:
            EntityNotFoundException: If supplier not found
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
            supplier = self.supplier_repository.get_by_id(supplier_id)
            if not supplier:
                raise EntityNotFoundException(
                    f"Supplier with ID {supplier_id} not found"
                )

            # Get previous rating for the event
            previous_rating = supplier.rating or 0

            # Get user ID from security context if available
            user_id = (
                self.security_context.current_user.id if self.security_context else None
            )

            # Create rating record
            rating_data = {
                "supplier_id": supplier_id,
                "previous_rating": previous_rating,
                "new_rating": rating,
                "comments": comments,
                "rated_by": user_id,
                "rating_date": datetime.now(),
            }

            rating_entry = self.repository.create(rating_data)

            # Update the supplier's current rating
            self.supplier_repository.update_supplier_rating(supplier_id, rating)

            # Publish event if event bus exists
            if self.event_bus:
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
                self.cache_service.invalidate(f"SupplierRating:{supplier_id}")
                self.cache_service.invalidate(f"SupplierRatingMetrics:{supplier_id}")
                self.cache_service.invalidate(f"Supplier:{supplier_id}")

            return rating_entry

    def get_ratings_by_supplier(
        self, supplier_id: int, limit: int = 50
    ) -> List[SupplierRating]:
        """
        Get rating entries for a specific supplier.

        Args:
            supplier_id: ID of the supplier
            limit: Maximum number of records to return

        Returns:
            List of supplier rating entries ordered by rating date (newest first)

        Raises:
            EntityNotFoundException: If supplier not found
        """
        # Check if supplier exists
        supplier = self.supplier_repository.get_by_id(supplier_id)
        if not supplier:
            raise EntityNotFoundException(f"Supplier with ID {supplier_id} not found")

        # Check cache first
        if self.cache_service:
            cache_key = f"SupplierRating:{supplier_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached[:limit]  # Return only requested number of records

        # Get ratings from repository
        ratings = self.repository.get_ratings_by_supplier(
            supplier_id, order_by="rating_date", order_dir="desc", limit=limit
        )

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, ratings, ttl=3600)  # 1 hour TTL

        return ratings

    def get_recent_ratings(self, days: int = 90) -> List[SupplierRating]:
        """
        Get recent rating entries across all suppliers.

        Args:
            days: Number of days to look back

        Returns:
            List of recent supplier rating entries
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        return self.repository.get_recent_ratings(cutoff_date)

    def get_average_rating(self, supplier_id: int) -> float:
        """
        Get the average rating for a supplier.

        Args:
            supplier_id: ID of the supplier

        Returns:
            Average rating (0.0 if no ratings)
        """
        average = self.repository.get_average_rating(supplier_id)
        return round(average, 1) if average is not None else 0.0

    def get_rating_distribution(self, supplier_id: int) -> Dict[int, int]:
        """
        Get the distribution of ratings for a supplier.

        Args:
            supplier_id: ID of the supplier

        Returns:
            Dictionary with rating counts by value (1-5)
        """
        distribution = self.repository.get_rating_distribution(supplier_id)
        return distribution

    def get_supplier_rating_metrics(self, supplier_id: int) -> Dict[str, Any]:
        """
        Get detailed rating metrics for a supplier.

        Args:
            supplier_id: ID of the supplier

        Returns:
            Dictionary with comprehensive rating metrics

        Raises:
            EntityNotFoundException: If supplier not found
        """
        # Check if supplier exists
        supplier = self.supplier_repository.get_by_id(supplier_id)
        if not supplier:
            raise EntityNotFoundException(f"Supplier with ID {supplier_id} not found")

        # Check cache first
        if self.cache_service:
            cache_key = f"SupplierRatingMetrics:{supplier_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get average rating
        average = self.get_average_rating(supplier_id)

        # Get rating distribution
        distribution = self.get_rating_distribution(supplier_id)

        # Calculate total ratings
        total_ratings = sum(distribution.values())

        # Calculate rating percentages
        percentages = {}
        for rating, count in distribution.items():
            percentages[rating] = round(
                (count / total_ratings * 100) if total_ratings > 0 else 0, 1
            )

        # Get recent trends (last 3 months vs previous 3 months)
        trend_data = self._analyze_rating_trends(supplier_id)

        # Get most recent ratings
        recent_ratings = self.get_ratings_by_supplier(supplier_id, limit=5)

        # Create metrics result
        metrics = {
            "average_rating": average,
            "rating_count": total_ratings,
            "distribution": distribution,
            "percentages": percentages,
            "recent_average": trend_data["recent_average"],
            "previous_average": trend_data["previous_average"],
            "trend": trend_data["trend"],
            "recent_count": trend_data["recent_count"],
            "previous_count": trend_data["previous_count"],
            "recent_ratings": [
                {
                    "id": r.id,
                    "rating": r.new_rating,
                    "date": r.rating_date.isoformat() if r.rating_date else None,
                    "comments": r.comments,
                }
                for r in recent_ratings
            ],
        }

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, metrics, ttl=3600)  # 1 hour TTL

        return metrics

    def get_top_rated_suppliers(
        self, min_ratings: int = 3, limit: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Get top-rated suppliers with a minimum number of ratings.

        Args:
            min_ratings: Minimum number of ratings required
            limit: Maximum number of suppliers to return

        Returns:
            List of tuples with supplier ID and average rating
        """
        return self.repository.get_top_rated_suppliers(
            min_ratings=min_ratings, limit=limit
        )

    def _analyze_rating_trends(self, supplier_id: int) -> Dict[str, Any]:
        """
        Analyze rating trends for a supplier.

        Args:
            supplier_id: ID of the supplier

        Returns:
            Dictionary with trend analysis data
        """
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

        # Determine trend direction
        trend = "stable"
        if previous_avg > 0:  # Only compare if there are previous ratings
            if recent_avg > previous_avg + 0.5:
                trend = "improving"
            elif recent_avg < previous_avg - 0.5:
                trend = "declining"

        return {
            "recent_average": round(recent_avg, 1),
            "previous_average": round(previous_avg, 1),
            "recent_count": len(recent_ratings),
            "previous_count": len(previous_ratings),
            "trend": trend,
        }
