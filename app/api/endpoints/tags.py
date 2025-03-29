# File: app/api/endpoints/tags.py
"""
Tags API endpoints for HideSync.

This module provides endpoints for managing tags including
creating, retrieving, updating, and deleting tags.
"""

from typing import List, Optional, Dict, Any
import logging
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
    Path,
    Body,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.schemas.tag import (
    TagCreate,
    TagUpdate,
    TagResponse,
    TagListResponse,
    TagSearchParams,
)
from app.services.tag_service import TagService
from app.services.service_factory import ServiceFactory
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    DuplicateEntityException,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=TagListResponse)
async def list_tags(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
        sort_by: str = Query("name", description="Field to sort by"),
        sort_dir: str = Query("asc", description="Sort direction ('asc' or 'desc')"),
        name: Optional[str] = Query(None, description="Filter by tag name"),
        search: Optional[str] = Query(None, description="Search term"),
):
    """
    Retrieve a list of tags with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        sort_by: Field to sort by
        sort_dir: Sort direction
        name: Optional filter by tag name
        search: Optional search term

    Returns:
        Paginated list of tags
    """
    # Create search parameters from query params
    search_params = TagSearchParams(
        name=name,
        search=search,
    )

    # Get service
    service_factory = ServiceFactory(db)
    tag_service = service_factory.get_tag_service()

    # Get tags
    tags, total = tag_service.list_tags(
        skip=skip,
        limit=limit,
        search_params=search_params.dict(exclude_none=True),
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Calculate pages
    pages = (total + limit - 1) // limit if limit > 0 else 1
    page = (skip // limit) + 1 if limit > 0 else 1

    # Prepare response
    return TagListResponse(
        items=[TagResponse.from_orm(tag) for tag in tags],
        total=total,
        page=page,
        size=limit,
        pages=pages,
    )


@router.post("/", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        tag_in: TagCreate,
):
    """
    Create a new tag.

    Args:
        db: Database session
        current_user: Currently authenticated user
        tag_in: Tag data

    Returns:
        Created tag information
    """
    # Get service
    service_factory = ServiceFactory(db)
    tag_service = service_factory.get_tag_service()

    try:
        # Create tag
        tag = tag_service.create_tag(
            name=tag_in.name,
            description=tag_in.description,
            color=tag_in.color,
        )

        return TagResponse.from_orm(tag)
    except DuplicateEntityException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        tag_id: str = Path(..., description="The ID of the tag"),
):
    """
    Retrieve detailed information about a specific tag.

    Args:
        db: Database session
        current_user: Currently authenticated user
        tag_id: ID of the tag

    Returns:
        Tag information
    """
    # Get service
    service_factory = ServiceFactory(db)
    tag_service = service_factory.get_tag_service()

    # Get tag
    tag = tag_service.get_tag(tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag with ID {tag_id} not found",
        )

    return TagResponse.from_orm(tag)


@router.put("/{tag_id}", response_model=TagResponse)
async def update_tag(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        tag_id: str = Path(..., description="The ID of the tag"),
        tag_in: TagUpdate,
):
    """
    Update a tag.

    Args:
        db: Database session
        current_user: Currently authenticated user
        tag_id: ID of the tag
        tag_in: Updated tag data

    Returns:
        Updated tag information
    """
    # Get service
    service_factory = ServiceFactory(db)
    tag_service = service_factory.get_tag_service()

    try:
        # Update tag
        tag = tag_service.update_tag(tag_id, tag_in.dict(exclude_none=True))

        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag with ID {tag_id} not found",
            )

        return TagResponse.from_orm(tag)
    except DuplicateEntityException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        tag_id: str = Path(..., description="The ID of the tag"),
):
    """
    Delete a tag.

    Args:
        db: Database session
        current_user: Currently authenticated user
        tag_id: ID of the tag

    Returns:
        No content
    """
    # Get service
    service_factory = ServiceFactory(db)
    tag_service = service_factory.get_tag_service()

    # Delete tag
    result = tag_service.delete_tag(tag_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag with ID {tag_id} not found",
        )


@router.get("/{tag_id}/assets", response_model=List[str])
async def get_tag_assets(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        tag_id: str = Path(..., description="The ID of the tag"),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
):
    """
    Get all media assets associated with a specific tag.

    Args:
        db: Database session
        current_user: Currently authenticated user
        tag_id: ID of the tag
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return

    Returns:
        List of media asset IDs
    """
    # Get services
    service_factory = ServiceFactory(db)
    tag_service = service_factory.get_tag_service()
    media_asset_service = service_factory.get_media_asset_service()

    try:
        # Verify tag exists
        tag = tag_service.get_tag(tag_id)
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag with ID {tag_id} not found",
            )

        # Get assets
        assets = media_asset_service.get_assets_by_tag(tag_id, skip, limit)

        # Return just the IDs for simplicity
        return [asset.id for asset in assets]
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{tag_id}/count", response_model=int)
async def get_asset_count_by_tag(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        tag_id: str = Path(..., description="The ID of the tag"),
):
    """
    Get the number of media assets associated with a specific tag.

    Args:
        db: Database session
        current_user: Currently authenticated user
        tag_id: ID of the tag

    Returns:
        Number of associated media assets
    """
    # Get service
    service_factory = ServiceFactory(db)
    tag_service = service_factory.get_tag_service()

    try:
        # Verify tag exists
        tag = tag_service.get_tag(tag_id)
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag with ID {tag_id} not found",
            )

        # Get count
        return tag_service.get_asset_count_by_tag(tag_id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))