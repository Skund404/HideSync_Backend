# File: app/api/endpoints/media_assets.py
"""
Media Assets API endpoints for HideSync.

This module provides endpoints for managing media assets including
uploading, retrieving, updating, and deleting media files.
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
    UploadFile,
    File,
    Form,
    BackgroundTasks,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from app.api.deps import get_current_active_user, get_db
from app.schemas.media_asset import (
    MediaAssetCreate,
    MediaAssetUpdate,
    MediaAssetResponse,
    MediaAssetListResponse,
    MediaAssetSearchParams,
    MediaAssetUploadComplete,
)
from app.services.media_asset_service import MediaAssetService
from app.services.tag_service import TagService
from app.services.service_factory import ServiceFactory
from app.services.file_storage_service import FileStorageService
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    FileStorageException,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=MediaAssetListResponse)
async def list_media_assets(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
        sort_by: str = Query("uploaded_at", description="Field to sort by"),
        sort_dir: str = Query("desc", description="Sort direction ('asc' or 'desc')"),
        file_name: Optional[str] = Query(None, description="Filter by file name"),
        file_type: Optional[str] = Query(None, description="Filter by file type"),
        tag_ids: Optional[List[str]] = Query(None, description="Filter by tag IDs"),
        uploaded_by: Optional[str] = Query(None, description="Filter by uploader"),
        search: Optional[str] = Query(None, description="Search term"),
):
    """
    Retrieve a list of media assets with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        sort_by: Field to sort by
        sort_dir: Sort direction
        file_name: Optional filter by file name
        file_type: Optional filter by file type
        tag_ids: Optional filter by tag IDs
        uploaded_by: Optional filter by uploader
        search: Optional search term

    Returns:
        Paginated list of media assets
    """
    # Create search parameters from query params
    search_params = MediaAssetSearchParams(
        file_name=file_name,
        file_type=file_type,
        tag_ids=tag_ids,
        uploaded_by=uploaded_by,
        search=search,
    )

    # Get service
    file_storage_service = FileStorageService()
    service_factory = ServiceFactory(db, file_storage_service=file_storage_service)
    media_asset_service = service_factory.create_media_asset_service()

    # Get assets
    assets, total = media_asset_service.list_media_assets(
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
    return MediaAssetListResponse(
        items=[MediaAssetResponse.from_orm(asset) for asset in assets],
        total=total,
        page=page,
        size=limit,
        pages=pages,
    )


@router.post("/", response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def create_media_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_in: MediaAssetCreate,
):
    """
    Create a new media asset (metadata only).

    This creates only the metadata record. Use the /upload endpoint to upload the actual file.

    Args:
        db: Database session
        current_user: Currently authenticated user
        asset_in: Media asset data

    Returns:
        Created media asset information
    """
    # Get service
    service_factory = ServiceFactory(db)
    media_asset_service = service_factory.create_media_asset_service()

    try:
        # Create media asset
        asset = media_asset_service.create_media_asset(
            file_name=asset_in.file_name,
            file_type=asset_in.file_type,
            content_type=asset_in.content_type,
            uploaded_by=asset_in.uploaded_by,
            tag_ids=asset_in.tag_ids,
        )

        return MediaAssetResponse.from_orm(asset)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/upload", response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_media_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        tag_ids: Optional[List[str]] = Form(None),
):
    """
    Upload a new media asset file.

    This endpoint both creates the metadata record and uploads the file in one operation.

    Args:
        db: Database session
        current_user: Currently authenticated user
        background_tasks: FastAPI background tasks
        file: The file to upload
        tag_ids: Optional list of tag IDs to associate

    Returns:
        Created media asset information
    """
    # Get services
    file_storage_service = FileStorageService()
    service_factory = ServiceFactory(db, file_storage_service=file_storage_service)
    media_asset_service = service_factory.create_media_asset_service()

    try:
        # Read file content
        file_content = await file.read()

        # Create media asset with content
        asset = media_asset_service.create_media_asset_with_content(
            file_name=file.filename,
            file_content=io.BytesIO(file_content),
            uploaded_by=current_user.username,  # Use the username from the authenticated user
            content_type=file.content_type,
            tag_ids=tag_ids,
        )

        return MediaAssetResponse.from_orm(asset)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileStorageException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{asset_id}", response_model=MediaAssetResponse)
async def get_media_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(..., description="The ID of the media asset"),
):
    """
    Retrieve detailed information about a specific media asset.

    Args:
        db: Database session
        current_user: Currently authenticated user
        asset_id: ID of the media asset

    Returns:
        Media asset information
    """
    # Get service
    service_factory = ServiceFactory(db)
    media_asset_service = service_factory.create_media_asset_service()

    # Get asset
    asset = media_asset_service.get_media_asset(asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media asset with ID {asset_id} not found",
        )

    return MediaAssetResponse.from_orm(asset)


@router.get("/{asset_id}/download")
async def download_media_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(..., description="The ID of the media asset"),
):
    """
    Download a media asset file.

    Args:
        db: Database session
        current_user: Currently authenticated user
        asset_id: ID of the media asset

    Returns:
        Streaming response with the file content
    """
    # Get services
    file_storage_service = FileStorageService()
    service_factory = ServiceFactory(db, file_storage_service=file_storage_service)
    media_asset_service = service_factory.create_media_asset_service()

    try:
        # Get asset
        asset = media_asset_service.get_media_asset(asset_id)
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media asset with ID {asset_id} not found",
            )

        # Get file content
        file_content = media_asset_service.get_file_content(asset_id)

        # Return file
        return StreamingResponse(
            file_content,
            media_type=asset.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{asset.file_name}"',
            },
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileStorageException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{asset_id}", response_model=MediaAssetResponse)
async def update_media_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(..., description="The ID of the media asset"),
        asset_in: MediaAssetUpdate,
):
    """
    Update a media asset.

    Args:
        db: Database session
        current_user: Currently authenticated user
        asset_id: ID of the media asset
        asset_in: Updated media asset data

    Returns:
        Updated media asset information
    """
    # Get service
    service_factory = ServiceFactory(db)
    media_asset_service = service_factory.create_media_asset_service()

    try:
        # Update asset
        asset = media_asset_service.update_media_asset(
            asset_id,
            asset_in.dict(exclude_none=True),
            user_id=current_user.id,
        )

        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media asset with ID {asset_id} not found",
            )

        return MediaAssetResponse.from_orm(asset)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{asset_id}/upload", response_model=MediaAssetResponse)
async def update_media_asset_file(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(..., description="The ID of the media asset"),
        file: UploadFile = File(...),
):
    """
    Update a media asset's file content.

    Args:
        db: Database session
        current_user: Currently authenticated user
        asset_id: ID of the media asset
        file: The new file to upload

    Returns:
        Updated media asset information
    """
    # Get services
    file_storage_service = FileStorageService()
    service_factory = ServiceFactory(db, file_storage_service=file_storage_service)
    media_asset_service = service_factory.create_media_asset_service()

    try:
        # Read file content
        file_content = await file.read()

        # Upload file
        asset = media_asset_service.upload_file(
            asset_id,
            io.BytesIO(file_content),
            update_content_type=file.content_type,
        )

        return MediaAssetResponse.from_orm(asset)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileStorageException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(..., description="The ID of the media asset"),
):
    """
    Delete a media asset.

    Args:
        db: Database session
        current_user: Currently authenticated user
        asset_id: ID of the media asset

    Returns:
        No content
    """
    # Get services
    file_storage_service = FileStorageService()
    service_factory = ServiceFactory(db, file_storage_service=file_storage_service)
    media_asset_service = service_factory.create_media_asset_service()

    # Delete asset
    result = media_asset_service.delete_media_asset(asset_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media asset with ID {asset_id} not found",
        )


@router.post("/{asset_id}/tags", response_model=MediaAssetResponse)
async def add_tags_to_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(..., description="The ID of the media asset"),
        tag_ids: List[str] = Body(..., description="List of tag IDs to add"),
):
    """
    Add tags to a media asset.

    Args:
        db: Database session
        current_user: Currently authenticated user
        asset_id: ID of the media asset
        tag_ids: List of tag IDs to add

    Returns:
        Updated media asset information
    """
    # Get service
    service_factory = ServiceFactory(db)
    media_asset_service = service_factory.create_media_asset_service()

    try:
        # Add tags
        asset = media_asset_service.add_tags_to_asset(asset_id, tag_ids)

        return MediaAssetResponse.from_orm(asset)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{asset_id}/tags", response_model=MediaAssetResponse)
async def remove_tags_from_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(..., description="The ID of the media asset"),
        tag_ids: List[str] = Body(..., description="List of tag IDs to remove"),
):
    """
    Remove tags from a media asset.

    Args:
        db: Database session
        current_user: Currently authenticated user
        asset_id: ID of the media asset
        tag_ids: List of tag IDs to remove

    Returns:
        Updated media asset information
    """
    # Get service
    service_factory = ServiceFactory(db)
    media_asset_service = service_factory.create_media_asset_service()

    try:
        # Remove tags
        asset = media_asset_service.remove_tags_from_asset(asset_id, tag_ids)

        return MediaAssetResponse.from_orm(asset)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))