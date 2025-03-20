# File: repositories/supplier_rating_repository.py

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime, timedelta

from app.db.models.supplier_rating import SupplierRating
from app.repositories.base_repository import BaseRepository


class SupplierRatingRepository(BaseRepository[SupplierRating]):
    """
    Repository for managing supplier rating records.

    This repository provides methods for creating and retrieving
    supplier rating history records and calculating rating metrics.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the SupplierRatingRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, SupplierRating, encryption_service)

    def get_ratings_by_supplier(
        self, supplier_id: int, limit: int = 100
    ) -> List[SupplierRating]:
        """
        Get rating history records for a supplier.

        Args:
            supplier_id: ID of the supplier
            limit: Maximum number of records to return

        Returns:
            List of rating records in reverse chronological order
        """
        return (
            self.session.query(SupplierRating)
            .filter(SupplierRating.supplier_id == supplier_id)
            .order_by(desc(SupplierRating.rating_date))
            .limit(limit)
            .all()
        )

    def get_average_rating(self, supplier_id: int) -> float:
        """
        Calculate the average rating for a supplier.

        Args:
            supplier_id: ID of the supplier

        Returns:
            Average rating or 0 if no ratings
        """
        result = (
            self.session.query(func.avg(SupplierRating.new_rating))
            .filter(SupplierRating.supplier_id == supplier_id)
            .scalar()
        )

        return float(result) if result is not None else 0.0

    def get_rating_distribution(self, supplier_id: int) -> Dict[int, int]:
        """
        Get distribution of ratings for a supplier.

        Args:
            supplier_id: ID of the supplier

        Returns:
            Dictionary mapping rating values to counts
        """
        results = (
            self.session.query(SupplierRating.new_rating, func.count(SupplierRating.id))
            .filter(SupplierRating.supplier_id == supplier_id)
            .group_by(SupplierRating.new_rating)
            .all()
        )

        # Convert to dictionary with all possible ratings (1-5)
        distribution = {i: 0 for i in range(1, 6)}
        for rating, count in results:
            distribution[rating] = count

        return distribution

    def get_recent_ratings(
        self, days: int = 30, limit: int = 100
    ) -> List[SupplierRating]:
        """
        Get recent ratings across all suppliers.

        Args:
            days: Number of days to look back
            limit: Maximum number of records to return

        Returns:
            List of recent ratings
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        return (
            self.session.query(SupplierRating)
            .filter(SupplierRating.rating_date >= cutoff_date)
            .order_by(desc(SupplierRating.rating_date))
            .limit(limit)
            .all()
        )

    def get_top_rated_suppliers(
        self, min_ratings: int = 5, limit: int = 10
    ) -> List[Tuple[int, float]]:
        """
        Get top-rated suppliers based on average rating.

        Args:
            min_ratings: Minimum number of ratings required
            limit: Maximum number of suppliers to return

        Returns:
            List of tuples containing (supplier_id, average_rating)
        """
        subquery = (
            self.session.query(
                SupplierRating.supplier_id,
                func.count(SupplierRating.id).label("rating_count"),
            )
            .group_by(SupplierRating.supplier_id)
            .having(func.count(SupplierRating.id) >= min_ratings)
            .subquery()
        )

        results = (
            self.session.query(
                SupplierRating.supplier_id,
                func.avg(SupplierRating.new_rating).label("avg_rating"),
            )
            .join(subquery, subquery.c.supplier_id == SupplierRating.supplier_id)
            .group_by(SupplierRating.supplier_id)
            .order_by(desc("avg_rating"))
            .limit(limit)
            .all()
        )

        return [(supplier_id, float(avg_rating)) for supplier_id, avg_rating in results]
