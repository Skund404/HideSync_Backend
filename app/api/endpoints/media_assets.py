"""
Media Assets API endpoints for HideSync.

This module provides endpoints for managing media assets including
uploading, retrieving, updating, and deleting media files.
"""
from fastapi.responses import FileResponse
import os
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
    Request,  # Add this
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
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    FileStorageException,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# Add these to app/api/endpoints/media_assets.py

@router.get("/public-preview/{asset_id}")
async def public_preview_media_asset(
        asset_id: str,
        db: Session = Depends(get_db)
):
    """Public preview endpoint without auth for debugging"""
    try:
        # Get asset info
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()
        asset = media_asset_service.get_media_asset(asset_id)

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # Try to serve the actual file first
        storage_path = asset.storage_location
        if os.path.exists(storage_path):
            logger.info(f"Serving existing file from: {storage_path}")
            return FileResponse(
                path=storage_path,
                media_type=asset.content_type
            )

        # Try alternative paths
        alt_paths = [
            f"media_assets/{asset_id}_{asset.file_name}",
            f"media_assets/{asset.file_name}",
            os.path.join(os.getcwd(), "media_assets", f"{asset_id}_{asset.file_name}")
        ]

        for path in alt_paths:
            if os.path.exists(path):
                logger.info(f"Serving existing file from alt path: {path}")
                return FileResponse(
                    path=path,
                    media_type=asset.content_type
                )

        # If we get here, no existing file was found, create a test file
        test_file = f"media_assets/preview_{asset_id}.txt"
        os.makedirs("media_assets", exist_ok=True)

        with open(test_file, "w") as f:
            f.write(f"This is a preview file for asset {asset_id}\n")
            f.write(f"Original filename: {asset.file_name}\n")
            f.write(f"Storage path: {storage_path}\n")
            f.write(f"Content type: {asset.content_type}\n")

        # Return test file directly
        return FileResponse(
            path=test_file,
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"Public preview error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/public-download/{asset_id}")
async def public_download_media_asset(
        asset_id: str,
        db: Session = Depends(get_db)
):
    """Public download endpoint without auth for debugging"""
    try:
        # Get asset info
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()
        asset = media_asset_service.get_media_asset(asset_id)

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # Try to serve the actual file first
        storage_path = asset.storage_location
        if os.path.exists(storage_path):
            logger.info(f"Serving existing file from: {storage_path}")
            return FileResponse(
                path=storage_path,
                media_type=asset.content_type,
                filename=asset.file_name
            )

        # Try alternative paths
        alt_paths = [
            f"media_assets/{asset_id}_{asset.file_name}",
            f"media_assets/{asset.file_name}",
            os.path.join(os.getcwd(), "media_assets", f"{asset_id}_{asset.file_name}")
        ]

        for path in alt_paths:
            if os.path.exists(path):
                logger.info(f"Serving existing file from alt path: {path}")
                return FileResponse(
                    path=path,
                    media_type=asset.content_type,
                    filename=asset.file_name
                )

        # If we get here, no existing file was found, create a test file
        test_file = f"media_assets/download_{asset_id}.txt"
        os.makedirs("media_assets", exist_ok=True)

        with open(test_file, "w") as f:
            f.write(f"This is a download file for asset {asset_id}\n")
            f.write(f"Original filename: {asset.file_name}\n")
            f.write(f"Storage path: {storage_path}\n")
            f.write(f"Content type: {asset.content_type}\n")

        # Return test file directly
        return FileResponse(
            path=test_file,
            media_type="text/plain",
            filename=f"test_{asset.file_name}"
        )
    except Exception as e:
        logger.error(f"Public download error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/diagnostic/{asset_id}")
async def file_diagnostic(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(...),
):
    """Diagnostic endpoint to check file paths"""
    try:
        # Get services
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()

        # Get asset
        asset = media_asset_service.get_media_asset(asset_id)
        if not asset:
            return {"error": f"Asset {asset_id} not found"}

        # Get stored path
        stored_path = asset.storage_location

        # Check if file exists at the stored path
        stored_path_exists = os.path.exists(stored_path)

        # Try alternative paths
        base_dir = "media_assets"
        alternative_paths = [
            f"{base_dir}/{asset_id}_{asset.file_name}",
            f"{base_dir}/{asset.file_name}",
            f"{base_dir}/{asset_id}/{asset.file_name}",
            f"uploads/{asset_id}_{asset.file_name}",
            f"uploads/{asset.file_name}"
        ]

        found_paths = []
        for path in alternative_paths:
            if os.path.exists(path):
                found_paths.append(path)

        # Check working directory
        working_dir = os.getcwd()

        # Check if media_assets folder exists
        media_dir_exists = os.path.exists("media_assets")

        # Check what files are in the media_assets folder
        media_dir_files = os.listdir("media_assets") if media_dir_exists else []

        return {
            "asset_id": asset_id,
            "file_name": asset.file_name,
            "content_type": asset.content_type,
            "stored_path": stored_path,
            "stored_path_exists": stored_path_exists,
            "working_directory": working_dir,
            "media_dir_exists": media_dir_exists,
            "media_dir_files": media_dir_files,
            "alternative_paths_checked": alternative_paths,
            "found_paths": found_paths
        }
    except Exception as e:
        logger.error(f"Diagnostic error: {str(e)}", exc_info=True)
        return {"error": str(e)}


@router.get("/file-locator/{asset_id}")
async def locate_file(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(...),
):
    """Diagnostic endpoint to find files in the filesystem."""
    try:
        # Get asset info
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()
        asset = media_asset_service.get_media_asset(asset_id)

        if not asset:
            return {"error": "Asset not found"}

        # Get the storage location from DB
        db_path = asset.storage_location

        # Look for the file in various locations
        results = {
            "asset_id": asset_id,
            "db_path": db_path,
            "file_name": asset.file_name,
            "content_type": asset.content_type,
            "paths_checked": [],
            "file_found": False,
            "found_at": None
        }

        # Get the current working directory
        cwd = os.getcwd()
        results["cwd"] = cwd

        # Check if common directories exist
        media_dir = os.path.join(cwd, "media_assets")
        results["media_dir_exists"] = os.path.exists(media_dir)

        # List all files in the media directory
        if results["media_dir_exists"]:
            results["media_dir_files"] = os.listdir(media_dir)

        # Use glob to find any files with this asset ID
        import glob

        # Try different search patterns
        search_patterns = [
            f"{cwd}/**/{asset_id}*",
            f"{cwd}/media_assets/**/{asset_id}*",
            f"{media_dir}/**/{asset_id}*",
            f"{media_dir}/{asset_id}*",
        ]

        all_matches = []
        for pattern in search_patterns:
            results["paths_checked"].append(pattern)
            matches = glob.glob(pattern, recursive=True)
            if matches:
                all_matches.extend(matches)

        # Process and deduplicate the matches
        unique_matches = list(set(all_matches))
        results["all_matching_files"] = unique_matches

        if unique_matches:
            results["file_found"] = True
            results["found_at"] = unique_matches

            # Update the database path if we found a file
            if len(unique_matches) == 1:
                # Maybe update the path in the database?
                pass

        return results
    except Exception as e:
        logger.error(f"File locator error: {str(e)}", exc_info=True)
        return {"error": str(e)}

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
        estimate_count: bool = Query(True, description="Use faster but approximate total count"),
):
    """
    Retrieve a list of media assets with optional filtering and pagination.
    """
    try:
        # Validate sort direction
        if sort_dir.lower() not in ["asc", "desc"]:
            sort_dir = "desc"  # Default for media assets is newest first

        # Create search parameters from query params
        search_params = MediaAssetSearchParams(
            file_name=file_name,
            file_type=file_type,
            tag_ids=tag_ids,
            uploaded_by=uploaded_by,
            search=search,
        )

        # Get service
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()

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

        # Get assets
        assets, total = media_asset_service.list_media_assets(
            skip=skip,
            limit=limit,
            search_params=search_params.dict(exclude_none=True),
            sort_by=sort_by,
            sort_dir=sort_dir,
            estimate_count=estimate_count,
        )

        # Calculate pages
        pages = (total + limit - 1) // limit if limit > 0 else 1
        page = (skip // limit) + 1 if limit > 0 else 1

        # Prepare response - using the existing MediaAssetListResponse model
        return MediaAssetListResponse(
            items=[MediaAssetResponse.from_orm(asset) for asset in assets],
            total=total,
            page=page,
            size=limit,
            pages=pages,
        )
    except Exception as e:
        logger.error(f"Error listing media assets: {e}", exc_info=True)
        # Return empty response on error to maintain consistent API
        return MediaAssetListResponse(
            items=[],
            total=0,
            page=1,
            size=limit,
            pages=0,
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
    """
    try:
        # Get service
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()

        # Set uploaded_by if not provided
        if not asset_in.uploaded_by:
            asset_in.uploaded_by = current_user.username

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
    except Exception as e:
        logger.error(f"Error creating media asset: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the media asset"
        )


from fastapi.responses import FileResponse
import os


@router.get("/{asset_id}/preview")
async def preview_media_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(...),
):
    """Preview a media asset file directly in browser."""
    try:
        # Get asset
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()
        asset = media_asset_service.get_media_asset(asset_id)

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        logger.info(f"Preview request for: {asset_id}, storage path: {asset.storage_location}")

        # Get working directory and base paths
        cwd = os.getcwd()
        media_dir = os.path.join(cwd, "media_assets")

        # Create directory if it doesn't exist
        os.makedirs(media_dir, exist_ok=True)

        # Try multiple paths
        paths_to_try = [
            asset.storage_location,
            os.path.join(cwd, asset.storage_location),
            os.path.join(media_dir, f"{asset_id}_{asset.file_name}"),
            os.path.join(media_dir, asset_id[:2], asset_id[2:4], f"{asset_id}{os.path.splitext(asset.file_name)[1]}"),
        ]

        # Look for the file
        for path in paths_to_try:
            logger.info(f"Checking path: {path}")
            if os.path.exists(path):
                logger.info(f"Found file at: {path}")
                return FileResponse(
                    path=path,
                    media_type=asset.content_type
                )

        # Create placeholder if not found (for development/testing)
        placeholder_path = os.path.join(media_dir, f"placeholder_{asset_id}.png")

        try:
            # Create simple placeholder image
            from PIL import Image, ImageDraw

            # Create a colored background based on asset ID for uniqueness
            # This helps visually distinguish different assets
            hue = int(asset_id.replace("-", "")[:8], 16) % 360

            img = Image.new('RGB', (300, 200), color=hsv_to_rgb(hue / 360, 0.3, 0.95))
            d = ImageDraw.Draw(img)

            # Draw asset info
            d.text((10, 10), f"Asset ID: {asset_id[:8]}...", fill=(0, 0, 0))
            d.text((10, 30), f"File: {asset.file_name[:30]}", fill=(0, 0, 0))
            d.text((10, 160), "Placeholder Image", fill=(0, 0, 0))

            # Save the placeholder
            img.save(placeholder_path)
            logger.info(f"Created placeholder at: {placeholder_path}")

            return FileResponse(
                path=placeholder_path,
                media_type="image/png"
            )
        except Exception as e:
            logger.error(f"Error creating placeholder: {str(e)}")
            raise HTTPException(status_code=404, detail="File not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Helper function for placeholder image colors
def hsv_to_rgb(h, s, v):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


@router.get("/{asset_id}/download")
async def download_media_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(...),
):
    """Download a media asset file."""
    try:
        # Get asset
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()
        asset = media_asset_service.get_media_asset(asset_id)

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # Try the exact same approach that works in the public endpoint
        storage_path = asset.storage_location
        alt_path = f"media_assets/{asset_id}_{asset.file_name}"

        if os.path.exists(storage_path):
            logger.info(f"Serving file from storage_location: {storage_path}")
            return FileResponse(
                path=storage_path,
                media_type=asset.content_type,
                filename=asset.file_name,
                headers={"Content-Disposition": f'attachment; filename="{asset.file_name}"'}
            )
        elif os.path.exists(alt_path):
            logger.info(f"Serving file from alt path: {alt_path}")
            return FileResponse(
                path=alt_path,
                media_type=asset.content_type,
                filename=asset.file_name,
                headers={"Content-Disposition": f'attachment; filename="{asset.file_name}"'}
            )
        else:
            logger.error(f"File not found for {asset_id} at {storage_path} or {alt_path}")
            raise HTTPException(status_code=404, detail="File not found")

    except Exception as e:
        logger.error(f"Download error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{asset_id}/download")
async def download_media_asset(
        asset_id: str,
        request: Request,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user)
):
    """Download endpoint with fallback to static file serving"""
    try:
        # Get asset info
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()
        asset = media_asset_service.get_media_asset(asset_id)

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # For now, create a test file we know will work
        test_file = f"media_assets/download_{asset_id}.txt"
        os.makedirs("media_assets", exist_ok=True)

        with open(test_file, "w") as f:
            f.write(f"This is a download file for asset {asset_id}")

        # Return test file directly
        return FileResponse(
            path=test_file,
            media_type="text/plain",
            filename=f"download_{asset.file_name}",
            headers={"Content-Disposition": f"attachment; filename=download_{asset.file_name}"}
        )
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{asset_id}/download")
async def download_media_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(...),
):
    """Download a media asset file."""
    try:
        # Get asset
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()
        asset = media_asset_service.get_media_asset(asset_id)

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # Log the access attempt
        logger.info(f"Download request for: {asset_id}, path: {asset.storage_location}")

        # Direct file access - try multiple possible paths
        file_path = asset.storage_location
        found_path = None

        # Check if the direct path exists
        if os.path.exists(file_path):
            found_path = file_path
        else:
            # Try alternative paths
            candidates = [
                f"media_assets/{asset_id}_{asset.file_name}",
                f"media_assets/{asset.file_name}",
                os.path.join(os.getcwd(), "media_assets", f"{asset_id}_{asset.file_name}"),
                os.path.join(os.getcwd(), asset.storage_location)
            ]

            for path in candidates:
                logger.info(f"Checking path: {path}")
                if os.path.exists(path):
                    found_path = path
                    logger.info(f"Found file at: {path}")
                    break

        if not found_path:
            logger.error(f"File not found at any location for {asset_id}")
            raise HTTPException(status_code=404, detail="File not found")

        # Serve the file as a download attachment
        return FileResponse(
            found_path,
            media_type=asset.content_type,
            filename=asset.file_name,
            headers={"Content-Disposition": f'attachment; filename="{asset.file_name}"'}
        )
    except Exception as e:
        logger.error(f"Download error for {asset_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{asset_id}/direct-file")
async def direct_file_access(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(...),
):
    """Direct file access bypass for debugging"""
    try:
        # Get asset
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()
        asset = media_asset_service.get_media_asset(asset_id)

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        logger.info(f"Direct file access for: {asset_id}, path: {asset.storage_location}")

        # Create media_assets directory if it doesn't exist
        os.makedirs("media_assets", exist_ok=True)

        # Create a test file if needed
        test_file_path = f"media_assets/{asset_id}_test.txt"
        with open(test_file_path, "w") as f:
            f.write(f"Test file for asset {asset_id}")

        return FileResponse(
            test_file_path,
            media_type="text/plain",
            filename=f"test_{asset.file_name}.txt"
        )
    except Exception as e:
        logger.error(f"Direct file error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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
    """
    try:
        # Get services
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()

        # Read file content with safety checks
        try:
            # Set a safe limit to prevent memory issues
            MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
            file_content = await file.read(MAX_FILE_SIZE + 1)

            # Check if file size exceeds limit
            if len(file_content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE/(1024*1024)} MB"
                )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error reading uploaded file: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error reading uploaded file"
            )

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
    except Exception as e:
        logger.error(f"Error uploading media asset: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while uploading the media asset"
        )


@router.get("/{asset_id}", response_model=MediaAssetResponse)
async def get_media_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(..., description="The ID of the media asset"),
):
    """
    Retrieve detailed information about a specific media asset.
    """
    try:
        # Get service
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()

        # Get asset
        asset = media_asset_service.get_media_asset(asset_id)
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media asset with ID {asset_id} not found",
            )

        return MediaAssetResponse.from_orm(asset)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting media asset {asset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the media asset"
        )


@router.get("/{asset_id}/download")
async def download_media_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(..., description="The ID of the media asset"),
):
    """
    Download a media asset file.
    """
    try:
        # Get services
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()

        # Get asset
        asset = media_asset_service.get_media_asset(asset_id)
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media asset with ID {asset_id} not found",
            )

        # Log the asset details for debugging
        logger.info(f"Downloading asset: {asset_id}, storage: {asset.storage_location}")

        # Get file content using a more direct approach
        file_path = asset.storage_location

        # Try both absolute and relative paths
        if not os.path.isfile(file_path):
            # Try relative path
            base_dir = "media_assets"
            possible_paths = [
                f"{base_dir}/{asset_id}_{asset.file_name}",
                f"{base_dir}/{asset.file_name}",
                f"{base_dir}/{asset_id}/{asset.file_name}"
            ]

            for path in possible_paths:
                if os.path.isfile(path):
                    file_path = path
                    logger.info(f"Found file at alternative path: {file_path}")
                    break
            else:
                logger.error(f"File not found for asset {asset_id} at any of the expected locations")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found for asset {asset_id}"
                )

        # Return file as attachment for download
        return FileResponse(
            file_path,
            media_type=asset.content_type,
            filename=asset.file_name,
            headers={"Content-Disposition": f'attachment; filename="{asset.file_name}"'}
        )
    except Exception as e:
        logger.error(f"Error downloading asset {asset_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading asset: {str(e)}"
        )

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
    """
    try:
        # Get service
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()

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
    except Exception as e:
        logger.error(f"Error updating media asset {asset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the media asset"
        )


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
    """
    try:
        # Get services
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()

        # Read file content with safety checks
        try:
            # Set a safe limit to prevent memory issues
            MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
            file_content = await file.read(MAX_FILE_SIZE + 1)

            # Check if file size exceeds limit
            if len(file_content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE/(1024*1024)} MB"
                )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error reading uploaded file: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error reading uploaded file"
            )

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
    except Exception as e:
        logger.error(f"Error updating media asset file {asset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the media asset file"
        )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media_asset(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        asset_id: str = Path(..., description="The ID of the media asset"),
):
    """
    Delete a media asset and all associated entity media references.
    """
    try:
        # Get services
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()
        entity_media_service = service_factory.get_entity_media_service()

        # First, check if the asset exists
        asset = media_asset_service.get_media_asset(asset_id)
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media asset with ID {asset_id} not found",
            )

        # Delete all entity media associations that reference this asset
        try:
            logger.info(f"Removing entity media associations for media asset {asset_id}")
            entity_media_service.remove_entity_media_by_asset_id(asset_id)
        except Exception as e:
            logger.error(f"Error removing entity media associations for asset {asset_id}: {e}", exc_info=True)
            # Continue with asset deletion even if association deletion fails
            # This prevents orphaned associations but allows cleanup of the asset

        # Delete the media asset
        result = media_asset_service.delete_media_asset(asset_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media asset with ID {asset_id} not found",
            )

        logger.info(f"Successfully deleted media asset {asset_id} and its entity associations")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting media asset {asset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the media asset"
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
    """
    try:
        # Get service
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()

        # Add tags
        asset = media_asset_service.add_tags_to_asset(asset_id, tag_ids)
        return MediaAssetResponse.from_orm(asset)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding tags to media asset {asset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while adding tags to the media asset"
        )


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
    """
    try:
        # Get service
        service_factory = ServiceFactory(db)
        media_asset_service = service_factory.get_media_asset_service()

        # Remove tags
        asset = media_asset_service.remove_tags_from_asset(asset_id, tag_ids)
        return MediaAssetResponse.from_orm(asset)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error removing tags from media asset {asset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while removing tags from the media asset"
        )


# Add a memory monitoring endpoint as recommended by the optimization guide
@router.get("/system/memory", include_in_schema=False)
async def check_memory_usage(
        *,
        current_user: Any = Depends(get_current_active_user),
):
    """Check current memory usage (admin only)."""
    # Verify the user has admin permissions
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for memory usage monitoring"
        )

    try:
        import psutil
        import gc

        # Force garbage collection before measuring
        gc.collect()

        # Get memory info
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)

        return {
            "memory_usage_mb": round(memory_mb, 2),
            "percent_memory": round(process.memory_percent(), 2),
            "gc_counts": gc.get_count(),
            "module": "media_assets"
        }
    except ImportError:
        return {"error": "psutil module not available for memory monitoring"}
    except Exception as e:
        logger.error(f"Error checking memory usage: {e}", exc_info=True)
        return {"error": f"Error monitoring memory: {str(e)}"}