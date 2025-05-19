# app/api/endpoints/presets.py

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, File, UploadFile, Form
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
import json
import io

from app.api.deps import get_db, get_current_active_user, get_enum_service, get_settings_service
from app.schemas.preset import (
    PresetRead, PresetCreate, PresetUpdate, PresetList,
    PresetApplicationOptions, PresetApplicationResult
)
from app.services.preset_service import PresetService
from app.services.property_definition_service import PropertyDefinitionService
from app.services.material_type_service import MaterialTypeService
from app.services.dynamic_material_service import DynamicMaterialService
from app.services.settings_service import SettingsService
from app.core.exceptions import (
    ValidationException, EntityNotFoundException
)

router = APIRouter()


def get_preset_service(
        db: Session = Depends(get_db),
        enum_service=Depends(get_enum_service),
        settings_service: SettingsService = Depends(get_settings_service),
        security_context=Depends(get_security_context)
) -> PresetService:
    """Provide PresetService instance."""
    property_service = PropertyDefinitionService(db, enum_service=enum_service)
    material_type_service = MaterialTypeService(db, property_repository=property_service.repository)
    material_service = DynamicMaterialService(
        db,
        property_service=property_service,
        material_type_service=material_type_service,
        security_context=security_context,
        settings_service=settings_service
    )

    return PresetService(
        db,
        property_service=property_service,
        material_type_service=material_type_service,
        material_service=material_service,
        settings_service=settings_service,
        security_context=security_context
    )


@router.get("/", response_model=PresetList)
def list_presets(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: PresetService = Depends(get_preset_service),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        search: Optional[str] = Query(None, description="Search term for name and description"),
        is_public: Optional[bool] = Query(None, description="Filter by public status"),
        tags: Optional[List[str]] = Query(None, description="Filter by tag names")
):
    """
    List presets with optional filtering and pagination.
    """
    # Get current user's presets and public presets
    presets, total = service.get_presets(
        skip=skip,
        limit=limit,
        search=search,
        user_id=None,  # Don't filter by user so we get all public presets
        is_public=is_public,
        tags=tags
    )

    # Filter out non-public presets that don't belong to the user
    filtered_presets = [p for p in presets if p.is_public or p.created_by == current_user.id]

    return {
        "items": filtered_presets,
        "total": len(filtered_presets),  # Simplified for this example
        "page": skip // limit + 1 if limit > 0 else 1,
        "size": limit,
        "pages": (total + limit - 1) // limit if limit > 0 else 1
    }


@router.post("/", response_model=PresetRead, status_code=status.HTTP_201_CREATED)
def create_preset(
        *,
        db: Session = Depends(get_db),
        preset_in: PresetCreate,
        current_user=Depends(get_current_active_user),
        service: PresetService = Depends(get_preset_service)
):
    """
    Create a new preset.
    """
    try:
        return service.create_preset(
            name=preset_in.name,
            description=preset_in.description,
            author=preset_in.author or current_user.username,
            is_public=preset_in.is_public,
            config=preset_in.config.dict(),
            created_by=current_user.id
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@router.get("/{preset_id}", response_model=PresetRead)
def get_preset(
        *,
        db: Session = Depends(get_db),
        preset_id: int = Path(..., gt=0, description="The ID of the preset"),
        current_user=Depends(get_current_active_user),
        service: PresetService = Depends(get_preset_service)
):
    """
    Get a specific preset by ID.
    """
    preset = service.get_preset(preset_id)
    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset with ID {preset_id} not found"
        )

    # Check access permissions
    if not preset.is_public and preset.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this preset"
        )

    return preset


