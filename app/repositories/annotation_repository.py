# File: app/repositories/annotation_repository.py
"""
Annotation repository for HideSync.

This module provides database access methods for annotation data,
implementing data access patterns for annotation management.
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from app.db.models.annotation import Annotation
from app.repositories.base_repository import BaseRepository


class AnnotationRepository(BaseRepository[Annotation]):
    """
    Repository for annotation operations.

    This repository implements data access methods for the annotation table,
    providing methods to create, read, update, and delete annotation records.
    """

    def __init__(self, db: Session):
        """
        Initialize the annotation repository.

        Args:
            db: Database session
        """
        super().__init__(Annotation, db)

    def list(self, skip: int = 0, limit: int = 100, **filters) -> List[Annotation]:
        """
        List annotations with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Additional filters to apply

        Returns:
            List of annotation objects
        """
        query = self.db.query(self.model)

        # Apply filters
        if "entity_type" in filters:
            query = query.filter(self.model.entity_type == filters["entity_type"])

        if "entity_id" in filters:
            query = query.filter(self.model.entity_id == filters["entity_id"])

        if "created_by" in filters:
            query = query.filter(self.model.created_by == filters["created_by"])

        if "visibility" in filters:
            query = query.filter(self.model.visibility == filters["visibility"])

        if "content_search" in filters:
            query = query.filter(self.model.content.ilike(filters["content_search"]))

        if "tags" in filters and filters["tags"]:
            # This assumes tags are stored as an array
            # The implementation might need to be adjusted based on how tags are stored
            for tag in filters["tags"]:
                query = query.filter(self.model.tags.contains([tag]))

        # Order by created_at desc (most recent first)
        query = query.order_by(desc(self.model.created_at))

        # Apply pagination
        return query.offset(skip).limit(limit).all()

    def get_by_id(self, annotation_id: int) -> Optional[Annotation]:
        """
        Get an annotation by ID.

        Args:
            annotation_id: ID of the annotation

        Returns:
            Annotation object or None if not found
        """
        return self.db.query(self.model).filter(self.model.id == annotation_id).first()

    def create(self, data: Dict[str, Any]) -> Annotation:
        """
        Create a new annotation.

        Args:
            data: Annotation data

        Returns:
            Created annotation object
        """
        obj = self.model(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, annotation_id: int, data: Dict[str, Any]) -> Optional[Annotation]:
        """
        Update an annotation.

        Args:
            annotation_id: ID of the annotation
            data: Updated annotation data

        Returns:
            Updated annotation object or None if not found
        """
        obj = self.get_by_id(annotation_id)
        if not obj:
            return None

        for key, value in data.items():
            setattr(obj, key, value)

        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, annotation_id: int) -> bool:
        """
        Delete an annotation.

        Args:
            annotation_id: ID of the annotation

        Returns:
            True if deleted successfully, False if not found
        """
        obj = self.get_by_id(annotation_id)
        if not obj:
            return False

        self.db.delete(obj)
        self.db.commit()
        return True

    def get_annotation_count_by_entity(self, entity_type: str, entity_id: int) -> int:
        """
        Get the count of annotations for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            Count of annotations
        """
        return (
            self.db.query(func.count(self.model.id))
            .filter(
                and_(
                    self.model.entity_type == entity_type,
                    self.model.entity_id == entity_id,
                )
            )
            .scalar()
        )

    def get_recent_annotations(
        self, user_id: Optional[int] = None, limit: int = 10
    ) -> List[Annotation]:
        """
        Get recent annotations, optionally filtered by user.

        Args:
            user_id: Optional user ID to filter by
            limit: Maximum number of annotations to return

        Returns:
            List of recent annotation objects
        """
        query = self.db.query(self.model).order_by(desc(self.model.created_at))

        if user_id:
            query = query.filter(self.model.created_by == user_id)

        return query.limit(limit).all()
