# app/api/endpoints/recurring_projects.py
"""
Recurring Projects API endpoints for HideSync.

This module provides endpoints for managing recurring projects,
including creation, retrieval, project generation, and scheduling.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.recurring_project import (
    RecurringProject,
    RecurringProjectCreate,
    RecurringProjectUpdate,
    RecurringProjectWithDetails,
    GeneratedProject,
)
from app.services.recurring_project_service import RecurringProjectService
from app.core.exceptions import EntityNotFoundException, BusinessRuleException

router = APIRouter()


@router.get("/", response_model=List[RecurringProject])
def list_recurring_projects(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    project_type: Optional[str] = Query(None, description="Filter by project type"),
):
    """
    List recurring projects with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        is_active: Optional filter by active status
        project_type: Optional filter by project type

    Returns:
        List of recurring project records
    """
    recurring_project_service = RecurringProjectService(db)

    filters = {}
    if is_active is not None:
        filters["is_active"] = is_active
    if project_type:
        filters["project_type"] = project_type

    return recurring_project_service.list_recurring_projects(
        skip=skip, limit=limit, **filters
    )


@router.post("/", response_model=RecurringProject, status_code=status.HTTP_201_CREATED)
def create_recurring_project(
    *,
    db: Session = Depends(get_db),
    project_in: RecurringProjectCreate,
    current_user: Any = Depends(get_current_active_user),
):
    """
    Create a new recurring project.

    Args:
        db: Database session
        project_in: Recurring project data for creation
        current_user: Currently authenticated user

    Returns:
        Created recurring project information

    Raises:
        HTTPException: If recurring project creation fails due to business rules
    """
    recurring_project_service = RecurringProjectService(db)
    try:
        return recurring_project_service.create_recurring_project(
            project_in, current_user.id
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{project_id}", response_model=RecurringProjectWithDetails)
def get_recurring_project(
    *,
    db: Session = Depends(get_db),
    project_id: str = Path(
        ..., description="The ID of the recurring project to retrieve"
    ),
    current_user: Any = Depends(get_current_active_user),
):
    """
    Get detailed information about a specific recurring project.

    Args:
        db: Database session
        project_id: ID of the recurring project to retrieve
        current_user: Currently authenticated user

    Returns:
        Recurring project information with details

    Raises:
        HTTPException: If the recurring project doesn't exist
    """
    recurring_project_service = RecurringProjectService(db)
    try:
        return recurring_project_service.get_recurring_project_with_details(project_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recurring project with ID {project_id} not found",
        )


@router.patch("/{project_id}", response_model=RecurringProject)
def update_recurring_project(
    *,
    db: Session = Depends(get_db),
    project_id: str = Path(
        ..., description="The ID of the recurring project to update"
    ),
    project_in: RecurringProjectUpdate,
    current_user: Any = Depends(get_current_active_user),
):
    """
    Update a recurring project.

    Args:
        db: Database session
        project_id: ID of the recurring project to update
        project_in: Updated recurring project data
        current_user: Currently authenticated user

    Returns:
        Updated recurring project information

    Raises:
        HTTPException: If the recurring project doesn't exist or update violates business rules
    """
    recurring_project_service = RecurringProjectService(db)
    try:
        return recurring_project_service.update_recurring_project(
            project_id, project_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recurring project with ID {project_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_project(
    *,
    db: Session = Depends(get_db),
    project_id: str = Path(
        ..., description="The ID of the recurring project to delete"
    ),
    current_user: Any = Depends(get_current_active_user),
):
    """
    Delete a recurring project.

    Args:
        db: Database session
        project_id: ID of the recurring project to delete
        current_user: Currently authenticated user

    Raises:
        HTTPException: If the recurring project doesn't exist or can't be deleted
    """
    recurring_project_service = RecurringProjectService(db)
    try:
        recurring_project_service.delete_recurring_project(project_id, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recurring project with ID {project_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{project_id}/generate", response_model=GeneratedProject)
def generate_project_instance(
    *,
    db: Session = Depends(get_db),
    project_id: str = Path(..., description="The ID of the recurring project"),
    scheduled_date: Optional[str] = Body(
        None,
        embed=True,
        description="Optional specific date for generation (YYYY-MM-DD)",
    ),
    current_user: Any = Depends(get_current_active_user),
):
    """
    Generate a project instance from a recurring project.

    Args:
        db: Database session
        project_id: ID of the recurring project
        scheduled_date: Optional specific date for generation
        current_user: Currently authenticated user

    Returns:
        Generated project instance

    Raises:
        HTTPException: If the recurring project doesn't exist or generation fails
    """
    recurring_project_service = RecurringProjectService(db)
    try:
        return recurring_project_service.generate_project_instance(
            project_id, scheduled_date, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recurring project with ID {project_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/upcoming", response_model=List[RecurringProjectWithDetails])
def get_upcoming_recurring_projects(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    days: int = Query(7, ge=1, le=365, description="Number of days to look ahead"),
    limit: int = Query(
        10, ge=1, le=100, description="Maximum number of projects to return"
    ),
):
    """
    Get upcoming recurring projects scheduled within the specified time frame.

    Args:
        db: Database session
        current_user: Currently authenticated user
        days: Number of days to look ahead
        limit: Maximum number of projects to return

    Returns:
        List of upcoming recurring projects with details
    """
    recurring_project_service = RecurringProjectService(db)
    return recurring_project_service.get_upcoming_recurring_projects(days, limit)


@router.get("/due-this-week", response_model=List[RecurringProject])
def get_projects_due_this_week(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
):
    """
    Get recurring projects with occurrences due this week.

    Args:
        db: Database session
        current_user: Currently authenticated user

    Returns:
        List of recurring projects with occurrences due this week
    """
    recurring_project_service = RecurringProjectService(db)
    return recurring_project_service.get_projects_due_this_week()


@router.get("/count", response_model=dict)
def get_recurring_project_count(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
):
    """
    Get count of recurring projects by status.

    Args:
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Dictionary with counts by status
    """
    recurring_project_service = RecurringProjectService(db)
    return recurring_project_service.get_recurring_project_count()


# Add this endpoint to your app/api/endpoints/recurring_projects.py file

@router.patch("/{project_id}/toggle-active", response_model=RecurringProject)
def toggle_recurring_project_active_state(
        *,
        db: Session = Depends(get_db),
        project_id: str = Path(
            ..., description="The ID of the recurring project to toggle"
        ),
        current_user: Any = Depends(get_current_active_user),
):
    """
    Toggle the active state of a recurring project.

    This endpoint allows quickly activating or deactivating a recurring project
    without needing to perform a full update.

    Args:
        db: Database session
        project_id: ID of the recurring project to toggle
        current_user: Currently authenticated user

    Returns:
        Updated recurring project information

    Raises:
        HTTPException: If the recurring project doesn't exist or update fails
    """
    recurring_project_service = RecurringProjectService(db)
    try:
        # Get the current recurring project to determine its active state
        project = recurring_project_service.get_recurring_project_with_details(project_id)

        # Toggle the is_active state
        update_data = {"is_active": not project['is_active']}

        # Update the recurring project
        return recurring_project_service.update_recurring_project(
            project_id, update_data, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recurring project with ID {project_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))