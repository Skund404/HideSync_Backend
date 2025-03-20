# File: app/services/audit_service.py

from typing import Dict, Any, List, Optional, Type, Union
from sqlalchemy.orm import Session
from datetime import datetime
import json
import logging
import ipaddress

from app.db.models.base import Base

logger = logging.getLogger(__name__)


class AuditService:
    """
    Service for audit logging of entity changes and user actions.

    Provides comprehensive audit trail functionality for compliance
    and troubleshooting purposes.
    """

    def __init__(self, session: Session, audit_repository=None, security_context=None):
        """
        Initialize audit service with dependencies.

        Args:
            session: Database session for persistence operations
            audit_repository: Repository for audit records
            security_context: Optional security context for authorization
        """
        self.session = session
        self.repository = audit_repository
        self.security_context = security_context

    def record_entity_change(
        self,
        entity_type: str,
        entity_id: Any,
        action: str,
        changes: Dict[str, Any],
        entity_name: Optional[str] = None,
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record an entity change in the audit trail.

        Args:
            entity_type: Type of entity (e.g., "Material")
            entity_id: ID of the entity
            action: Action performed (create, update, delete)
            changes: Dictionary of changed fields with old and new values
            entity_name: Optional name/identifier of the entity for easier reference
            user_id: ID of the user performing action (if not from security context)
            metadata: Additional contextual information

        Returns:
            Created audit record
        """
        # Get user from security context if available
        if user_id is None and self.security_context:
            try:
                user_id = self.security_context.current_user.id
            except Exception:
                logger.warning("Failed to get user from security context for audit")

        # Prepare audit record
        audit_data = {
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "entity_name": entity_name,
            "action": action,
            "changes": json.dumps(changes) if isinstance(changes, dict) else changes,
            "user_id": user_id,
            "timestamp": datetime.now(),
            "ip_address": self._get_client_ip(),
            "metadata": json.dumps(metadata) if metadata else None,
        }

        # Log the audit record
        logger.info(
            f"AUDIT: {action} {entity_type} {entity_id} by user {user_id}",
            extra={
                "audit": True,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "user_id": user_id,
            },
        )

        # Store in repository if available
        if self.repository:
            return self.repository.create(audit_data)

        return audit_data

    def record_create(
        self,
        entity: Base,
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        exclude_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Record entity creation.

        Args:
            entity: Created entity
            user_id: User ID (if not from security context)
            metadata: Additional contextual information
            exclude_fields: Fields to exclude from audit

        Returns:
            Created audit record
        """
        entity_type = entity.__class__.__name__
        entity_id = entity.id
        entity_name = getattr(entity, "name", None)

        # Get entity data, excluding specified fields
        exclude_fields = exclude_fields or []
        exclude_fields.extend(["id", "created_at", "updated_at"])

        # Get entity data as dict
        if hasattr(entity, "to_dict"):
            entity_data = entity.to_dict()
        else:
            entity_data = {
                k: v for k, v in entity.__dict__.items() if not k.startswith("_")
            }

        # All values are new, exclude specified fields
        changes = {
            k: {"old": None, "new": v}
            for k, v in entity_data.items()
            if k not in exclude_fields
        }

        return self.record_entity_change(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            action="create",
            changes=changes,
            user_id=user_id,
            metadata=metadata,
        )

    def record_update(
        self,
        entity: Base,
        original_data: Dict[str, Any],
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        exclude_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Record entity update with changed fields.

        Args:
            entity: Updated entity
            original_data: Original entity data before changes
            user_id: User ID (if not from security context)
            metadata: Additional contextual information
            exclude_fields: Fields to exclude from audit

        Returns:
            Created audit record if changes detected, None otherwise
        """
        entity_type = entity.__class__.__name__
        entity_id = entity.id
        entity_name = getattr(entity, "name", None)

        # Get exclude fields
        exclude_fields = exclude_fields or []
        exclude_fields.extend(["id", "updated_at"])

        # Get current values
        if hasattr(entity, "to_dict"):
            current_data = entity.to_dict()
        else:
            current_data = {
                k: v for k, v in entity.__dict__.items() if not k.startswith("_")
            }

        # Find changed fields, excluding specified fields
        changes = {}
        for key, new_value in current_data.items():
            if key in exclude_fields:
                continue

            if key in original_data and original_data[key] != new_value:
                # Handle sensitive fields
                if self._is_sensitive_field(key):
                    changes[key] = {"changed": True}
                else:
                    changes[key] = {"old": original_data[key], "new": new_value}

        if not changes:
            logger.debug(
                f"No changes detected for {entity_type} {entity_id}, skipping audit"
            )
            return None

        return self.record_entity_change(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            action="update",
            changes=changes,
            user_id=user_id,
            metadata=metadata,
        )

    def record_delete(
        self,
        entity: Base,
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        exclude_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Record entity deletion.

        Args:
            entity: Deleted entity
            user_id: User ID (if not from security context)
            metadata: Additional contextual information
            exclude_fields: Fields to exclude from audit

        Returns:
            Created audit record
        """
        entity_type = entity.__class__.__name__
        entity_id = entity.id
        entity_name = getattr(entity, "name", None)

        # Get exclude fields
        exclude_fields = exclude_fields or []
        exclude_fields.extend(["id", "created_at", "updated_at"])

        # Get entity data as dict
        if hasattr(entity, "to_dict"):
            entity_data = entity.to_dict()
        else:
            entity_data = {
                k: v for k, v in entity.__dict__.items() if not k.startswith("_")
            }

        # All values are being deleted, exclude specified fields
        changes = {}
        for k, v in entity_data.items():
            if k in exclude_fields:
                continue

            # Handle sensitive fields
            if self._is_sensitive_field(k):
                changes[k] = {"deleted": True}
            else:
                changes[k] = {"old": v, "new": None}

        return self.record_entity_change(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            action="delete",
            changes=changes,
            user_id=user_id,
            metadata=metadata,
        )

    def record_login(
        self,
        user_id: int,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record user login attempt.

        Args:
            user_id: ID of the user
            success: Whether login was successful
            ip_address: Optional IP address of the client
            user_agent: Optional user agent string
            metadata: Additional contextual information

        Returns:
            Created audit record
        """
        action = "login_success" if success else "login_failure"

        # Add IP and user agent to metadata
        metadata = metadata or {}
        if ip_address:
            metadata["ip_address"] = ip_address
        if user_agent:
            metadata["user_agent"] = user_agent

        # Record the login event
        audit_data = {
            "entity_type": "User",
            "entity_id": str(user_id),
            "action": action,
            "changes": None,
            "user_id": user_id,
            "timestamp": datetime.now(),
            "ip_address": ip_address or self._get_client_ip(),
            "metadata": json.dumps(metadata),
        }

        # Log the audit event
        logger.info(
            f"AUDIT: {action} for user {user_id}",
            extra={
                "audit": True,
                "entity_type": "User",
                "entity_id": user_id,
                "action": action,
                "user_id": user_id,
            },
        )

        # Store in repository if available
        if self.repository:
            return self.repository.create(audit_data)

        return audit_data

    def record_api_access(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        user_id: Optional[int] = None,
        duration_ms: Optional[float] = None,
        request_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record API endpoint access.

        Args:
            endpoint: API endpoint accessed
            method: HTTP method used
            status_code: HTTP status code returned
            user_id: Optional user ID (if authenticated)
            duration_ms: Optional request duration in milliseconds
            request_data: Optional request data (sanitized)

        Returns:
            Created audit record
        """
        # Get user from security context if available
        if user_id is None and self.security_context:
            try:
                user_id = self.security_context.current_user.id
            except Exception:
                pass

        # Prepare metadata
        metadata = {"endpoint": endpoint, "method": method, "status_code": status_code}

        if duration_ms is not None:
            metadata["duration_ms"] = duration_ms

        if request_data:
            # Sanitize request data to remove sensitive information
            sanitized_data = self._sanitize_request_data(request_data)
            metadata["request_data"] = sanitized_data

        # Record the API access
        audit_data = {
            "entity_type": "API",
            "entity_id": endpoint,
            "action": f"{method.upper()} {status_code}",
            "changes": None,
            "user_id": user_id,
            "timestamp": datetime.now(),
            "ip_address": self._get_client_ip(),
            "metadata": json.dumps(metadata),
        }

        # Log the audit event
        logger.info(
            f"AUDIT: API {method.upper()} {endpoint} {status_code} by user {user_id}",
            extra={
                "audit": True,
                "entity_type": "API",
                "entity_id": endpoint,
                "action": f"{method.upper()} {status_code}",
                "user_id": user_id,
            },
        )

        # Store in repository if available
        if self.repository:
            return self.repository.create(audit_data)

        return audit_data

    def get_entity_history(
        self,
        entity_type: str,
        entity_id: Any,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        actions: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get the audit history for an entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            actions: Optional list of actions to filter by
            limit: Maximum number of records to return

        Returns:
            List of audit records in chronological order
        """
        if not self.repository:
            logger.warning("Audit repository not available for history retrieval")
            return []

        filters = {"entity_type": entity_type, "entity_id": str(entity_id)}

        if start_date:
            filters["timestamp_gte"] = start_date

        if end_date:
            filters["timestamp_lte"] = end_date

        if actions:
            filters["action_in"] = actions

        return self.repository.list(
            limit=limit, sort_by="timestamp", sort_dir="asc", **filters
        )

    def get_user_activity(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        entity_types: Optional[List[str]] = None,
        actions: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get audit history for a specific user.

        Args:
            user_id: ID of the user
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            entity_types: Optional list of entity types to filter by
            actions: Optional list of actions to filter by
            limit: Maximum number of records to return

        Returns:
            List of audit records in chronological order
        """
        if not self.repository:
            logger.warning("Audit repository not available for user activity retrieval")
            return []

        filters = {"user_id": user_id}

        if start_date:
            filters["timestamp_gte"] = start_date

        if end_date:
            filters["timestamp_lte"] = end_date

        if entity_types:
            filters["entity_type_in"] = entity_types

        if actions:
            filters["action_in"] = actions

        return self.repository.list(
            limit=limit, sort_by="timestamp", sort_dir="desc", **filters
        )

    def get_login_history(
        self,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        success_only: bool = False,
        failures_only: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get login history for a user or all users.

        Args:
            user_id: Optional ID of the user (all users if None)
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            success_only: Only include successful logins
            failures_only: Only include failed logins
            limit: Maximum number of records to return

        Returns:
            List of login audit records
        """
        if not self.repository:
            logger.warning("Audit repository not available for login history retrieval")
            return []

        filters = {"entity_type": "User"}

        actions = []
        if success_only:
            actions.append("login_success")
        elif failures_only:
            actions.append("login_failure")
        else:
            actions.extend(["login_success", "login_failure"])

        filters["action_in"] = actions

        if user_id:
            filters["user_id"] = user_id

        if start_date:
            filters["timestamp_gte"] = start_date

        if end_date:
            filters["timestamp_lte"] = end_date

        return self.repository.list(
            limit=limit, sort_by="timestamp", sort_dir="desc", **filters
        )

    def get_api_access_history(
        self,
        endpoint: Optional[str] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        methods: Optional[List[str]] = None,
        status_codes: Optional[List[int]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get API access history.

        Args:
            endpoint: Optional specific endpoint filter
            user_id: Optional user ID filter
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            methods: Optional list of HTTP methods to filter by
            status_codes: Optional list of status codes to filter by
            limit: Maximum number of records to return

        Returns:
            List of API access audit records
        """
        if not self.repository:
            logger.warning(
                "Audit repository not available for API access history retrieval"
            )
            return []

        filters = {"entity_type": "API"}

        if endpoint:
            filters["entity_id"] = endpoint

        if user_id:
            filters["user_id"] = user_id

        if start_date:
            filters["timestamp_gte"] = start_date

        if end_date:
            filters["timestamp_lte"] = end_date

        if methods:
            action_filters = []
            for method in methods:
                if status_codes:
                    for code in status_codes:
                        action_filters.append(f"{method.upper()} {code}")
                else:
                    action_filters.append(f"{method.upper()} %")

            filters["action_in"] = action_filters

        elif status_codes:
            action_filters = []
            for code in status_codes:
                action_filters.append(f"% {code}")

            filters["action_in"] = action_filters

        return self.repository.list(
            limit=limit, sort_by="timestamp", sort_dir="desc", **filters
        )

    def _get_client_ip(self) -> Optional[str]:
        """
        Get client IP address from context if available.

        Returns:
            Client IP address or None
        """
        if self.security_context:
            return getattr(self.security_context, "client_ip", None)
        return None

    def _is_sensitive_field(self, field_name: str) -> bool:
        """
        Check if a field is considered sensitive.

        Args:
            field_name: Name of the field

        Returns:
            True if field is sensitive, False otherwise
        """
        sensitive_fields = [
            "password",
            "token",
            "secret",
            "key",
            "salt",
            "hash",
            "card",
            "account",
            "ssn",
            "social",
            "credit",
            "debit",
            "cvv",
            "security_code",
            "security_question",
            "security_answer",
        ]

        return any(sensitive in field_name.lower() for sensitive in sensitive_fields)

    def _sanitize_request_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize request data to remove sensitive information.

        Args:
            data: Request data

        Returns:
            Sanitized request data
        """
        sanitized = {}

        for key, value in data.items():
            if self._is_sensitive_field(key):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_request_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    (
                        self._sanitize_request_data(item)
                        if isinstance(item, dict)
                        else item
                    )
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized
