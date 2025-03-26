# File: app/api/endpoints/materials.py
"""
Material API endpoints for HideSync.

This module provides endpoints for managing material data,
including inventory tracking, material types, and related operations.
It includes specialized endpoints for leather, hardware, and supplies materials.
"""

from typing import Any, List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.schemas.material import (
    MaterialResponse as Material,  # Updated alias here
    MaterialCreate,
    MaterialUpdate,
    MaterialSearchParams,
)
from app.schemas.leather_material import (
    LeatherMaterialCreate,
    LeatherMaterialUpdate,
    LeatherMaterialResponse,
    LeatherMaterialList,
)
from app.schemas.hardware_material import (
    HardwareMaterialCreate,
    HardwareMaterialUpdate,
    HardwareMaterialResponse,
    HardwareMaterialList,
)
from app.schemas.supplies_material import (
    SuppliesMaterialCreate,
    SuppliesMaterialUpdate,
    SuppliesMaterialResponse,
    SuppliesMaterialList,
)
from app.services.material_service import MaterialService
from app.db.models.leather_material_service import LeatherMaterialService
from app.db.models.hardware_material_service import HardwareMaterialService
from app.db.models.supplies_material_service import SuppliesMaterialService
from app.db.models.enums import (
    MaterialType,
    LeatherType,
    LeatherFinish,
    HardwareType,
    HardwareMaterial as HardwareMaterialEnum,
    HardwareFinish,
)
from app.core.exceptions import (
    EntityNotFoundException,
    MaterialNotFoundException,
    BusinessRuleException,
    ValidationException,
    InsufficientInventoryException,
)

router = APIRouter()


# Generic material endpoints
@router.get("/", response_model=List[Material])
def list_materials(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    material_type: Optional[str] = Query(None, description="Filter by material type"),
    quality: Optional[str] = Query(None, description="Filter by material quality"),
    in_stock: Optional[bool] = Query(None, description="Filter by availability"),
    search: Optional[str] = Query(None, description="Search term for name"),
) -> List[Material]:
    """
    Retrieve materials with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        material_type: Optional filter by material type
        quality: Optional filter by material quality
        in_stock: Optional filter by stock availability
        search: Optional search term for name

    Returns:
        List of material records
    """
    search_params = MaterialSearchParams(
        material_type=material_type, quality=quality, in_stock=in_stock, search=search
    )

    material_service = MaterialService(db)
    return material_service.get_materials(
        skip=skip, limit=limit, search_params=search_params
    )


