# app/api/endpoints/roles.py
"""
Role management API endpoints for HideSync.

This module provides endpoints for managing roles, permissions,
and role assignments.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_current_active_superuser
from app.db.session import get_db
from app.schemas.role import (
    Role,
    RoleCreate,
    RoleUpdate,
    Permission,
    RoleAssignmentCreate,
)
from app.services.role_service import RoleService, PermissionService
from app.core.exceptions import EntityNotFoundException, BusinessRuleException

router = APIRouter()


@router.get("/", response_model=List[Role])
def list_roles(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    search: Optional[str] = Query(None, description="Search for roles by name"),
) -> List[Role]:
    """
    Retrieve roles with optional filtering and pagination.
    """
    role_service = RoleService(db)
    filters = {}

    if search:
        filters["search"] = search

    return role_service.list(skip=skip, limit=limit, **filters)


@router.post("/", response_model=Role, status_code=status.HTTP_201_CREATED)
def create_role(
    *,
    db: Session = Depends(get_db),
    role_in: RoleCreate,
    current_user: Any = Depends(get_current_active_superuser),
) -> Role:
    """
    Create a new role.

    This endpoint requires superuser privileges.
    """
    role_service = RoleService(db)
    try:
        return role_service.create_role(
            name=role_in.name,
            description=role_in.description,
            permission_codes=role_in.permission_codes,
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{role_id}", response_model=Role)
def get_role(
    *,
    db: Session = Depends(get_db),
    role_id: int = Path(..., ge=1, description="The ID of the role to retrieve"),
    current_user: Any = Depends(get_current_active_user),
) -> Role:
    """
    Get detailed information about a specific role.
    """
    role_service = RoleService(db)
    try:
        return role_service.get_role_with_permissions(role_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found",
        )


@router.put("/{role_id}", response_model=Role)
def update_role(
    *,
    db: Session = Depends(get_db),
    role_id: int = Path(..., ge=1, description="The ID of the role to update"),
    role_in: RoleUpdate,
    current_user: Any = Depends(get_current_active_superuser),
) -> Role:
    """
    Update a role.

    This endpoint requires superuser privileges.
    """
    role_service = RoleService(db)
    try:
        return role_service.update_role(role_id, role_in.dict(exclude_unset=True))
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    *,
    db: Session = Depends(get_db),
    role_id: int = Path(..., ge=1, description="The ID of the role to delete"),
    current_user: Any = Depends(get_current_active_superuser),
) -> None:
    """
    Delete a role.

    This endpoint requires superuser privileges.
    """
    role_service = RoleService(db)
    try:
        role_service.delete_role(role_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/permissions", response_model=List[Permission])
def list_permissions(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    resource: Optional[str] = Query(None, description="Filter by resource"),
) -> List[Permission]:
    """
    Retrieve available permissions with optional filtering.
    """
    permission_service = PermissionService(db)
    return permission_service.list_permissions(resource=resource)


@router.post("/assign", status_code=status.HTTP_204_NO_CONTENT)
def assign_role_to_user(
    *,
    db: Session = Depends(get_db),
    assignment: RoleAssignmentCreate = Body(...),
    current_user: Any = Depends(get_current_active_superuser),
) -> None:
    """
    Assign a role to a user.

    This endpoint requires superuser privileges.
    """
    role_service = RoleService(db)
    try:
        role_service.assign_role_to_user(assignment.user_id, assignment.role_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {assignment.role_id} not found",
        )


@router.delete(
    "/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_role_from_user(
    *,
    db: Session = Depends(get_db),
    user_id: int = Path(..., ge=1, description="The ID of the user"),
    role_id: int = Path(..., ge=1, description="The ID of the role to remove"),
    current_user: Any = Depends(get_current_active_superuser),
) -> None:
    """
    Remove a role from a user.

    This endpoint requires superuser privileges.
    """
    role_service = RoleService(db)
    role_service.remove_role_from_user(user_id, role_id)


@router.get("/users/{user_id}/roles", response_model=List[Role])
def get_user_roles(
    *,
    db: Session = Depends(get_db),
    user_id: int = Path(..., ge=1, description="The ID of the user"),
    current_user: Any = Depends(get_current_active_user),
) -> List[Role]:
    """
    Get roles assigned to a user.
    """
    # Only allow superusers or the user themselves to see their roles
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    role_service = RoleService(db)
    return role_service.get_user_roles(user_id)
