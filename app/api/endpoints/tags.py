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
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of records to return"
    ),
    sort_by: str = Query("name", description="Field to sort by"),
    sort_dir: str = Query("asc", description="Sort direction ('asc' or 'desc')"),
    name: Optional[str] = Query(None, description="Filter by tag name"),
    search: Optional[str] = Query(None, description="Search term"),
    estimate_count: bool = Query(
        True, description="Use faster but approximate total count"
    ),
):
    """
    Retrieve a list of tags with optional filtering and pagination.
    """
    try:
        # Validate sort direction
        if sort_dir.lower() not in ["asc", "desc"]:
            sort_dir = "asc"  # Default for tags is alphabetical

        # Create search parameters from query params
        search_params = TagSearchParams(
            name=name,
            search=search,
        )

        # Force reasonable limits for memory safety
        if limit > 100:
            limit = 100
            logger.info("Limiting results to 100 items for memory safety")

        # Check memory usage before query
        try:
            import gc
            import psutil

            process = psutil.Process()
            mem_before = process.memory_info().rss / (1024 * 1024)
            if mem_before > 150:  # If already using > 150MB
                gc.collect()  # Force garbage collection
                logger.info(f"Memory usage before query: {mem_before:.1f}MB, GC forced")
        except ImportError:
            # psutil not available, skip memory check
            pass

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
            estimate_count=estimate_count,
        )

        # Calculate pagination information
        pages = (total + limit - 1) // limit if limit > 0 else 1
        page = (skip // limit) + 1 if limit > 0 else 1

        # Return response - using the existing TagListResponse model
        return TagListResponse(
            items=[TagResponse.from_orm(tag) for tag in tags],
            total=total,
            page=page,
            size=limit,
            pages=pages,
        )
    except Exception as e:
        logger.error(f"Error listing tags: {e}", exc_info=True)
        # Return empty response on error to maintain consistent API
        return TagListResponse(
            items=[],
            total=0,
            page=1,
            size=limit,
            pages=0,
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
    """
    try:
        # Get service
        service_factory = ServiceFactory(db)
        tag_service = service_factory.get_tag_service()

        # Create tag
        tag = tag_service.create_tag(
            name=tag_in.name,
            description=tag_in.description,
            color=tag_in.color,
        )

        return TagResponse.from_orm(tag)
    except DuplicateEntityException as e:
        # This is a specific exception that needs a 409 status
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating tag: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the tag",
        )


@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    tag_id: str = Path(..., description="The ID of the tag"),
):
    """
    Retrieve detailed information about a specific tag.
    """
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving tag {tag_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the tag",
        )


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
    """
    try:
        # Get service
        service_factory = ServiceFactory(db)
        tag_service = service_factory.get_tag_service()

        # Update tag
        tag = tag_service.update_tag(tag_id, tag_in.dict(exclude_none=True))

        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag with ID {tag_id} not found",
            )

        return TagResponse.from_orm(tag)
    except DuplicateEntityException as e:
        # This is a specific exception that needs a 409 status
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating tag {tag_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the tag",
        )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    tag_id: str = Path(..., description="The ID of the tag"),
):
    """
    Delete a tag.
    """
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tag {tag_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the tag",
        )


@router.get("/{tag_id}/assets")
async def get_tag_assets(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    tag_id: str = Path(..., description="The ID of the tag"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of records to return"
    ),
):
    """
    Get all media assets associated with a specific tag with pagination.
    """
    try:
        # Get services
        service_factory = ServiceFactory(db)
        tag_service = service_factory.get_tag_service()
        media_asset_service = service_factory.get_media_asset_service()

        # Verify tag exists
        tag = tag_service.get_tag(tag_id)
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag with ID {tag_id} not found",
            )

        # Get assets
        assets = media_asset_service.get_assets_by_tag(tag_id, skip, limit)

        # Get total count for pagination
        total = tag_service.get_asset_count_by_tag(tag_id)

        # Calculate pagination information
        pages = (total + limit - 1) // limit if limit > 0 else 1
        page = (skip // limit) + 1 if limit > 0 else 1

        # Return a paginated response with asset IDs
        return {
            "items": [asset.id for asset in assets],
            "total": total,
            "page": page,
            "pages": pages,
            "size": limit,
        }
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting assets for tag {tag_id}: {e}", exc_info=True)
        # Return empty response on error
        return {"items": [], "total": 0, "page": 1, "pages": 0, "size": limit}


@router.get("/{tag_id}/count", response_model=int)
async def get_asset_count_by_tag(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    tag_id: str = Path(..., description="The ID of the tag"),
):
    """
    Get the number of media assets associated with a specific tag.
    """
    try:
        # Get service
        service_factory = ServiceFactory(db)
        tag_service = service_factory.get_tag_service()

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
    except Exception as e:
        logger.error(f"Error getting asset count for tag {tag_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while counting assets",
        )
