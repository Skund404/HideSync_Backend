# File: app/api/endpoints/annotations.py
"""
Annotations API endpoints for HideSync.

This module provides endpoints for managing annotations throughout the HideSync system.
Annotations allow users to attach notes, comments, or metadata to various entities such
as patterns, projects, materials, sales, and other objects.

The Annotations API supports:
- Creating, retrieving, updating, and deleting annotations
- Filtering annotations by entity type, entity ID, creator, or content
- Setting visibility levels (private, team, public) for collaboration
- Tagging annotations for better organization and searchability

Each annotation is associated with the user who created it and maintains
timestamp information for auditing purposes.
"""

from typing import Any, List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.annotation import (
    Annotation,
    AnnotationCreate,
    AnnotationUpdate,
    AnnotationSearchParams,
)
from app.services.annotation_service import AnnotationService
from app.core.exceptions import EntityNotFoundException, BusinessRuleException

router = APIRouter()


@router.get("/", response_model=List[Annotation])
def list_annotations(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(
            100, ge=1, le=1000, description="Maximum number of records to return"
        ),
        entity_type: Optional[str] = Query(None, description="Filter by entity type"),
        entity_id: Optional[int] = Query(None, ge=1, description="Filter by entity ID"),
        created_by: Optional[int] = Query(None, ge=1, description="Filter by creator user ID"),
        search: Optional[str] = Query(None, description="Search by content"),
) -> List[Annotation]:
    """
    Retrieve annotations with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        entity_type: Optional filter by entity type (pattern, project, material, etc.)
        entity_id: Optional filter by entity ID
        created_by: Optional filter by creator user ID
        search: Optional search term for annotation content

    Returns:
        List of annotation records
    """
    search_params = AnnotationSearchParams(
        entity_type=entity_type,
        entity_id=entity_id,
        created_by=created_by,
        search=search
    )

    annotation_service = AnnotationService(db)
    return annotation_service.get_annotations(
        skip=skip, limit=limit, search_params=search_params
    )


@router.post("/", response_model=Annotation, status_code=status.HTTP_201_CREATED)
def create_annotation(
        *,
        db: Session = Depends(get_db),
        annotation_in: AnnotationCreate,
        current_user: Any = Depends(get_current_active_user),
) -> Annotation:
    """
    Create a new annotation.

    Args:
        db: Database session
        annotation_in: Annotation data for creation
        current_user: Currently authenticated user

    Returns:
        Created annotation information

    Raises:
        HTTPException: If annotation creation fails due to business rules
    """
    annotation_service = AnnotationService(db)
    try:
        return annotation_service.create_annotation(annotation_in, current_user.id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{annotation_id}", response_model=Annotation)
def get_annotation(
        *,
        db: Session = Depends(get_db),
        annotation_id: int = Path(..., ge=1, description="The ID of the annotation to retrieve"),
        current_user: Any = Depends(get_current_active_user),
) -> Annotation:
    """
    Get detailed information about a specific annotation.

    Args:
        db: Database session
        annotation_id: ID of the annotation to retrieve
        current_user: Currently authenticated user

    Returns:
        Annotation information

    Raises:
        HTTPException: If the annotation doesn't exist
    """
    annotation_service = AnnotationService(db)
    try:
        return annotation_service.get_annotation(annotation_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation with ID {annotation_id} not found",
        )


@router.patch("/{annotation_id}", response_model=Annotation)
def update_annotation(
        *,
        db: Session = Depends(get_db),
        annotation_id: int = Path(..., ge=1, description="The ID of the annotation to update"),
        annotation_in: AnnotationUpdate,
        current_user: Any = Depends(get_current_active_user),
) -> Annotation:
    """
    Update an annotation.

    Args:
        db: Database session
        annotation_id: ID of the annotation to update
        annotation_in: Updated annotation data
        current_user: Currently authenticated user

    Returns:
        Updated annotation information

    Raises:
        HTTPException: If the annotation doesn't exist or update violates business rules
    """
    annotation_service = AnnotationService(db)
    try:
        return annotation_service.update_annotation(
            annotation_id, annotation_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation with ID {annotation_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annotation(
        *,
        db: Session = Depends(get_db),
        annotation_id: int = Path(..., ge=1, description="The ID of the annotation to delete"),
        current_user: Any = Depends(get_current_active_user),
) -> None:
    """
    Delete an annotation.

    Args:
        db: Database session
        annotation_id: ID of the annotation to delete
        current_user: Currently authenticated user

    Raises:
        HTTPException: If the annotation doesn't exist or can't be deleted
    """
    annotation_service = AnnotationService(db)
    try:
        annotation_service.delete_annotation(annotation_id, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotation with ID {annotation_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/entity/{entity_type}/{entity_id}", response_model=List[Annotation])
def get_annotations_by_entity(
        *,
        db: Session = Depends(get_db),
        entity_type: str = Path(..., description="Entity type (pattern, project, material, etc.)"),
        entity_id: int = Path(..., ge=1, description="ID of the entity"),
        current_user: Any = Depends(get_current_active_user),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
) -> List[Annotation]:
    """
    Get annotations for a specific entity.

    Args:
        db: Database session
        entity_type: Type of entity (pattern, project, material, etc.)
        entity_id: ID of the entity
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return

    Returns:
        List of annotations for the entity
    """
    annotation_service = AnnotationService(db)
    return annotation_service.get_annotations_by_entity(
        entity_type, entity_id, skip=skip, limit=limit
    )


@router.post("/entity/{entity_type}/{entity_id}", response_model=Annotation, status_code=status.HTTP_201_CREATED)
def create_entity_annotation(
        *,
        db: Session = Depends(get_db),
        entity_type: str = Path(..., description="Entity type (pattern, project, material, etc.)"),
        entity_id: int = Path(..., ge=1, description="ID of the entity"),
        content: str = Body(..., embed=True, description="Annotation content"),
        visibility: str = Body("private", embed=True, description="Annotation visibility (private, team, public)"),
        current_user: Any = Depends(get_current_active_user),
) -> Annotation:
    """
    Create a new annotation for a specific entity.

    Args:
        db: Database session
        entity_type: Type of entity (pattern, project, material, etc.)
        entity_id: ID of the entity
        content: Annotation content
        visibility: Annotation visibility (private, team, public)
        current_user: Currently authenticated user

    Returns:
        Created annotation information

    Raises:
        HTTPException: If annotation creation fails
    """
    annotation_service = AnnotationService(db)

    # Create annotation data
    annotation_data = AnnotationCreate(
        entity_type=entity_type,
        entity_id=entity_id,
        content=content,
        visibility=visibility
    )

    try:
        return annotation_service.create_annotation(annotation_data, current_user.id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))