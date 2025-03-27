# File: app/api/endpoints/patterns.py
"""
Patterns API endpoints for the HideSync system.

This module defines the API endpoints for managing patterns within the HideSync system,
including pattern creation, retrieval, updates, and specialized operations like
favorites and project type filtering. Patterns represent design templates that can
be used to create leather projects.
"""

from typing import Any, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Body,
    status,
    UploadFile,
    File,
    Form,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.exceptions import (
    EntityNotFoundException,
    ValidationException,
    BusinessRuleException,
)
from app.db.session import get_db
from app.schemas.compatibility import (
    PatternCreate,
    PatternResponse,
    PatternUpdate,
    PatternListResponse,
    ProjectTemplateCreate,
    ProjectTemplateResponse,
)
from app.services.pattern_service import PatternService

router = APIRouter()


@router.get("/", response_model=PatternListResponse)
def list_patterns(
    name: Optional[str] = Query(None, description="Filter by pattern name"),
    project_type: Optional[str] = Query(None, description="Filter by project type"),
    skill_level: Optional[str] = Query(None, description="Filter by skill level"),
    author_name: Optional[str] = Query(None, description="Filter by author name"),
    is_public: Optional[bool] = Query(None, description="Filter by public status"),
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get a list of patterns with optional filtering.
    """
    pattern_service = PatternService(db)

    # Build filter parameters
    filters = {}
    if name:
        filters["name"] = name
    if project_type:
        filters["projectType"] = project_type
    if skill_level:
        filters["skillLevel"] = skill_level
    if author_name:
        filters["authorName"] = author_name
    if is_public is not None:
        filters["isPublic"] = is_public

    patterns = pattern_service.list(skip=skip, limit=limit, **filters)
    total = pattern_service.count(**filters)

    return {"items": patterns, "total": total, "skip": skip, "limit": limit}


@router.post("/", response_model=PatternResponse, status_code=status.HTTP_201_CREATED)
def create_pattern(
    pattern_data: PatternCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Create a new pattern.
    """
    pattern_service = PatternService(db)

    try:
        pattern = pattern_service.create_pattern(pattern_data.dict())
        return pattern
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )


@router.get("/{pattern_id}", response_model=PatternResponse)
def get_pattern(
    pattern_id: int = Path(..., description="The ID of the pattern to retrieve"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get a pattern by ID.
    """
    pattern_service = PatternService(db)
    pattern = pattern_service.get_pattern_with_details(pattern_id)

    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern with ID {pattern_id} not found",
        )

    return pattern


@router.put("/{pattern_id}", response_model=PatternResponse)
def update_pattern(
    pattern_id: int = Path(..., description="The ID of the pattern to update"),
    pattern_data: PatternUpdate = Body(...),
    increment_version: bool = Query(
        False, description="Whether to increment pattern version"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Update a pattern.
    """
    pattern_service = PatternService(db)

    try:
        pattern = pattern_service.update_pattern(
            pattern_id,
            pattern_data.dict(exclude_unset=True),
            increment_version=increment_version,
        )
        return pattern
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern with ID {pattern_id} not found",
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )


@router.delete("/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pattern(
    pattern_id: int = Path(..., description="The ID of the pattern to delete"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> None:
    """
    Delete a pattern.
    """
    pattern_service = PatternService(db)

    try:
        result = pattern_service.delete_pattern(pattern_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pattern with ID {pattern_id} not found",
            )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern with ID {pattern_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# New pattern management endpoints


@router.get("/favorites", response_model=List[PatternResponse])
def get_favorite_patterns(
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get all favorite patterns for the current user.

    Returns a list of patterns that have been marked as favorites,
    allowing users to quickly access their most used patterns.
    """
    pattern_service = PatternService(db)

    # Use the underlying repository to get favorite patterns
    patterns = pattern_service.repository.get_favorite_patterns(skip=skip, limit=limit)

    # Convert to detailed responses
    detailed_patterns = []
    for pattern in patterns:
        detailed = pattern_service.get_pattern_with_details(pattern.id)
        detailed_patterns.append(detailed)

    return detailed_patterns


@router.post("/{pattern_id}/toggle-favorite", response_model=PatternResponse)
def toggle_pattern_favorite(
    pattern_id: int = Path(..., description="The ID of the pattern"),
    is_favorite: bool = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Toggle a pattern as favorite.

    Allows users to mark or unmark patterns as favorites for quick access
    and organization of frequently used patterns.
    """
    pattern_service = PatternService(db)

    try:
        # Check if pattern exists
        pattern = pattern_service.get_by_id(pattern_id)
        if not pattern:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pattern with ID {pattern_id} not found",
            )

        # Toggle favorite status
        updated_pattern = pattern_service.toggle_favorite(pattern_id, is_favorite)

        # Return detailed response
        return pattern_service.get_pattern_with_details(pattern_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern with ID {pattern_id} not found",
        )


@router.get("/by-project-type/{project_type}", response_model=List[PatternResponse])
def get_patterns_by_project_type(
    project_type: str = Path(..., description="The project type to filter by"),
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get patterns by project type.

    Filters patterns by the specified project type, allowing users to
    find patterns for specific types of leather projects (wallets, bags, etc.).
    """
    pattern_service = PatternService(db)

    try:
        # Get patterns by project type
        patterns = pattern_service.get_patterns_by_project_type(project_type)

        # Apply pagination
        paginated_patterns = patterns[skip : skip + limit]

        # Convert to detailed responses
        detailed_patterns = []
        for pattern in paginated_patterns:
            detailed = pattern_service.get_pattern_with_details(pattern.id)
            detailed_patterns.append(detailed)

        return detailed_patterns
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid project type: {project_type}",
        )


@router.post("/{pattern_id}/upload-file", response_model=PatternResponse)
def upload_pattern_file(
    pattern_id: int = Path(..., description="The ID of the pattern"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Upload a pattern file (SVG, PDF, or image).
    """
    pattern_service = PatternService(db)

    try:
        # Read file data
        file_data = file.file.read()

        # Upload file
        updated_pattern = pattern_service.upload_pattern_file(
            pattern_id, file_data, file.filename, file.content_type
        )

        # Return detailed response
        return pattern_service.get_pattern_with_details(pattern_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern with ID {pattern_id} not found",
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )


@router.post(
    "/{pattern_id}/clone",
    response_model=PatternResponse,
    status_code=status.HTTP_201_CREATED,
)
def clone_pattern(
    pattern_id: int = Path(..., description="The ID of the pattern to clone"),
    new_name: str = Body(..., embed=True),
    custom_data: Optional[PatternUpdate] = Body(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Clone an existing pattern.

    Creates a new pattern based on an existing one, including components and material
    requirements. Particularly useful for creating variations of a pattern.
    """
    pattern_service = PatternService(db)

    try:
        # Clone pattern
        custom_dict = custom_data.dict(exclude_unset=True) if custom_data else None
        cloned_pattern = pattern_service.clone_pattern(
            pattern_id, new_name, custom_dict
        )

        # Return detailed response
        return pattern_service.get_pattern_with_details(cloned_pattern.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern with ID {pattern_id} not found",
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )


# Project Template endpoints


@router.post(
    "/templates",
    response_model=ProjectTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_template(
    template_data: ProjectTemplateCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Create a new project template from a pattern.
    """
    pattern_service = PatternService(db)

    try:
        template = pattern_service.create_project_template(template_data.dict())
        return pattern_service.get_template_with_details(template.id)
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
