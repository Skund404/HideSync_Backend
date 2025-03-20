# File: app/api/endpoints/documentation.py
"""
Documentation API endpoints for HideSync.

This module provides endpoints for managing documentation resources,
including guides, tutorials, and reference materials.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_current_active_superuser
from app.db.session import get_db
from app.schemas.documentation import (
    DocumentationResource,
    DocumentationResourceCreate,
    DocumentationResourceUpdate,
    DocumentationCategory,
    DocumentationCategoryCreate,
    DocumentationCategoryUpdate,
    DocumentationSearchParams,
)
from app.services.documentation_service import DocumentationService
from app.core.exceptions import EntityNotFoundException, BusinessRuleException

router = APIRouter()


@router.get("/resources", response_model=List[DocumentationResource])
def list_documentation_resources(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    category: Optional[str] = Query(None, description="Filter by category"),
    type: Optional[str] = Query(None, description="Filter by resource type"),
    skill_level: Optional[str] = Query(None, description="Filter by skill level"),
    search: Optional[str] = Query(None, description="Search term for title or content"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
) -> List[DocumentationResource]:
    """
    Retrieve documentation resources with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        category: Optional filter by category
        type: Optional filter by resource type
        skill_level: Optional filter by skill level
        search: Optional search term for title or content
        tags: Optional filter by tags

    Returns:
        List of documentation resource records
    """
    search_params = DocumentationSearchParams(
        category=category, type=type, skill_level=skill_level, search=search, tags=tags
    )

    documentation_service = DocumentationService(db)
    return documentation_service.get_documentation_resources(
        skip=skip, limit=limit, search_params=search_params
    )


@router.post(
    "/resources",
    response_model=DocumentationResource,
    status_code=status.HTTP_201_CREATED,
)
def create_documentation_resource(
    *,
    db: Session = Depends(get_db),
    resource_in: DocumentationResourceCreate,
    current_user: Any = Depends(get_current_active_superuser),
) -> DocumentationResource:
    """
    Create a new documentation resource.

    Note: Requires superuser privileges.

    Args:
        db: Database session
        resource_in: Documentation resource data for creation
        current_user: Currently authenticated superuser

    Returns:
        Created documentation resource information

    Raises:
        HTTPException: If resource creation fails
    """
    documentation_service = DocumentationService(db)
    try:
        return documentation_service.create_documentation_resource(
            resource_in, current_user.id
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/resources/{resource_id}", response_model=DocumentationResource)
def get_documentation_resource(
    *,
    db: Session = Depends(get_db),
    resource_id: str = Path(
        ..., description="The ID of the documentation resource to retrieve"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> DocumentationResource:
    """
    Get detailed information about a specific documentation resource.

    Args:
        db: Database session
        resource_id: ID of the documentation resource to retrieve
        current_user: Currently authenticated user

    Returns:
        Documentation resource information

    Raises:
        HTTPException: If the resource doesn't exist
    """
    documentation_service = DocumentationService(db)
    try:
        return documentation_service.get_documentation_resource(resource_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documentation resource with ID {resource_id} not found",
        )


@router.put("/resources/{resource_id}", response_model=DocumentationResource)
def update_documentation_resource(
    *,
    db: Session = Depends(get_db),
    resource_id: str = Path(
        ..., description="The ID of the documentation resource to update"
    ),
    resource_in: DocumentationResourceUpdate,
    current_user: Any = Depends(get_current_active_superuser),
) -> DocumentationResource:
    """
    Update a documentation resource.

    Note: Requires superuser privileges.

    Args:
        db: Database session
        resource_id: ID of the documentation resource to update
        resource_in: Updated documentation resource data
        current_user: Currently authenticated superuser

    Returns:
        Updated documentation resource information

    Raises:
        HTTPException: If the resource doesn't exist or update fails
    """
    documentation_service = DocumentationService(db)
    try:
        return documentation_service.update_documentation_resource(
            resource_id, resource_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documentation resource with ID {resource_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_documentation_resource(
    *,
    db: Session = Depends(get_db),
    resource_id: str = Path(
        ..., description="The ID of the documentation resource to delete"
    ),
    current_user: Any = Depends(get_current_active_superuser),
) -> None:
    """
    Delete a documentation resource.

    Note: Requires superuser privileges.

    Args:
        db: Database session
        resource_id: ID of the documentation resource to delete
        current_user: Currently authenticated superuser

    Raises:
        HTTPException: If the resource doesn't exist or deletion fails
    """
    documentation_service = DocumentationService(db)
    try:
        documentation_service.delete_documentation_resource(
            resource_id, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documentation resource with ID {resource_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Documentation categories
@router.get("/categories", response_model=List[DocumentationCategory])
def list_documentation_categories(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> List[DocumentationCategory]:
    """
    Retrieve all documentation categories.

    Args:
        db: Database session
        current_user: Currently authenticated user

    Returns:
        List of documentation category records
    """
    documentation_service = DocumentationService(db)
    return documentation_service.get_documentation_categories()


@router.post(
    "/categories",
    response_model=DocumentationCategory,
    status_code=status.HTTP_201_CREATED,
)
def create_documentation_category(
    *,
    db: Session = Depends(get_db),
    category_in: DocumentationCategoryCreate,
    current_user: Any = Depends(get_current_active_superuser),
) -> DocumentationCategory:
    """
    Create a new documentation category.

    Note: Requires superuser privileges.

    Args:
        db: Database session
        category_in: Documentation category data for creation
        current_user: Currently authenticated superuser

    Returns:
        Created documentation category information

    Raises:
        HTTPException: If category creation fails
    """
    documentation_service = DocumentationService(db)
    try:
        return documentation_service.create_documentation_category(
            category_in, current_user.id
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/categories/{category_id}", response_model=DocumentationCategory)
def get_documentation_category(
    *,
    db: Session = Depends(get_db),
    category_id: str = Path(
        ..., description="The ID of the documentation category to retrieve"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> DocumentationCategory:
    """
    Get detailed information about a specific documentation category.

    Args:
        db: Database session
        category_id: ID of the documentation category to retrieve
        current_user: Currently authenticated user

    Returns:
        Documentation category information

    Raises:
        HTTPException: If the category doesn't exist
    """
    documentation_service = DocumentationService(db)
    try:
        return documentation_service.get_documentation_category(category_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documentation category with ID {category_id} not found",
        )


@router.put("/categories/{category_id}", response_model=DocumentationCategory)
def update_documentation_category(
    *,
    db: Session = Depends(get_db),
    category_id: str = Path(
        ..., description="The ID of the documentation category to update"
    ),
    category_in: DocumentationCategoryUpdate,
    current_user: Any = Depends(get_current_active_superuser),
) -> DocumentationCategory:
    """
    Update a documentation category.

    Note: Requires superuser privileges.

    Args:
        db: Database session
        category_id: ID of the documentation category to update
        category_in: Updated documentation category data
        current_user: Currently authenticated superuser

    Returns:
        Updated documentation category information

    Raises:
        HTTPException: If the category doesn't exist or update fails
    """
    documentation_service = DocumentationService(db)
    try:
        return documentation_service.update_documentation_category(
            category_id, category_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documentation category with ID {category_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_documentation_category(
    *,
    db: Session = Depends(get_db),
    category_id: str = Path(
        ..., description="The ID of the documentation category to delete"
    ),
    current_user: Any = Depends(get_current_active_superuser),
) -> None:
    """
    Delete a documentation category.

    Note: Requires superuser privileges.

    Args:
        db: Database session
        category_id: ID of the documentation category to delete
        current_user: Currently authenticated superuser

    Raises:
        HTTPException: If the category doesn't exist or deletion fails
    """
    documentation_service = DocumentationService(db)
    try:
        documentation_service.delete_documentation_category(
            category_id, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documentation category with ID {category_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/resources/by-context/{context_key}", response_model=List[DocumentationResource]
)
def get_contextual_help(
    *,
    db: Session = Depends(get_db),
    context_key: str = Path(..., description="Contextual help key"),
    current_user: Any = Depends(get_current_active_user),
) -> List[DocumentationResource]:
    """
    Get documentation resources relevant to a specific context.

    Args:
        db: Database session
        context_key: Contextual help key
        current_user: Currently authenticated user

    Returns:
        List of documentation resources for the specified context
    """
    documentation_service = DocumentationService(db)
    return documentation_service.get_contextual_help(context_key)
