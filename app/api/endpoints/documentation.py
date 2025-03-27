# File: app/api/endpoints/documentation.py
"""
Documentation API endpoints for HideSync.

This module handles all documentation-related operations, including
documentation resources and categories management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from app.db.models.enums import SkillLevel
from app.schemas.documentation import (
    DocumentationCategory,
    DocumentationCategoryCreate,
    DocumentationCategoryList,
    DocumentationCategoryUpdate,
    DocumentationCategoryWithResources,
    DocumentationResourceResponse,
    DocumentationResourceCreate,
    DocumentationResourceList,
    DocumentationResourceResponse,
    DocumentationResourceUpdate,
    DocumentationSearchParams,
)
from app.api.deps import get_db, get_current_active_user
from app.db.models.user import User
from app.services.documentation_service import DocumentationService

# Create router for documentation endpoints
router = APIRouter()


# Dependency to get the documentation service
def get_documentation_service(db: Session = Depends(get_db)):
    return DocumentationService(db)


@router.get("/", response_model=dict)
def get_documentation_root():
    """
    Root endpoint for documentation API.
    """
    return {
        "message": "HideSync Documentation API",
        "endpoints": {
            "resources": "/resources - Manage documentation resources",
            "categories": "/categories - Manage documentation categories",
        },
    }


@router.get("/resources/", response_model=DocumentationResourceList)
def list_documentation_resources(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    type: Optional[str] = None,
    skill_level: Optional[SkillLevel] = None,
    search: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    service: DocumentationService = Depends(get_documentation_service),
):
    """
    List documentation resources with optional filtering.
    """
    search_params = DocumentationSearchParams(
        category=category, type=type, skill_level=skill_level, search=search, tags=tags
    )
    return service.list_resources(skip=skip, limit=limit, search_params=search_params)


@router.post(
    "/resources/", response_model=DocumentationResourceResponse, status_code=201
)
def create_documentation_resource(
    resource: DocumentationResourceCreate,
    current_user: User = Depends(get_current_active_user),
    service: DocumentationService = Depends(get_documentation_service),
):
    """
    Create a new documentation resource.
    """
    if not resource.author:
        resource.author = str(current_user.id)
    return service.create_resource(resource)


@router.get("/resources/{resource_id}", response_model=DocumentationResourceResponse)
def get_documentation_resource(
    resource_id: str = Path(..., description="The ID of the resource to retrieve"),
    service: DocumentationService = Depends(get_documentation_service),
):
    """
    Get a specific documentation resource by ID.
    """
    resource = service.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Documentation resource not found")
    return resource


@router.put("/resources/{resource_id}", response_model=DocumentationResourceResponse)
def update_documentation_resource(
    resource_id: str = Path(..., description="The ID of the resource to update"),
    resource_update: DocumentationResourceUpdate = None,
    current_user: User = Depends(get_current_active_user),
    service: DocumentationService = Depends(get_documentation_service),
):
    """
    Update a documentation resource.
    """
    existing_resource = service.get_resource(resource_id)
    if not existing_resource:
        raise HTTPException(status_code=404, detail="Documentation resource not found")

    # If author not specified, use current user
    if not resource_update.author:
        resource_update.author = str(current_user.id)

    updated_resource = service.update_resource(resource_id, resource_update)
    return updated_resource


@router.delete("/resources/{resource_id}", response_model=dict)
def delete_documentation_resource(
    resource_id: str = Path(..., description="The ID of the resource to delete"),
    current_user: User = Depends(get_current_active_user),
    service: DocumentationService = Depends(get_documentation_service),
):
    """
    Delete a documentation resource.
    """
    existing_resource = service.get_resource(resource_id)
    if not existing_resource:
        raise HTTPException(status_code=404, detail="Documentation resource not found")

    result = service.delete_resource(resource_id)
    if result:
        return {"message": "Resource deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete resource")


@router.get("/categories/", response_model=DocumentationCategoryList)
def list_documentation_categories(
    service: DocumentationService = Depends(get_documentation_service),
):
    """
    List all documentation categories.
    """
    return service.list_categories()


@router.post("/categories/", response_model=DocumentationCategory, status_code=201)
def create_documentation_category(
    category: DocumentationCategoryCreate,
    current_user: User = Depends(get_current_active_user),
    service: DocumentationService = Depends(get_documentation_service),
):
    """
    Create a new documentation category.
    """
    return service.create_category(category)


@router.get(
    "/categories/{category_id}", response_model=DocumentationCategoryWithResources
)
def get_documentation_category(
    category_id: str = Path(..., description="The ID of the category to retrieve"),
    service: DocumentationService = Depends(get_documentation_service),
):
    """
    Get a specific documentation category with its resources.
    """
    category = service.get_category_with_resources(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Documentation category not found")
    return category


@router.put("/categories/{category_id}", response_model=DocumentationCategory)
def update_documentation_category(
    category_id: str = Path(..., description="The ID of the category to update"),
    category_update: DocumentationCategoryUpdate = None,
    current_user: User = Depends(get_current_active_user),
    service: DocumentationService = Depends(get_documentation_service),
):
    """
    Update a documentation category.
    """
    existing_category = service.get_category(category_id)
    if not existing_category:
        raise HTTPException(status_code=404, detail="Documentation category not found")

    updated_category = service.update_category(category_id, category_update)
    return updated_category


@router.delete("/categories/{category_id}", response_model=dict)
def delete_documentation_category(
    category_id: str = Path(..., description="The ID of the category to delete"),
    current_user: User = Depends(get_current_active_user),
    service: DocumentationService = Depends(get_documentation_service),
):
    """
    Delete a documentation category.
    """
    existing_category = service.get_category(category_id)
    if not existing_category:
        raise HTTPException(status_code=404, detail="Documentation category not found")

    result = service.delete_category(category_id)
    if result:
        return {"message": "Category deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete category")
