# File: app/services/annotation_service.py
"""
Annotation service for HideSync.

This module provides service methods for managing annotations,
implementing business logic for creating, retrieving, updating,
and deleting annotations.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.db.models.annotation import Annotation as AnnotationModel
from app.db.models.user import User
from app.schemas.annotation import (
    AnnotationCreate,
    AnnotationUpdate,
    AnnotationSearchParams,
    Annotation as AnnotationSchema,
)
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    PermissionDeniedException,
)
from app.repositories.annotation_repository import AnnotationRepository
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class AnnotationService(BaseService):
    """
    Service for annotation operations.

    This service implements business logic for managing annotations,
    which allow users to add notes or comments to various entities in the system.
    """

    def __init__(self, db: Session):
        """
        Initialize the annotation service.

        Args:
            db: Database session
        """
        # --- MODIFICATION START ---
        # Pass the session and the specific repository class to the parent
        super().__init__(session=db, repository_class=AnnotationRepository)
        # --- MODIFICATION END ---

        # Any AnnotationService-specific initialization can go here
        # e.g., self.some_other_service = SomeOtherService(db)
        logger.info("AnnotationService initialized.") # Add logging if desired


    def get_annotations(
        self,
        skip: int = 0,
        limit: int = 100,
        search_params: Optional[AnnotationSearchParams] = None,
    ) -> List[AnnotationSchema]:
        """
        Get annotations with optional filtering and pagination.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            search_params: Optional search parameters

        Returns:
            List of annotation records
        """
        # Build filter conditions
        filters = {}

        if search_params:
            if search_params.entity_type:
                filters["entity_type"] = search_params.entity_type
            if search_params.entity_id:
                filters["entity_id"] = search_params.entity_id
            if search_params.created_by:
                filters["created_by"] = search_params.created_by
            if search_params.visibility:
                filters["visibility"] = search_params.visibility
            if search_params.search:
                # Add content search filter
                search_term = f"%{search_params.search}%"
                filters["content_search"] = search_term

        # Query annotations
        annotations = self.repository.list(skip=skip, limit=limit, **filters)
        return [AnnotationSchema.from_orm(annotation) for annotation in annotations]

    def get_annotation(self, annotation_id: int) -> AnnotationSchema:
        """
        Get a specific annotation by ID.

        Args:
            annotation_id: ID of the annotation to retrieve

        Returns:
            Annotation object

        Raises:
            EntityNotFoundException: If annotation not found
        """
        annotation = self.repository.get_by_id(annotation_id)
        if not annotation:
            raise EntityNotFoundException(
                f"Annotation with ID {annotation_id} not found"
            )

        return AnnotationSchema.from_orm(annotation)

    def create_annotation(
        self, annotation_in: AnnotationCreate, user_id: int
    ) -> AnnotationSchema:
        """
        Create a new annotation.

        Args:
            annotation_in: Annotation data
            user_id: ID of the user creating the annotation

        Returns:
            Created annotation object

        Raises:
            BusinessRuleException: If annotation creation fails
            EntityNotFoundException: If referenced entity doesn't exist
        """
        # Validate entity exists by checking the relevant service
        # This is a simplified example - actual implementation would need to check
        # different services based on entity_type
        self._validate_entity_exists(annotation_in.entity_type, annotation_in.entity_id)

        # Create annotation data
        annotation_data = annotation_in.dict()
        annotation_data["created_by"] = user_id
        annotation_data["created_at"] = datetime.utcnow()

        # Create annotation
        annotation = self.repository.create(annotation_data)
        return AnnotationSchema.from_orm(annotation)

    def update_annotation(
        self, annotation_id: int, annotation_in: AnnotationUpdate, user_id: int
    ) -> AnnotationSchema:
        """
        Update an annotation.

        Args:
            annotation_id: ID of the annotation to update
            annotation_in: Updated annotation data
            user_id: ID of the user updating the annotation

        Returns:
            Updated annotation object

        Raises:
            EntityNotFoundException: If annotation not found
            PermissionDeniedException: If user doesn't have permission
            BusinessRuleException: If update violates business rules
        """
        # Get existing annotation
        annotation = self.repository.get_by_id(annotation_id)
        if not annotation:
            raise EntityNotFoundException(
                f"Annotation with ID {annotation_id} not found"
            )

        # Check if user has permission to update the annotation
        if annotation.created_by != user_id:
            # Users can only edit their own annotations
            # (In a real system, you might check for admin permissions here)
            raise PermissionDeniedException(
                "You don't have permission to update this annotation"
            )

        # Update annotation
        update_data = annotation_in.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        updated_annotation = self.repository.update(annotation_id, update_data)
        return AnnotationSchema.from_orm(updated_annotation)

    def delete_annotation(self, annotation_id: int, user_id: int) -> bool:
        """
        Delete an annotation.

        Args:
            annotation_id: ID of the annotation to delete
            user_id: ID of the user deleting the annotation

        Returns:
            True if deleted successfully

        Raises:
            EntityNotFoundException: If annotation not found
            PermissionDeniedException: If user doesn't have permission
        """
        # Get existing annotation
        annotation = self.repository.get_by_id(annotation_id)
        if not annotation:
            raise EntityNotFoundException(
                f"Annotation with ID {annotation_id} not found"
            )

        # Check if user has permission to delete the annotation
        if annotation.created_by != user_id:
            # Users can only delete their own annotations
            # (In a real system, you might check for admin permissions here)
            raise PermissionDeniedException(
                "You don't have permission to delete this annotation"
            )

        # Delete annotation
        self.repository.delete(annotation_id)
        return True

    def get_annotations_by_entity(
        self, entity_type: str, entity_id: int, skip: int = 0, limit: int = 100
    ) -> List[AnnotationSchema]:
        """
        Get annotations for a specific entity.

        Args:
            entity_type: Type of entity (pattern, project, material, etc.)
            entity_id: ID of the entity
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            List of annotations for the entity
        """
        filters = {
            "entity_type": entity_type,
            "entity_id": entity_id,
        }

        annotations = self.repository.list(skip=skip, limit=limit, **filters)
        return [AnnotationSchema.from_orm(annotation) for annotation in annotations]

    def _validate_entity_exists(self, entity_type: str, entity_id: int) -> bool:
        """
        Validate that the referenced entity exists.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            True if entity exists

        Raises:
            EntityNotFoundException: If entity doesn't exist
        """
        # This is a simplified implementation
        # In a real system, you would check the appropriate service based on entity_type

        if entity_type == "pattern":
            # Example: Check if pattern exists
            # pattern_service = PatternService(self.db)
            # pattern = pattern_service.get_by_id(entity_id)
            # if not pattern:
            #     raise EntityNotFoundException(f"Pattern with ID {entity_id} not found")
            pass
        elif entity_type == "project":
            # Example: Check if project exists
            # project_service = ProjectService(self.db)
            # project = project_service.get_by_id(entity_id)
            # if not project:
            #     raise EntityNotFoundException(f"Project with ID {entity_id} not found")
            pass
        elif entity_type == "material":
            # Example: Check if material exists
            # material_service = MaterialService(self.db)
            # material = material_service.get_by_id(entity_id)
            # if not material:
            #     raise EntityNotFoundException(f"Material with ID {entity_id} not found")
            pass
        elif entity_type == "sale":
            # Example: Check if sale exists
            # sale_service = SaleService(self.db)
            # sale = sale_service.get_by_id(entity_id)
            # if not sale:
            #     raise EntityNotFoundException(f"Sale with ID {entity_id} not found")
            pass
        else:
            # For unsupported entity types, you could either:
            # 1. Reject them with an error
            # 2. Accept them without validation (useful for system extensibility)

            # Option 1: Reject unsupported entity types
            # raise BusinessRuleException(f"Unsupported entity type: {entity_type}")

            # Option 2: Accept without validation
            pass

        return True