@router.put("/{preset_id}", response_model=PresetRead)
def update_preset(
        *,
        db: Session = Depends(get_db),
        preset_id: int = Path(..., gt=0, description="The ID of the preset"),
        preset_in: PresetUpdate,
        current_user=Depends(get_current_active_user),
        service: PresetService = Depends(get_preset_service)
):
    """
    Update a preset.
    """
    # Check if preset exists and user has permission
    preset = service.get_preset(preset_id)
    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset with ID {preset_id} not found"
        )

    if preset.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this preset"
        )

    try:
        updated_preset = service.update_preset(
            preset_id=preset_id,
            data=preset_in.dict(exclude_unset=True)
        )

        if not updated_preset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Preset with ID {preset_id} not found"
            )

        return updated_preset
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_preset(
        *,
        db: Session = Depends(get_db),
        preset_id: int = Path(..., gt=0, description="The ID of the preset"),
        current_user=Depends(get_current_active_user),
        service: PresetService = Depends(get_preset_service)
):
    """
    Delete a preset.
    """
    # Check if preset exists and user has permission
    preset = service.get_preset(preset_id)
    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset with ID {preset_id} not found"
        )

    if preset.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this preset"
        )

    result = service.delete_preset(preset_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset with ID {preset_id} not found"
        )

    return None


@router.post("/import", response_model=PresetRead)
async def import_preset(
        *,
        db: Session = Depends(get_db),
        file: UploadFile = File(...),
        current_user=Depends(get_current_active_user),
        service: PresetService = Depends(get_preset_service)
):
    """
    Import a preset from a JSON file.
    """
    try:
        # Read file content
        content = await file.read()

        # Parse JSON
        try:
            preset_data = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON file"
            )

        # Extract metadata
        if not isinstance(preset_data, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid preset format, expected JSON object"
            )

        name = preset_data.get("name")
        if not name:
            # Try to get name from metadata
            metadata = preset_data.get("metadata", {})
            if isinstance(metadata, dict):
                name = metadata.get("name", "Imported Preset")
            else:
                name = "Imported Preset"

        description = preset_data.get("description")
        author = preset_data.get("author")

        # Create preset
        preset = service.create_preset(
            name=name,
            description=description,
            author=author,
            is_public=False,
            config=preset_data,
            created_by=current_user.id
        )

        return preset
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@router.get("/{preset_id}/export")
def export_preset(
        *,
        db: Session = Depends(get_db),
        preset_id: int = Path(..., gt=0, description="The ID of the preset"),
        current_user=Depends(get_current_active_user),
        service: PresetService = Depends(get_preset_service)
):
    """
    Export a preset as a JSON file.
    """
    preset = service.get_preset(preset_id)
    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset with ID {preset_id} not found"
        )

    # Check access permissions
    if not preset.is_public and preset.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this preset"
        )

    # Create a JSON file in memory
    config_json = json.dumps(preset.config, indent=2)

    # Create a stream for the response
    stream = io.StringIO(config_json)

    # Generate filename
    filename = f"{preset.name.replace(' ', '_')}_preset.json"

    # Return streaming response
    return StreamingResponse(
        io.BytesIO(stream.getvalue().encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/{preset_id}/apply", response_model=PresetApplicationResult)
def apply_preset(
        *,
        db: Session = Depends(get_db),
        preset_id: int = Path(..., gt=0, description="The ID of the preset"),
        options: PresetApplicationOptions,
        current_user=Depends(get_current_active_user),
        service: PresetService = Depends(get_preset_service)
):
    """
    Apply a preset to create/update material types and properties.
    """
    try:
        result = service.apply_preset(
            preset_id=preset_id,
            options=options.dict(),
            user_id=current_user.id
        )

        return result
    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@router.post("/generate", response_model=PresetRead)
def generate_preset(
        *,
        db: Session = Depends(get_db),
        material_type_ids: List[int],
        name: str = Query(..., description="Name for the generated preset"),
        description: Optional[str] = Query(None, description="Description for the preset"),
        include_samples: bool = Query(True, description="Whether to include sample materials"),
        include_settings: bool = Query(True, description="Whether to include settings"),
        current_user=Depends(get_current_active_user),
        service: PresetService = Depends(get_preset_service)
):
    """
    Generate a preset from existing material types.
    """
    try:
        # Generate preset configuration
        config = service.generate_preset_from_system(
            material_type_ids=material_type_ids,
            include_samples=include_samples,
            include_settings=include_settings,
            user_id=current_user.id
        )

        # Create preset
        preset = service.create_preset(
            name=name,
            description=description,
            author=current_user.username,
            is_public=False,
            config=config,
            created_by=current_user.id
        )

        return preset
    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )