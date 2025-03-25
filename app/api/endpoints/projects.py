# File: app/api/endpoints/projects.py
"""
Project API endpoints for HideSync.

This module provides endpoints for managing projects, including
project creation, status updates, components, and timelines.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.compatibility import (
    Project,
    ProjectCreate,
    ProjectUpdate,
    ProjectWithDetails,
    ProjectSearchParams,
    ProjectComponent,
    ProjectComponentCreate,
    TimelineTask,
    TimelineTaskCreate,
    TimelineTaskUpdate,
)
from app.services.project_service import ProjectService
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
)
from app.core.exceptions import (
    InsufficientInventoryException as InsufficientQuantityException,
)

router = APIRouter()


@router.get("/", response_model=List[Project])
def list_projects(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    status: Optional[str] = Query(None, description="Filter by project status"),
    type: Optional[str] = Query(None, description="Filter by project type"),
    customer_id: Optional[int] = Query(None, ge=1, description="Filter by customer ID"),
    search: Optional[str] = Query(None, description="Search term for project name"),
) -> List[Project]:
    """
    Retrieve projects with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        status: Optional filter by project status
        type: Optional filter by project type
        customer_id: Optional filter by customer ID
        search: Optional search term for project name

    Returns:
        List of project records
    """
    search_params = ProjectSearchParams(
        status=status, type=type, customer_id=customer_id, search=search
    )

    project_service = ProjectService(db)
    return project_service.get_projects(
        skip=skip, limit=limit, search_params=search_params
    )


@router.post("/", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(
    *,
    db: Session = Depends(get_db),
    project_in: ProjectCreate,
    current_user: Any = Depends(get_current_active_user),
) -> Project:
    """
    Create a new project.

    Args:
        db: Database session
        project_in: Project data for creation
        current_user: Currently authenticated user

    Returns:
        Created project information

    Raises:
        HTTPException: If project creation fails due to business rules
    """
    project_service = ProjectService(db)
    try:
        return project_service.create_project(project_in, current_user.id)
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{project_id}", response_model=ProjectWithDetails)
def get_project(
    *,
    db: Session = Depends(get_db),
    project_id: int = Path(..., ge=1, description="The ID of the project to retrieve"),
    current_user: Any = Depends(get_current_active_user),
) -> ProjectWithDetails:
    """
    Get detailed information about a specific project.

    Args:
        db: Database session
        project_id: ID of the project to retrieve
        current_user: Currently authenticated user

    Returns:
        Project information with details including components and timeline

    Raises:
        HTTPException: If the project doesn't exist
    """
    project_service = ProjectService(db)
    try:
        return project_service.get_project_with_details(project_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )


@router.put("/{project_id}", response_model=Project)
def update_project(
    *,
    db: Session = Depends(get_db),
    project_id: int = Path(..., ge=1, description="The ID of the project to update"),
    project_in: ProjectUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> Project:
    """
    Update a project.

    Args:
        db: Database session
        project_id: ID of the project to update
        project_in: Updated project data
        current_user: Currently authenticated user

    Returns:
        Updated project information

    Raises:
        HTTPException: If the project doesn't exist or update violates business rules
    """
    project_service = ProjectService(db)
    try:
        return project_service.update_project(project_id, project_in, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    *,
    db: Session = Depends(get_db),
    project_id: int = Path(..., ge=1, description="The ID of the project to delete"),
    current_user: Any = Depends(get_current_active_user),
) -> None:
    """
    Delete a project.

    Args:
        db: Database session
        project_id: ID of the project to delete
        current_user: Currently authenticated user

    Raises:
        HTTPException: If the project doesn't exist or can't be deleted
    """
    project_service = ProjectService(db)
    try:
        project_service.delete_project(project_id, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{project_id}/status", response_model=Project)
def update_project_status(
    *,
    db: Session = Depends(get_db),
    project_id: int = Path(..., ge=1, description="The ID of the project"),
    status: str = Body(..., embed=True, description="New project status"),
    current_user: Any = Depends(get_current_active_user),
) -> Project:
    """
    Update a project's status.

    Args:
        db: Database session
        project_id: ID of the project
        status: New status for the project
        current_user: Currently authenticated user

    Returns:
        Updated project information

    Raises:
        HTTPException: If the project doesn't exist or status transition is invalid
    """
    project_service = ProjectService(db)
    try:
        return project_service.update_project_status(
            project_id, status, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )
    except InvalidStatusTransitionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Project Components
@router.get("/{project_id}/components", response_model=List[ProjectComponent])
def list_project_components(
    *,
    db: Session = Depends(get_db),
    project_id: int = Path(..., ge=1, description="The ID of the project"),
    current_user: Any = Depends(get_current_active_user),
) -> List[ProjectComponent]:
    """
    List all components for a project.

    Args:
        db: Database session
        project_id: ID of the project
        current_user: Currently authenticated user

    Returns:
        List of project components

    Raises:
        HTTPException: If the project doesn't exist
    """
    project_service = ProjectService(db)
    try:
        return project_service.get_project_components(project_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )


@router.post(
    "/{project_id}/components",
    response_model=ProjectComponent,
    status_code=status.HTTP_201_CREATED,
)
def add_project_component(
    *,
    db: Session = Depends(get_db),
    project_id: int = Path(..., ge=1, description="The ID of the project"),
    component_in: ProjectComponentCreate,
    current_user: Any = Depends(get_current_active_user),
) -> ProjectComponent:
    """
    Add a component to a project.

    Args:
        db: Database session
        project_id: ID of the project
        component_in: Component data to add
        current_user: Currently authenticated user

    Returns:
        Added project component

    Raises:
        HTTPException: If the project doesn't exist or component can't be added
    """
    project_service = ProjectService(db)
    try:
        return project_service.add_project_component(
            project_id, component_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Timeline Tasks
@router.get("/{project_id}/timeline", response_model=List[TimelineTask])
def list_timeline_tasks(
    *,
    db: Session = Depends(get_db),
    project_id: int = Path(..., ge=1, description="The ID of the project"),
    current_user: Any = Depends(get_current_active_user),
) -> List[TimelineTask]:
    """
    List all timeline tasks for a project.

    Args:
        db: Database session
        project_id: ID of the project
        current_user: Currently authenticated user

    Returns:
        List of timeline tasks

    Raises:
        HTTPException: If the project doesn't exist
    """
    project_service = ProjectService(db)
    try:
        return project_service.get_timeline_tasks(project_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )


@router.post(
    "/{project_id}/timeline",
    response_model=TimelineTask,
    status_code=status.HTTP_201_CREATED,
)
def add_timeline_task(
    *,
    db: Session = Depends(get_db),
    project_id: int = Path(..., ge=1, description="The ID of the project"),
    task_in: TimelineTaskCreate,
    current_user: Any = Depends(get_current_active_user),
) -> TimelineTask:
    """
    Add a timeline task to a project.

    Args:
        db: Database session
        project_id: ID of the project
        task_in: Task data to add
        current_user: Currently authenticated user

    Returns:
        Added timeline task

    Raises:
        HTTPException: If the project doesn't exist or task can't be added
    """
    project_service = ProjectService(db)
    try:
        return project_service.add_timeline_task(project_id, task_in, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{project_id}/timeline/{task_id}", response_model=TimelineTask)
def update_timeline_task(
    *,
    db: Session = Depends(get_db),
    project_id: int = Path(..., ge=1, description="The ID of the project"),
    task_id: int = Path(..., ge=1, description="The ID of the task"),
    task_in: TimelineTaskUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> TimelineTask:
    """
    Update a timeline task.

    Args:
        db: Database session
        project_id: ID of the project
        task_id: ID of the task to update
        task_in: Updated task data
        current_user: Currently authenticated user

    Returns:
        Updated timeline task

    Raises:
        HTTPException: If the project or task doesn't exist
    """
    project_service = ProjectService(db)
    try:
        return project_service.update_timeline_task(
            project_id, task_id, task_in, current_user.id
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
