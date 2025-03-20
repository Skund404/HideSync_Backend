# File: app/repositories/documentation_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from datetime import datetime

from app.db.models.documentation import (
    DocumentationResource,
    DocumentationCategory,
    Refund,
)
from app.db.models.enums import SkillLevel
from app.repositories.base_repository import BaseRepository


class DocumentationResourceRepository(BaseRepository[DocumentationResource]):
    """
    Repository for DocumentationResource entity operations.

    Handles retrieval and management of documentation resources,
    including guides, tutorials, and reference materials.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the DocumentationResourceRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = DocumentationResource

    def get_resources_by_category(
        self, category: str, skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Get documentation resources by category.

        Args:
            category (str): The category to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[DocumentationResource]: List of resources in the specified category
        """
        query = self.session.query(self.model).filter(self.model.category == category)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_resources_by_type(
        self, resource_type: str, skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Get documentation resources by type.

        Args:
            resource_type (str): The resource type to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[DocumentationResource]: List of resources of the specified type
        """
        query = self.session.query(self.model).filter(self.model.type == resource_type)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_resources_by_skill_level(
        self, skill_level: SkillLevel, skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Get documentation resources by skill level.

        Args:
            skill_level (SkillLevel): The skill level to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[DocumentationResource]: List of resources for the specified skill level
        """
        query = self.session.query(self.model).filter(
            self.model.skillLevel == skill_level
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_resources_by_tags(
        self, tags: List[str], skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Get documentation resources by tags.

        Args:
            tags (List[str]): List of tags to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[DocumentationResource]: List of resources with any of the specified tags
        """
        query = self.session.query(self.model)

        # Filter by any of the provided tags
        for tag in tags:
            query = query.filter(self.model.tags.contains(tag))

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_resources_by_author(
        self, author: str, skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Get documentation resources by author.

        Args:
            author (str): The author to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[DocumentationResource]: List of resources by the specified author
        """
        query = self.session.query(self.model).filter(self.model.author == author)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recently_updated_resources(
        self, skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Get recently updated documentation resources.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[DocumentationResource]: List of recently updated resources
        """
        query = self.session.query(self.model).order_by(desc(self.model.lastUpdated))

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def search_resources(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[DocumentationResource]:
        """
        Search for documentation resources by title, description, or content.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[DocumentationResource]: List of matching resources
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.title.ilike(f"%{query}%"),
                self.model.description.ilike(f"%{query}%"),
                self.model.content.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_resource_content(
        self, resource_id: str, content: str
    ) -> Optional[DocumentationResource]:
        """
        Update a documentation resource's content.

        Args:
            resource_id (str): ID of the resource
            content (str): New content

        Returns:
            Optional[DocumentationResource]: Updated resource if found, None otherwise
        """
        resource = self.get_by_id(resource_id)
        if not resource:
            return None

        resource.content = content
        resource.lastUpdated = datetime.now().isoformat()

        self.session.commit()
        self.session.refresh(resource)
        return self._decrypt_sensitive_fields(resource)

    def update_resource_tags(
        self, resource_id: str, tags: List[str]
    ) -> Optional[DocumentationResource]:
        """
        Update a documentation resource's tags.

        Args:
            resource_id (str): ID of the resource
            tags (List[str]): New list of tags

        Returns:
            Optional[DocumentationResource]: Updated resource if found, None otherwise
        """
        resource = self.get_by_id(resource_id)
        if not resource:
            return None

        resource.tags = tags
        resource.lastUpdated = datetime.now().isoformat()

        self.session.commit()
        self.session.refresh(resource)
        return self._decrypt_sensitive_fields(resource)


class DocumentationCategoryRepository(BaseRepository[DocumentationCategory]):
    """
    Repository for DocumentationCategory entity operations.

    Manages documentation categories, which organize documentation
    resources into logical groups for easier discovery.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the DocumentationCategoryRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = DocumentationCategory

    def get_category_with_resources(self, category_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a category with its associated resources.

        Args:
            category_id (str): ID of the category

        Returns:
            Optional[Dict[str, Any]]: Dictionary with category and resources if found, None otherwise
        """
        category = self.get_by_id(category_id)
        if not category:
            return None

        # Get resources for this category
        resources = (
            self.session.query(DocumentationResource)
            .filter(DocumentationResource.category == category.name)
            .all()
        )

        return {
            "category": self._decrypt_sensitive_fields(category),
            "resources": resources,
        }

    def search_categories(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[DocumentationCategory]:
        """
        Search for categories by name or description.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[DocumentationCategory]: List of matching categories
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.description.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_category_resources(
        self, category_id: str, resources: List[str]
    ) -> Optional[DocumentationCategory]:
        """
        Update a category's associated resources.

        Args:
            category_id (str): ID of the category
            resources (List[str]): New list of resource IDs

        Returns:
            Optional[DocumentationCategory]: Updated category if found, None otherwise
        """
        category = self.get_by_id(category_id)
        if not category:
            return None

        category.resources = resources

        self.session.commit()
        self.session.refresh(category)
        return self._decrypt_sensitive_fields(category)


class RefundRepository(BaseRepository[Refund]):
    """
    Repository for Refund entity operations.

    Manages refund records, tracking refund amounts, reasons,
    and statuses for customer orders.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the RefundRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Refund

    def get_refunds_by_sale(self, sale_id: int) -> List[Refund]:
        """
        Get refunds associated with a specific sale.

        Args:
            sale_id (int): ID of the sale

        Returns:
            List[Refund]: List of refunds for the sale
        """
        query = self.session.query(self.model).filter(self.model.sale_id == sale_id)

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_refunds_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[Refund]:
        """
        Get refunds by status.

        Args:
            status (str): The refund status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Refund]: List of refunds with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_refunds_by_date_range(
        self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100
    ) -> List[Refund]:
        """
        Get refunds within a specific date range.

        Args:
            start_date (datetime): Start of the date range
            end_date (datetime): End of the date range
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Refund]: List of refunds within the date range
        """
        query = self.session.query(self.model).filter(
            and_(
                self.model.refund_date >= start_date, self.model.refund_date <= end_date
            )
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_refund_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about refunds.

        Returns:
            Dict[str, Any]: Dictionary with refund statistics
        """
        total_count = self.session.query(func.count(self.model.id)).scalar()

        total_amount = (
            self.session.query(func.sum(self.model.refund_amount)).scalar() or 0
        )

        # Count by status
        status_counts = (
            self.session.query(
                self.model.status, func.count(self.model.id).label("count")
            )
            .group_by(self.model.status)
            .all()
        )

        # Calculate average refund amount
        avg_amount = (
            self.session.query(func.avg(self.model.refund_amount)).scalar() or 0
        )

        # Get recent refunds
        recent_refunds = (
            self.session.query(self.model)
            .order_by(desc(self.model.refund_date))
            .limit(5)
            .all()
        )

        return {
            "total_count": total_count,
            "total_amount": float(total_amount),
            "average_amount": float(avg_amount),
            "by_status": [
                {"status": status, "count": count} for status, count in status_counts
            ],
            "recent_refunds": [
                {
                    "id": refund.id,
                    "sale_id": refund.sale_id,
                    "amount": float(refund.refund_amount),
                    "date": refund.refund_date,
                    "status": refund.status,
                }
                for refund in recent_refunds
            ],
        }

    def create_refund(self, sale_id: int, refund_amount: float, reason: str) -> Refund:
        """
        Create a new refund record.

        Args:
            sale_id (int): ID of the sale being refunded
            refund_amount (float): Amount to refund
            reason (str): Reason for the refund

        Returns:
            Refund: The created refund record
        """
        refund_data = {
            "sale_id": sale_id,
            "refund_date": datetime.now(),
            "refund_amount": refund_amount,
            "reason": reason,
            "status": "PENDING",
        }

        return self.create(refund_data)

    def update_refund_status(self, refund_id: int, status: str) -> Optional[Refund]:
        """
        Update a refund's status.

        Args:
            refund_id (int): ID of the refund
            status (str): New status to set

        Returns:
            Optional[Refund]: Updated refund if found, None otherwise
        """
        refund = self.get_by_id(refund_id)
        if not refund:
            return None

        refund.status = status

        self.session.commit()
        self.session.refresh(refund)
        return self._decrypt_sensitive_fields(refund)
