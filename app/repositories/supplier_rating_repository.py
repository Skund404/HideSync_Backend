# File: app/repositories/supplier_rating_repository.py

from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func
from sqlalchemy.sql.expression import case
from datetime import datetime

from app.db.models.supplier_rating import SupplierRating
from app.repositories.base_repository import BaseRepository


class SupplierRatingRepository(BaseRepository[SupplierRating]):
    """
    Repository for SupplierRating entity operations.

    Handles data access for supplier ratings, providing methods for
    querying, aggregating, and analyzing supplier performance data.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the SupplierRatingRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = SupplierRating

    def get_ratings_by_supplier(
            self,
            supplier_id: int,
            order_by: str = "rating_date",
            order_dir: str = "desc",
            limit: int = 50
    ) -> List[SupplierRating]:
        """
        Get rating entries for a specific supplier.

        Args:
            supplier_id: ID of the supplier
            order_by: Field to order by
            order_dir: Direction of ordering ("asc" or "desc")
            limit: Maximum number of records to return

        Returns:
            List of supplier rating entries
        """
        query = self.session.query(self.model).filter(self.model.supplier_id == supplier_id)

        # Apply ordering
        if order_dir.lower() == "desc":
            query = query.order_by(desc(getattr(self.model, order_by)))
        else:
            query = query.order_by(asc(getattr(self.model, order_by)))

        # Apply limit
        query = query.limit(limit)

        # Apply decryption if needed
        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recent_ratings(
            self, cutoff_date: datetime, limit: int = 1000
    ) -> List[SupplierRating]:
        """
        Get rating entries after a cutoff date.

        Args:
            cutoff_date: Date after which to get entries
            limit: Maximum number of records to return

        Returns:
            List of recent supplier rating entries
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.rating_date >= cutoff_date)
            .order_by(desc(self.model.rating_date))
            .limit(limit)
        )

        # Apply decryption if needed
        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_average_rating(self, supplier_id: int) -> float:
        """
        Get the average rating for a supplier.

        Args:
            supplier_id: ID of the supplier

        Returns:
            Average rating (None if no ratings)
        """
        result = (
            self.session.query(func.avg(self.model.new_rating))
            .filter(self.model.supplier_id == supplier_id)
            .scalar()
        )

        return float(result) if result is not None else 0.0

    def get_rating_distribution(self, supplier_id: int) -> Dict[int, int]:
        """
        Get the distribution of ratings for a supplier.

        Args:
            supplier_id: ID of the supplier

        Returns:
            Dictionary with rating counts by value (1-5)
        """
        query = (
            self.session.query(
                self.model.new_rating,
                func.count(self.model.id)
            )
            .filter(self.model.supplier_id == supplier_id)
            .group_by(self.model.new_rating)
        )

        result = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for rating, count in query.all():
            if 1 <= rating <= 5:
                result[rating] = count

        return result

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
        # Subquery to count ratings per supplier
        rating_counts = (
            self.session.query(
                self.model.supplier_id,
                func.count(self.model.id).label("rating_count")
            )
            .group_by(self.model.supplier_id)
            .having(func.count(self.model.id) >= min_ratings)
            .subquery()
        )

        # Query for average ratings of suppliers with minimum number of ratings
        query = (
            self.session.query(
                self.model.supplier_id,
                func.avg(self.model.new_rating).label("avg_rating")
            )
            .join(
                rating_counts,
                self.model.supplier_id == rating_counts.c.supplier_id
            )
            .group_by(self.model.supplier_id)
            .order_by(desc("avg_rating"))
            .limit(limit)
        )

        # Return list of (supplier_id, average_rating) tuples
        return [(supplier_id, float(avg_rating)) for supplier_id, avg_rating in query.all()]

    def get_rating_trends(
            self, supplier_id: int, months: int = 12
    ) -> Dict[str, float]:
        """
        Get average rating by month for a supplier.

        Args:
            supplier_id: ID of the supplier
            months: Number of months to look back

        Returns:
            Dictionary with month keys and average rating values
        """
        # This is a simplified version - in a real implementation, you would use
        # SQLAlchemy's func.date_trunc or equivalent to group by month

        # Get recent ratings
        now = datetime.now()
        cutoff_date = datetime(now.year - (months // 12), now.month - (months % 12), 1)
        if cutoff_date.month < 1:
            cutoff_date = datetime(cutoff_date.year - 1, 12 + cutoff_date.month, 1)

        recent_ratings = self.get_recent_ratings(cutoff_date)

        # Filter for this supplier
        supplier_ratings = [r for r in recent_ratings if r.supplier_id == supplier_id]

        # Group by month
        result = {}
        for rating in supplier_ratings:
            month_key = rating.rating_date.strftime("%Y-%m")
            if month_key not in result:
                result[month_key] = {"total": 0, "count": 0}

            result[month_key]["total"] += rating.new_rating
            result[month_key]["count"] += 1

        # Calculate averages
        monthly_averages = {}
        for month, data in result.items():
            if data["count"] > 0:
                monthly_averages[month] = round(data["total"] / data["count"], 1)

        return monthly_averages