# File: app/repositories/annotation_repository.py
"""
Annotation repository for HideSync.

This module provides database access methods for annotation data,
implementing data access patterns for annotation management.
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
import logging  # Added for logging

from app.db.models.annotation import Annotation
from app.repositories.base_repository import BaseRepository

# Setup logger
logger = logging.getLogger(__name__)


class AnnotationRepository(BaseRepository[Annotation]):
    """
    Repository for annotation operations.

    This repository implements data access methods for the annotation table,
    providing methods to create, read, update, and delete annotation records.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the AnnotationRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Annotation  # Correctly sets the model for this repository
        logger.debug("AnnotationRepository initialized.")

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
        logger.debug(
            f"Listing annotations with skip={skip}, limit={limit}, filters={filters}"
        )
        # --- CORRECTED: Use self.session ---
        query = self.session.query(self.model)

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
            search_term = f"%{filters['content_search']}%"
            query = query.filter(self.model.content.ilike(search_term))

        if "tags" in filters and filters["tags"]:
            # This assumes tags are stored as an array or similar structure
            # Adjust based on actual storage (e.g., JSONB, relationship)
            # Example for array containment:
            # from sqlalchemy.dialects.postgresql import ARRAY, Any
            # query = query.filter(self.model.tags.contains(filters["tags"])) # Check exact match
            # query = query.filter(func.array_to_string(self.model.tags, ',').ilike(f"%{tag}%")) # Simple string search
            logger.warning(
                "Tag filtering implementation depends on storage method - check if correct."
            )
            # Placeholder: Assuming simple string search if tags is a string field
            # for tag in filters["tags"]:
            #    query = query.filter(self.model.tags.ilike(f"%{tag}%"))

        # Order by created_at desc (most recent first)
        query = query.order_by(desc(self.model.created_at))

        # Apply pagination
        try:
            results = query.offset(skip).limit(limit).all()
            logger.debug(f"Found {len(results)} annotations matching criteria.")
            return results
        except Exception as e:
            logger.error(f"Error listing annotations: {e}", exc_info=True)
            raise  # Re-raise the exception after logging

    def get_by_id(self, annotation_id: int) -> Optional[Annotation]:
        """
        Get an annotation by ID.

        Args:
            annotation_id: ID of the annotation

        Returns:
            Annotation object or None if not found
        """
        logger.debug(f"Getting annotation by ID: {annotation_id}")
        try:
            # --- CORRECTED: Use self.session ---
            result = (
                self.session.query(self.model)
                .filter(self.model.id == annotation_id)
                .first()
            )
            if result:
                logger.debug(f"Annotation found for ID: {annotation_id}")
            else:
                logger.debug(f"Annotation not found for ID: {annotation_id}")
            return result
        except Exception as e:
            logger.error(
                f"Error getting annotation by ID {annotation_id}: {e}", exc_info=True
            )
            raise

        # In app/repositories/annotation_repository.py

        def create(self, data: Dict[str, Any]) -> Annotation:
            """
            Create a new annotation.

            Args:
                data: Annotation data dictionary (should match model fields)

            Returns:
                Created annotation object
            """
            logger.debug(f"Creating annotation with data: {data}")
            try:
                # Ensure self.model is set
                if not hasattr(self, "model") or self.model is None:
                    raise AttributeError(
                        "'AnnotationRepository' object has no attribute 'model' or it's None"
                    )

                obj = self.model(**data)
                self.session.add(obj)
                # --- ADD FLUSH HERE ---
                self.session.flush()
                # ----------------------
                self.session.commit()
                # Refresh might be redundant now, but keep for safety
                self.session.refresh(obj)

                # Add a check for debugging:
                if obj.id is None:
                    logger.error(
                        "!!! Annotation ID is still None after flush, commit and refresh !!!"
                    )
                    # Optionally raise an error here if it's still None
                    # raise RuntimeError("Failed to obtain generated ID for Annotation")
                else:
                    logger.info(f"Annotation created successfully with ID: {obj.id}")

                return obj
            except Exception as e:
                logger.error(f"Error creating annotation: {e}", exc_info=True)
                self.session.rollback()  # Rollback on error
                raise

    def update(self, annotation_id: int, data: Dict[str, Any]) -> Optional[Annotation]:
        """
        Update an annotation.

        Args:
            annotation_id: ID of the annotation
            data: Updated annotation data dictionary

        Returns:
            Updated annotation object or None if not found
        """
        logger.debug(f"Updating annotation ID: {annotation_id} with data: {data}")
        try:
            # Use get_by_id which now uses self.session
            obj = self.get_by_id(annotation_id)
            if not obj:
                logger.warning(f"Annotation not found for update: ID {annotation_id}")
                return None

            # BaseRepository handles encryption if needed
            # If update is overridden here, apply updates directly
            for key, value in data.items():
                if hasattr(obj, key):  # Check if attribute exists on the model
                    setattr(obj, key, value)
                else:
                    logger.warning(
                        f"Attempted to update non-existent attribute '{key}' on Annotation {annotation_id}"
                    )

            # --- CORRECTED: Use self.session ---
            # self.session.add(obj) # Not needed if obj is already in session from get_by_id
            self.session.commit()
            self.session.refresh(obj)
            logger.info(f"Annotation updated successfully: ID {annotation_id}")
            return obj
        except Exception as e:
            logger.error(
                f"Error updating annotation {annotation_id}: {e}", exc_info=True
            )
            self.session.rollback()
            raise

    def delete(self, annotation_id: int) -> bool:
        """
        Delete an annotation.

        Args:
            annotation_id: ID of the annotation

        Returns:
            True if deleted successfully, False if not found
        """
        logger.debug(f"Deleting annotation ID: {annotation_id}")
        try:
            # Use get_by_id which now uses self.session
            obj = self.get_by_id(annotation_id)
            if not obj:
                logger.warning(f"Annotation not found for deletion: ID {annotation_id}")
                return False

            # --- CORRECTED: Use self.session ---
            self.session.delete(obj)
            self.session.commit()
            logger.info(f"Annotation deleted successfully: ID {annotation_id}")
            return True
        except Exception as e:
            logger.error(
                f"Error deleting annotation {annotation_id}: {e}", exc_info=True
            )
            self.session.rollback()
            raise

    def get_annotation_count_by_entity(self, entity_type: str, entity_id: int) -> int:
        """
        Get the count of annotations for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            Count of annotations
        """
        logger.debug(
            f"Counting annotations for entity_type={entity_type}, entity_id={entity_id}"
        )
        try:
            # --- CORRECTED: Use self.session ---
            count = (
                self.session.query(func.count(self.model.id))
                .filter(
                    and_(
                        self.model.entity_type == entity_type,
                        self.model.entity_id == entity_id,
                    )
                )
                .scalar()
                or 0  # Ensure scalar returns 0 if no rows match
            )
            logger.debug(f"Found {count} annotations for entity.")
            return count
        except Exception as e:
            logger.error(
                f"Error counting annotations for entity {entity_type}/{entity_id}: {e}",
                exc_info=True,
            )
            raise

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
        logger.debug(f"Getting recent annotations (limit={limit}, user_id={user_id})")
        try:
            # --- CORRECTED: Use self.session ---
            query = self.session.query(self.model).order_by(desc(self.model.created_at))

            if user_id is not None:  # Explicit check for None
                query = query.filter(self.model.created_by == user_id)

            results = query.limit(limit).all()
            logger.debug(f"Found {len(results)} recent annotations.")
            return results
        except Exception as e:
            logger.error(f"Error getting recent annotations: {e}", exc_info=True)
            raise

    # Add any other AnnotationRepository specific methods here
    # e.g., find_by_tags, find_by_content_search etc. if needed beyond BaseRepository.search
