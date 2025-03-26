# app/services/role_service.py
"""
Role service for HideSync.

This module provides functionality for managing roles and permissions
in the HideSync system.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.db.models.role import Role, Permission
from app.repositories.role_repository import RoleRepository, PermissionRepository
from app.core.exceptions import EntityNotFoundException, BusinessRuleException


class RoleService(BaseService[Role]):
    """
    Service for managing roles in the HideSync system.

    Provides functionality for:
    - Role management (CRUD operations)
    - Permission assignment
    - User-role assignments
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        permission_repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
    ):
        """
        Initialize RoleService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            permission_repository: Optional permission repository
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
        """
        self.session = session
        self.repository = repository or RoleRepository(session)
        self.permission_repository = permission_repository or PermissionRepository(
            session
        )
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service

    def create_role(
        self,
        name: str,
        description: Optional[str] = None,
        permission_codes: List[str] = None,
    ) -> Role:
        """
        Create a new role.

        Args:
            name: Role name
            description: Optional role description
            permission_codes: Optional list of permission codes to assign

        Returns:
            Created role entity

        Raises:
            BusinessRuleException: If a role with the same name already exists
        """
        with self.transaction():
            # Check if role with same name exists
            existing = self.repository.get_by_name(name)
            if existing:
                raise BusinessRuleException(f"Role with name '{name}' already exists")

            # Create role
            role_data = {
                "name": name,
                "description": description,
                "is_system_role": False,
            }
            role = self.repository.create(role_data)

            # Assign permissions if provided
            if permission_codes:
                self._assign_permissions_by_codes(role.id, permission_codes)

            return role

    def update_role(self, role_id: int, data: Dict[str, Any]) -> Role:
        """
        Update an existing role.

        Args:
            role_id: Role ID
            data: Updated role data

        Returns:
            Updated role entity

        Raises:
            EntityNotFoundException: If role not found
            BusinessRuleException: If update violates business rules
        """
        with self.transaction():
            # Check if role exists
            role = self.repository.get_by_id(role_id)
            if not role:
                raise EntityNotFoundException("Role", role_id)

            # Check if system role
            if role.is_system_role and ("name" in data or "is_system_role" in data):
                raise BusinessRuleException(
                    "Cannot modify name or system status of system roles"
                )

            # Check if name is being changed and already exists
            if "name" in data and data["name"] != role.name:
                existing = self.repository.get_by_name(data["name"])
                if existing:
                    raise BusinessRuleException(
                        f"Role with name '{data['name']}' already exists"
                    )

            # Extract permission codes if present
            permission_codes = data.pop("permission_codes", None)

            # Update role
            updated_role = self.repository.update(role_id, data)

            # Update permissions if provided
            if permission_codes is not None:
                self._assign_permissions_by_codes(role_id, permission_codes)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"Role:{role_id}")
                self.cache_service.invalidate("Roles:list")

            return updated_role

    def delete_role(self, role_id: int) -> bool:
        """
        Delete a role.

        Args:
            role_id: Role ID

        Returns:
            True if role was deleted

        Raises:
            EntityNotFoundException: If role not found
            BusinessRuleException: If role is a system role
        """
        with self.transaction():
            # Check if role exists
            role = self.repository.get_by_id(role_id)
            if not role:
                raise EntityNotFoundException("Role", role_id)

            # Check if system role
            if role.is_system_role:
                raise BusinessRuleException("Cannot delete system roles")

            # Delete role
            result = self.repository.delete(role_id)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"Role:{role_id}")
                self.cache_service.invalidate("Roles:list")

            return result

    def get_role_with_permissions(self, role_id: int) -> Dict[str, Any]:
        """
        Get a role with its permissions.

        Args:
            role_id: Role ID

        Returns:
            Role with permissions

        Raises:
            EntityNotFoundException: If role not found
        """
        # Check if role exists
        role = self.repository.get_by_id(role_id)
        if not role:
            raise EntityNotFoundException("Role", role_id)

        # Get permissions
        permissions = self.permission_repository.get_role_permissions(role_id)

        # Format response
        result = {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "is_system_role": role.is_system_role,
            "created_at": role.created_at,
            "updated_at": role.updated_at,
            "permissions": [
                {
                    "id": p.id,
                    "code": p.code,
                    "name": p.name,
                    "description": p.description,
                    "resource": p.resource,
                }
                for p in permissions
            ],
        }

        return result

    def assign_role_to_user(self, user_id: int, role_id: int) -> bool:
        """
        Assign a role to a user.

        Args:
            user_id: User ID
            role_id: Role ID

        Returns:
            True if assignment was successful

        Raises:
            EntityNotFoundException: If role not found
        """
        with self.transaction():
            # Check if role exists
            role = self.repository.get_by_id(role_id)
            if not role:
                raise EntityNotFoundException("Role", role_id)

            # Assign role
            result = self.repository.assign_role_to_user(user_id, role_id)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"User:{user_id}:roles")

            return result

    def remove_role_from_user(self, user_id: int, role_id: int) -> bool:
        """
        Remove a role from a user.

        Args:
            user_id: User ID
            role_id: Role ID

        Returns:
            True if removal was successful
        """
        with self.transaction():
            result = self.repository.remove_role_from_user(user_id, role_id)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"User:{user_id}:roles")

            return result

    def get_user_roles(self, user_id: int) -> List[Role]:
        """
        Get roles assigned to a user.

        Args:
            user_id: User ID

        Returns:
            List of roles assigned to the user
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"User:{user_id}:roles"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get roles from repository
        roles = self.repository.get_user_roles(user_id)

        # Cache result if needed
        if self.cache_service:
            self.cache_service.set(cache_key, roles, ttl=3600)  # 1 hour TTL

        return roles

    def get_user_permissions(self, user_id: int) -> List[str]:
        """
        Get permission codes for a user based on their roles.

        Args:
            user_id: User ID

        Returns:
            List of unique permission codes
        """
        # Get user roles
        roles = self.get_user_roles(user_id)

        # Collect all permissions
        all_permissions = set()
        for role in roles:
            permissions = self.permission_repository.get_role_permissions(role.id)
            for perm in permissions:
                all_permissions.add(perm.code)

        return list(all_permissions)

    def has_permission(self, user_id: int, permission_code: str) -> bool:
        """
        Check if a user has a specific permission.

        Args:
            user_id: User ID
            permission_code: Permission code to check

        Returns:
            True if the user has the permission
        """
        permissions = self.get_user_permissions(user_id)
        return permission_code in permissions

    def list_permissions(self, resource: Optional[str] = None) -> List[Permission]:
        """
        List available permissions.

        Args:
            resource: Optional resource to filter by

        Returns:
            List of permissions
        """
        if resource:
            return self.permission_repository.get_by_resource(resource)
        else:
            return self.permission_repository.list(limit=1000)

    def _assign_permissions_by_codes(
        self, role_id: int, permission_codes: List[str]
    ) -> bool:
        """
        Assign permissions to a role by their codes.

        Args:
            role_id: Role ID
            permission_codes: List of permission codes

        Returns:
            True if assignment was successful
        """
        # Get permissions by codes
        permissions = self.permission_repository.get_by_codes(permission_codes)

        # Get permission IDs
        permission_ids = [p.id for p in permissions]

        # Assign permissions
        return self.repository.assign_permissions(role_id, permission_ids)


class PermissionService(BaseService[Permission]):
    """
    Service for managing permissions in the HideSync system.

    Provides functionality for:
    - Permission management (CRUD operations)
    - Permission querying
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
    ):
        """
        Initialize PermissionService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
        """
        self.session = session
        self.repository = repository or PermissionRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service

    def create_permission(
        self, code: str, name: str, resource: str, description: Optional[str] = None
    ) -> Permission:
        """
        Create a new permission.

        Args:
            code: Permission code (unique identifier)
            name: Permission display name
            resource: Resource this permission applies to
            description: Optional permission description

        Returns:
            Created permission entity

        Raises:
            BusinessRuleException: If a permission with the same code already exists
        """
        with self.transaction():
            # Check if permission with same code exists
            existing = self.repository.get_by_code(code)
            if existing:
                raise BusinessRuleException(
                    f"Permission with code '{code}' already exists"
                )

            # Create permission
            permission_data = {
                "code": code,
                "name": name,
                "resource": resource,
                "description": description,
            }
            permission = self.repository.create(permission_data)

            return permission

    def update_permission(self, permission_id: int, data: Dict[str, Any]) -> Permission:
        """
        Update an existing permission.

        Args:
            permission_id: Permission ID
            data: Updated permission data

        Returns:
            Updated permission entity

        Raises:
            EntityNotFoundException: If permission not found
            BusinessRuleException: If update violates business rules
        """
        with self.transaction():
            # Check if permission exists
            permission = self.repository.get_by_id(permission_id)
            if not permission:
                raise EntityNotFoundException("Permission", permission_id)

            # Check if code is being changed and already exists
            if "code" in data and data["code"] != permission.code:
                existing = self.repository.get_by_code(data["code"])
                if existing:
                    raise BusinessRuleException(
                        f"Permission with code '{data['code']}' already exists"
                    )

            # Update permission
            updated_permission = self.repository.update(permission_id, data)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"Permission:{permission_id}")
                self.cache_service.invalidate("Permissions:list")

            return updated_permission

    def delete_permission(self, permission_id: int) -> bool:
        """
        Delete a permission.

        Args:
            permission_id: Permission ID

        Returns:
            True if permission was deleted

        Raises:
            EntityNotFoundException: If permission not found
        """
        with self.transaction():
            # Check if permission exists
            permission = self.repository.get_by_id(permission_id)
            if not permission:
                raise EntityNotFoundException("Permission", permission_id)

            # Delete permission
            result = self.repository.delete(permission_id)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"Permission:{permission_id}")
                self.cache_service.invalidate("Permissions:list")

            return result

    def get_by_code(self, code: str) -> Optional[Permission]:
        """
        Get a permission by its code.

        Args:
            code: Permission code

        Returns:
            Permission if found, None otherwise
        """
        return self.repository.get_by_code(code)

    def get_by_resource(self, resource: str) -> List[Permission]:
        """
        Get permissions for a resource.

        Args:
            resource: Resource name

        Returns:
            List of permissions for the resource
        """
        return self.repository.get_by_resource(resource)

    def get_available_resources(self) -> List[str]:
        """
        Get all available resource types.

        Returns:
            List of unique resource names
        """
        permissions = self.repository.list(limit=1000)
        resources = set(p.resource for p in permissions)
        return list(resources)