@router.post("/", response_model=Material, status_code=status.HTTP_201_CREATED)
def create_material(
    *,
    db: Session = Depends(get_db),
    material_in: MaterialCreate,
    current_user: Any = Depends(get_current_active_user),
) -> Material:
    """
    Create a new material.

    Args:
        db: Database session
        material_in: Material data for creation
        current_user: Currently authenticated user

    Returns:
        Created material information

    Raises:
        HTTPException: If material creation fails due to business rules
    """
    material_service = MaterialService(db)
    try:
        return material_service.create_material(material_in, current_user.id)
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{material_id}", response_model=Material)
def get_material(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(
        ..., ge=1, description="The ID of the material to retrieve"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> Material:
    """
    Get detailed information about a specific material.

    Args:
        db: Database session
        material_id: ID of the material to retrieve
        current_user: Currently authenticated user

    Returns:
        Material information

    Raises:
        HTTPException: If the material doesn't exist
    """
    material_service = MaterialService(db)
    try:
        return material_service.get_material(material_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )


@router.put("/{material_id}", response_model=Material)
def update_material(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(..., ge=1, description="The ID of the material to update"),
    material_in: MaterialUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> Material:
    """
    Update a material.

    Args:
        db: Database session
        material_id: ID of the material to update
        material_in: Updated material data
        current_user: Currently authenticated user

    Returns:
        Updated material information

    Raises:
        HTTPException: If the material doesn't exist or update violates business rules
    """
    material_service = MaterialService(db)
    try:
        return material_service.update_material(
            material_id, material_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(..., ge=1, description="The ID of the material to delete"),
    current_user: Any = Depends(get_current_active_user),
) -> None:
    """
    Delete a material.

    Args:
        db: Database session
        material_id: ID of the material to delete
        current_user: Currently authenticated user

    Raises:
        HTTPException: If the material doesn't exist or can't be deleted
    """
    material_service = MaterialService(db)
    try:
        material_service.delete_material(material_id, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{material_id}/adjust-stock", response_model=Material)
def adjust_material_stock(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(..., ge=1, description="The ID of the material"),
    quantity: float = Query(
        ..., description="Quantity to add (positive) or remove (negative)"
    ),
    notes: Optional[str] = Query(None, description="Notes for this stock adjustment"),
    current_user: Any = Depends(get_current_active_user),
) -> Material:
    """
    Adjust the stock quantity of a material.

    Args:
        db: Database session
        material_id: ID of the material
        quantity: Quantity to add (positive) or remove (negative)
        notes: Optional notes for this adjustment
        current_user: Currently authenticated user

    Returns:
        Updated material information

    Raises:
        HTTPException: If the material doesn't exist or adjustment isn't possible
    """
    material_service = MaterialService(db)
    try:
        return material_service.adjust_stock(
            material_id, quantity, notes, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except InsufficientInventoryException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient quantity available for this adjustment",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Leather material endpoints
@router.get("/leather", response_model=List[LeatherMaterialResponse])
def list_leather_materials(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    leather_type: Optional[LeatherType] = Query(None, description="Filter by leather type"),
    min_thickness: Optional[float] = Query(None, ge=0, description="Minimum thickness in mm"),
    max_thickness: Optional[float] = Query(None, ge=0, description="Maximum thickness in mm"),
    animal_source: Optional[str] = Query(None, description="Filter by animal source"),
    finish: Optional[LeatherFinish] = Query(None, description="Filter by finish type"),
    color: Optional[str] = Query(None, description="Filter by color"),
    is_full_hide: Optional[bool] = Query(None, description="Filter for full hides"),
) -> List[LeatherMaterialResponse]:
    """
    Retrieve leather materials with specialized filtering options.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        leather_type: Optional filter by leather type
        min_thickness: Optional minimum thickness filter
        max_thickness: Optional maximum thickness filter
        animal_source: Optional filter by animal source
        finish: Optional filter by finish type
        color: Optional filter by color
        is_full_hide: Optional filter for full hides

    Returns:
        List of leather material records
    """
    leather_service = LeatherMaterialService(db)
    return leather_service.get_leather_materials(
        skip=skip,
        limit=limit,
        leather_type=leather_type,
        min_thickness=min_thickness,
        max_thickness=max_thickness,
        animal_source=animal_source,
        finish=finish,
        color=color,
        is_full_hide=is_full_hide,
    )


@router.post("/leather", response_model=LeatherMaterialResponse, status_code=status.HTTP_201_CREATED)
def create_leather_material(
    *,
    db: Session = Depends(get_db),
    material_in: LeatherMaterialCreate,
    current_user: Any = Depends(get_current_active_user),
) -> LeatherMaterialResponse:
    """
    Create a new leather material.

    Args:
        db: Database session
        material_in: Leather material data for creation
        current_user: Currently authenticated user

    Returns:
        Created leather material information

    Raises:
        HTTPException: If material creation fails due to validation or business rules
    """
    leather_service = LeatherMaterialService(db)
    try:
        return leather_service.create_leather_material(material_in, current_user.id)
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.details}
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/leather/{material_id}", response_model=LeatherMaterialResponse)
def get_leather_material(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(
        ..., ge=1, description="The ID of the leather material to retrieve"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> LeatherMaterialResponse:
    """
    Get detailed information about a specific leather material.

    Args:
        db: Database session
        material_id: ID of the leather material to retrieve
        current_user: Currently authenticated user

    Returns:
        Leather material information

    Raises:
        HTTPException: If the material doesn't exist or is not a leather material
    """
    leather_service = LeatherMaterialService(db)
    try:
        return leather_service.get_leather_material_by_id(material_id)
    except MaterialNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/leather/{material_id}", response_model=LeatherMaterialResponse)
def update_leather_material(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(..., ge=1, description="The ID of the leather material to update"),
    material_in: LeatherMaterialUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> LeatherMaterialResponse:
    """
    Update a leather material.

    Args:
        db: Database session
        material_id: ID of the leather material to update
        material_in: Updated leather material data
        current_user: Currently authenticated user

    Returns:
        Updated leather material information

    Raises:
        HTTPException: If the material doesn't exist, is not a leather material, or update violates business rules
    """
    leather_service = LeatherMaterialService(db)
    try:
        return leather_service.update_leather_material(
            material_id, material_in, current_user.id
        )
    except MaterialNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.details}
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/leather/area-value/{material_id}", response_model=Dict[str, Any])
def calculate_leather_area_value(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(
        ..., ge=1, description="The ID of the leather material"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Calculate the value per area unit of a leather material.

    Args:
        db: Database session
        material_id: ID of the leather material
        current_user: Currently authenticated user

    Returns:
        Dictionary with value metrics

    Raises:
        HTTPException: If the material doesn't exist or metrics can't be calculated
    """
    leather_service = LeatherMaterialService(db)
    try:
        return leather_service.calculate_leather_area_value(material_id)
    except MaterialNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Hardware material endpoints
@router.get("/hardware", response_model=List[HardwareMaterialResponse])
def list_hardware_materials(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    hardware_type: Optional[HardwareType] = Query(None, description="Filter by hardware type"),
    hardware_material: Optional[HardwareMaterialEnum] = Query(None, description="Filter by hardware material"),
    finish: Optional[HardwareFinish] = Query(None, description="Filter by finish"),
    size: Optional[str] = Query(None, description="Filter by size"),
    color: Optional[str] = Query(None, description="Filter by color"),
) -> List[HardwareMaterialResponse]:
    """
    Retrieve hardware materials with specialized filtering options.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        hardware_type: Optional filter by hardware type
        hardware_material: Optional filter by hardware material
        finish: Optional filter by finish
        size: Optional filter by size
        color: Optional filter by color

    Returns:
        List of hardware material records
    """
    hardware_service = HardwareMaterialService(db)
    return hardware_service.get_hardware_materials(
        skip=skip,
        limit=limit,
        hardware_type=hardware_type,
        hardware_material=hardware_material,
        finish=finish,
        size=size,
        color=color,
    )


@router.post("/hardware", response_model=HardwareMaterialResponse, status_code=status.HTTP_201_CREATED)
def create_hardware_material(
    *,
    db: Session = Depends(get_db),
    material_in: HardwareMaterialCreate,
    current_user: Any = Depends(get_current_active_user),
) -> HardwareMaterialResponse:
    """
    Create a new hardware material.

    Args:
        db: Database session
        material_in: Hardware material data for creation
        current_user: Currently authenticated user

    Returns:
        Created hardware material information

    Raises:
        HTTPException: If material creation fails due to validation or business rules
    """
    hardware_service = HardwareMaterialService(db)
    try:
        return hardware_service.create_hardware_material(material_in, current_user.id)
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.details}
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/hardware/{material_id}", response_model=HardwareMaterialResponse)
def get_hardware_material(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(
        ..., ge=1, description="The ID of the hardware material to retrieve"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> HardwareMaterialResponse:
    """
    Get detailed information about a specific hardware material.

    Args:
        db: Database session
        material_id: ID of the hardware material to retrieve
        current_user: Currently authenticated user

    Returns:
        Hardware material information

    Raises:
        HTTPException: If the material doesn't exist or is not a hardware material
    """
    hardware_service = HardwareMaterialService(db)
    try:
        return hardware_service.get_hardware_material_by_id(material_id)
    except MaterialNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/hardware/{material_id}", response_model=HardwareMaterialResponse)
def update_hardware_material(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(..., ge=1, description="The ID of the hardware material to update"),
    material_in: HardwareMaterialUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> HardwareMaterialResponse:
    """
    Update a hardware material.

    Args:
        db: Database session
        material_id: ID of the hardware material to update
        material_in: Updated hardware material data
        current_user: Currently authenticated user

    Returns:
        Updated hardware material information

    Raises:
        HTTPException: If the material doesn't exist, is not a hardware material, or update violates business rules
    """
    hardware_service = HardwareMaterialService(db)
    try:
        return hardware_service.update_hardware_material(
            material_id, material_in, current_user.id
        )
    except MaterialNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.details}
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/hardware/by-type/{hardware_type}", response_model=List[HardwareMaterialResponse])
def get_hardware_by_type(
    *,
    db: Session = Depends(get_db),
    hardware_type: HardwareType = Path(..., description="Hardware type to filter by"),
    size: Optional[str] = Query(None, description="Optional size filter"),
    current_user: Any = Depends(get_current_active_user),
) -> List[HardwareMaterialResponse]:
    """
    Get hardware materials filtered by type and optional size.

    Args:
        db: Database session
        hardware_type: Type of hardware to filter by
        size: Optional size filter
        current_user: Currently authenticated user

    Returns:
        List of matching hardware materials
    """
    hardware_service = HardwareMaterialService(db)
    return hardware_service.get_hardware_by_type_and_size(hardware_type, size)


@router.get("/hardware/compatible/{project_id}", response_model=List[Dict[str, Any]])
def get_compatible_hardware(
    *,
    db: Session = Depends(get_db),
    project_id: int = Path(..., ge=1, description="Project ID to find compatible hardware for"),
    current_user: Any = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    """
    Get hardware materials compatible with a specific project.

    Args:
        db: Database session
        project_id: ID of the project
        current_user: Currently authenticated user

    Returns:
        List of compatible hardware materials with compatibility scores
    """
    hardware_service = HardwareMaterialService(db)
    return hardware_service.get_compatible_hardware(project_id)


# Supplies material endpoints
@router.get("/supplies", response_model=List[SuppliesMaterialResponse])
def list_supplies_materials(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    supplies_type: Optional[str] = Query(None, description="Filter by supplies type"),
    color: Optional[str] = Query(None, description="Filter by color"),
    thread_thickness: Optional[str] = Query(None, description="Filter by thread thickness"),
    material_composition: Optional[str] = Query(None, description="Filter by material composition"),
    min_volume: Optional[float] = Query(None, ge=0, description="Minimum volume"),
    max_volume: Optional[float] = Query(None, ge=0, description="Maximum volume"),
    min_length: Optional[float] = Query(None, ge=0, description="Minimum length"),
    max_length: Optional[float] = Query(None, ge=0, description="Maximum length"),
) -> List[SuppliesMaterialResponse]:
    """
    Retrieve supplies materials with specialized filtering options.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        supplies_type: Optional filter by supplies type
        color: Optional filter by color
        thread_thickness: Optional filter by thread thickness
        material_composition: Optional filter by material composition
        min_volume: Optional minimum volume
        max_volume: Optional maximum volume
        min_length: Optional minimum length
        max_length: Optional maximum length

    Returns:
        List of supplies material records
    """
    supplies_service = SuppliesMaterialService(db)
    return supplies_service.get_supplies_materials(
        skip=skip,
        limit=limit,
        supplies_type=supplies_type,
        color=color,
        thread_thickness=thread_thickness,
        material_composition=material_composition,
        min_volume=min_volume,
        max_volume=max_volume,
        min_length=min_length,
        max_length=max_length,
    )


@router.post("/supplies", response_model=SuppliesMaterialResponse, status_code=status.HTTP_201_CREATED)
def create_supplies_material(
    *,
    db: Session = Depends(get_db),
    material_in: SuppliesMaterialCreate,
    current_user: Any = Depends(get_current_active_user),
) -> SuppliesMaterialResponse:
    """
    Create a new supplies material.

    Args:
        db: Database session
        material_in: Supplies material data for creation
        current_user: Currently authenticated user

    Returns:
        Created supplies material information

    Raises:
        HTTPException: If material creation fails due to validation or business rules
    """
    supplies_service = SuppliesMaterialService(db)
    try:
        return supplies_service.create_supplies_material(material_in, current_user.id)
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.details}
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/supplies/{material_id}", response_model=SuppliesMaterialResponse)
def get_supplies_material(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(
        ..., ge=1, description="The ID of the supplies material to retrieve"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> SuppliesMaterialResponse:
    """
    Get detailed information about a specific supplies material.

    Args:
        db: Database session
        material_id: ID of the supplies material to retrieve
        current_user: Currently authenticated user

    Returns:
        Supplies material information

    Raises:
        HTTPException: If the material doesn't exist or is not a supplies material
    """
    supplies_service = SuppliesMaterialService(db)
    try:
        return supplies_service.get_supplies_material_by_id(material_id)
    except MaterialNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/supplies/{material_id}", response_model=SuppliesMaterialResponse)
def update_supplies_material(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(..., ge=1, description="The ID of the supplies material to update"),
    material_in: SuppliesMaterialUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> SuppliesMaterialResponse:
    """
    Update a supplies material.

    Args:
        db: Database session
        material_id: ID of the supplies material to update
        material_in: Updated supplies material data
        current_user: Currently authenticated user

    Returns:
        Updated supplies material information

    Raises:
        HTTPException: If the material doesn't exist, is not a supplies material, or update violates business rules
    """
    supplies_service = SuppliesMaterialService(db)
    try:
        return supplies_service.update_supplies_material(
            material_id, material_in, current_user.id
        )
    except MaterialNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(e), "errors": e.details}
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/supplies/by-type/{supplies_type}", response_model=List[SuppliesMaterialResponse])
def get_supplies_by_type(
    *,
    db: Session = Depends(get_db),
    supplies_type: str = Path(..., description="Supplies type to filter by"),
    current_user: Any = Depends(get_current_active_user),
) -> List[SuppliesMaterialResponse]:
    """
    Get supplies materials filtered by type.

    Args:
        db: Database session
        supplies_type: Type of supplies to filter by
        current_user: Currently authenticated user

    Returns:
        List of matching supplies materials
    """
    supplies_service = SuppliesMaterialService(db)
    return supplies_service.get_supplies_by_type(supplies_type)


@router.get("/supplies/usage-rate/{material_id}", response_model=Dict[str, Any])
def get_consumable_usage_rate(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(..., ge=1, description="ID of the supplies material"),
    time_period_days: int = Query(30, ge=1, le=365, description="Time period in days for usage calculation"),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Calculate the usage rate of a consumable supplies material.

    Args:
        db: Database session
        material_id: ID of the supplies material
        time_period_days: Time period in days for usage calculation
        current_user: Currently authenticated user

    Returns:
        Dictionary with usage metrics

    Raises:
        HTTPException: If the material doesn't exist or metrics can't be calculated
    """
    supplies_service = SuppliesMaterialService(db)
    try:
        return supplies_service.get_consumable_usage_rate(material_id, time_period_days)
    except MaterialNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Common endpoints for all material types
@router.get("/low-stock", response_model=List[Material])
def get_low_stock_materials(
    *,
    db: Session = Depends(get_db),
    threshold_percentage: float = Query(
        20.0, ge=0, le=100, description="Threshold percentage for considering low stock"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> List[Material]:
    """
    Get materials that are low in stock (below reorder threshold).

    Args:
        db: Database session
        threshold_percentage: Percentage threshold for considering low stock
        current_user: Currently authenticated user

    Returns:
        List of materials that are low in stock
    """
    material_service = MaterialService(db)
    return material_service.get_low_stock_materials(threshold_percentage)


@router.get("/by-storage/{location_id}", response_model=List[Material])
def get_materials_by_storage_location(
    *,
    db: Session = Depends(get_db),
    location_id: int = Path(..., ge=1, description="Storage location ID"),
    current_user: Any = Depends(get_current_active_user),
) -> List[Material]:
    """
    Get materials stored at a specific location.

    Args:
        db: Database session
        location_id: Storage location ID
        current_user: Currently authenticated user

    Returns:
        List of materials at the specified location
    """
    material_service = MaterialService(db)
    return material_service.get_materials_by_storage_location(location_id)
