# File: app/api/endpoints/entity_media.py
from typing import List, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.schemas.entity_media import (
    EntityMediaCreate,
    EntityMediaUpdate,
    EntityMediaResponse,
    EntityMediaListResponse,
)
from app.services.entity_media_service import EntityMediaService
from app.services.service_factory import ServiceFactory
from app.core.exceptions import EntityNotFoundException, BusinessRuleException

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/entity/{entity_type}/{entity_id}", response_model=List[EntityMediaResponse])
async def get_entity_media(
        entity_type: str = Path(..., description="The type of entity (material, tool, supplier, etc.)"),
        entity_id: str = Path(..., description="The ID of the entity"),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_active_user),
):
    """
    Retrieve all media associations for a specific entity.
    """
    try:
        service_factory = ServiceFactory(db)
        entity_media_service = service_factory.get_entity_media_service()

        # Fetch all media for the entity
        entity_media_list = entity_media_service.get_by_entity(entity_type, entity_id)

        return entity_media_list
    except Exception as e:
        logger.error(f"Error retrieving entity media: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve media for {entity_type} {entity_id}: {str(e)}"
        )


@router.get("/media-asset/{media_asset_id}", response_model=List[EntityMediaResponse])
async def get_entity_media_by_asset(
        media_asset_id: str = Path(..., description="The ID of the media asset"),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_active_user),
):
    """
    Retrieve all entity associations for a specific media asset.
    """
    try:
        service_factory = ServiceFactory(db)
        entity_media_service = service_factory.get_entity_media_service()

        # Fetch all entities for the media asset
        entity_media_list = entity_media_service.find_by_media_asset_id(media_asset_id)

        return entity_media_list
    except Exception as e:
        logger.error(f"Error retrieving entities for media asset {media_asset_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve entities for media asset {media_asset_id}: {str(e)}"
        )

@router.get("/thumbnail/{entity_type}/{entity_id}", response_model=Optional[EntityMediaResponse])
async def get_entity_thumbnail(
        entity_type: str = Path(..., description="The type of entity (material, tool, supplier, etc.)"),
        entity_id: str = Path(..., description="The ID of the entity"),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_active_user),
):
    """
    Retrieve the thumbnail media association for a specific entity.
    """
    try:
        service_factory = ServiceFactory(db)
        entity_media_service = service_factory.get_entity_media_service()

        # Fetch thumbnail for the entity
        thumbnail = entity_media_service.get_thumbnail(entity_type, entity_id)

        if not thumbnail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No thumbnail found for {entity_type} {entity_id}"
            )

        return thumbnail
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving entity thumbnail: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve thumbnail for {entity_type} {entity_id}: {str(e)}"
        )


@router.post("", response_model=EntityMediaResponse, status_code=status.HTTP_201_CREATED)
async def create_entity_media(
        entity_media: EntityMediaCreate,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_active_user),
):
    """
    Create a new entity media association.
    """
    try:
        service_factory = ServiceFactory(db)
        entity_media_service = service_factory.get_entity_media_service()

        # Create the entity media association
        result = entity_media_service.update_entity_media(
            entity_type=entity_media.entity_type,
            entity_id=entity_media.entity_id,
            media_asset_id=entity_media.media_asset_id,
            media_type=entity_media.media_type,
            display_order=entity_media.display_order,
            caption=entity_media.caption,
        )

        return result
    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except BusinessRuleException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating entity media: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create entity media: {str(e)}"
        )


@router.patch("/{id}", response_model=EntityMediaResponse)
async def update_entity_media(
        id: str = Path(..., description="The ID of the entity media association"),
        updates: EntityMediaUpdate = Body(...),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_active_user),
):
    """
    Update an entity media association.
    """
    try:
        service_factory = ServiceFactory(db)
        entity_media_service = service_factory.get_entity_media_service()

        # First, get the existing entity media
        existing_media = entity_media_service.get_by_id(id)
        if not existing_media:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity media with ID {id} not found"
            )

        # Update the entity media with the new values
        result = entity_media_service.update_entity_media(
            entity_type=existing_media.entity_type,
            entity_id=existing_media.entity_id,
            media_asset_id=updates.media_asset_id or existing_media.media_asset_id,
            media_type=updates.media_type or existing_media.media_type,
            display_order=updates.display_order if updates.display_order is not None else existing_media.display_order,
            caption=updates.caption if updates.caption is not None else existing_media.caption,
        )

        return result
    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except BusinessRuleException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating entity media: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update entity media: {str(e)}"
        )


from fastapi import Response  # Add this import at the top

# Fix the DELETE endpoint
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity_media(
        id: str = Path(..., description="The ID of the entity media association"),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_active_user),
):
    try:
        service_factory = ServiceFactory(db)
        entity_media_service = service_factory.get_entity_media_service()

        # Delete the entity media
        success = entity_media_service.delete_entity_media(id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity media with ID {id} not found"
            )

        # Return a proper 204 No Content response instead of None
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting entity media: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete entity media: {str(e)}"
        )


@router.delete("/entity", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity_media_by_entity(
        entity_type: str = Query(..., description="The type of entity (material, tool, supplier, etc.)"),
        entity_id: str = Query(..., description="The ID of the entity"),
        media_type: Optional[str] = Query(None, description="Optional type of media to remove (if None, removes all)"),
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_active_user),
):
    """
    Remove media associations for an entity.
    """
    try:
        service_factory = ServiceFactory(db)
        entity_media_service = service_factory.get_entity_media_service()

        # Delete media for the entity
        success = entity_media_service.remove_entity_media(entity_type, entity_id, media_type)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No media found for {entity_type} {entity_id}"
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting entity media: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete media for {entity_type} {entity_id}: {str(e)}"
        )