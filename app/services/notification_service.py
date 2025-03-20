# File: services/notification_service.py

"""
Notification management service for the HideSync system.

This module provides functionality for creating, delivering, and managing notifications
throughout the system. It allows for different notification types, priorities, and delivery
channels, enabling effective communication with users about important events, alerts,
and system updates.

Notifications are a critical component for keeping users informed about project statuses,
inventory alerts, upcoming deadlines, and system events. This service ensures that
relevant stakeholders receive timely information through their preferred communication
channels.

Key features:
- Notification creation and management
- Multiple notification types (system, project, inventory, etc.)
- Priority levels for importance indication
- Delivery channel selection (in-app, email, SMS, etc.)
- User preference management
- Notification grouping and batching
- Read/unread status tracking
- Notification retention and archiving

The service follows clean architecture principles with clear separation from
the data access layer through repository interfaces, and integrates with other
services like communications service and user preference service.
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
import logging
import uuid
import json
from sqlalchemy.orm import Session

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
)
from app.core.validation import validate_input, validate_entity
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class NotificationCreated(DomainEvent):
    """Event emitted when a notification is created."""

    def __init__(
        self,
        notification_id: str,
        notification_type: str,
        user_id: Optional[str] = None,
        priority: str = "NORMAL",
    ):
        """
        Initialize notification created event.

        Args:
            notification_id: ID of the created notification
            notification_type: Type of notification
            user_id: Optional ID of the target user
            priority: Priority level of the notification
        """
        super().__init__()
        self.notification_id = notification_id
        self.notification_type = notification_type
        self.user_id = user_id
        self.priority = priority


class NotificationSent(DomainEvent):
    """Event emitted when a notification is sent through a delivery channel."""

    def __init__(
        self,
        notification_id: str,
        user_id: Optional[str],
        channel: str,
        successful: bool,
        error: Optional[str] = None,
    ):
        """
        Initialize notification sent event.

        Args:
            notification_id: ID of the sent notification
            user_id: Optional ID of the target user
            channel: Delivery channel used
            successful: Whether the delivery was successful
            error: Optional error message if delivery failed
        """
        super().__init__()
        self.notification_id = notification_id
        self.user_id = user_id
        self.channel = channel
        self.successful = successful
        self.error = error


class NotificationRead(DomainEvent):
    """Event emitted when a notification is marked as read."""

    def __init__(self, notification_id: str, user_id: Optional[str], read_at: datetime):
        """
        Initialize notification read event.

        Args:
            notification_id: ID of the read notification
            user_id: Optional ID of the user who read it
            read_at: Timestamp when notification was read
        """
        super().__init__()
        self.notification_id = notification_id
        self.user_id = user_id
        self.read_at = read_at


class NotificationArchived(DomainEvent):
    """Event emitted when a notification is archived."""

    def __init__(self, notification_id: str, user_id: Optional[str] = None):
        """
        Initialize notification archived event.

        Args:
            notification_id: ID of the archived notification
            user_id: Optional ID of the user who archived it
        """
        super().__init__()
        self.notification_id = notification_id
        self.user_id = user_id


class NotificationService(BaseService):
    """
    Service for managing notifications in the HideSync system.

    Provides functionality for:
    - Creating notifications for users
    - Sending notifications through various channels
    - Managing notification preferences
    - Tracking notification status (read/unread)
    - Grouping and batching notifications
    - Archiving and cleaning up old notifications
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        user_service=None,
        email_service=None,
        sms_service=None,
    ):
        """
        Initialize NotificationService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for notifications
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            user_service: Optional service for user operations
            email_service: Optional service for email delivery
            sms_service: Optional service for SMS delivery
        """
        self.session = session
        self.repository = repository
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.user_service = user_service
        self.email_service = email_service
        self.sms_service = sms_service

    def create_notification(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new notification.

        Args:
            data: Notification data with required fields
                Required fields:
                - type: Notification type (e.g. "PROJECT_DUE", "INVENTORY_LOW")
                - title: Title/subject of the notification
                - message: Body text of the notification
                Optional fields:
                - user_id: ID of the recipient user (None for system-wide)
                - priority: Priority level (defaults to "NORMAL")
                - link: Optional URL or application route for further action
                - metadata: Additional structured data related to notification
                - expiry: Optional expiration date
                - delivery_channels: List of delivery channels to use

        Returns:
            Created notification with delivery status

        Raises:
            ValidationException: If validation fails
        """
        with self.transaction():
            # Validate required fields
            if "type" not in data:
                raise ValidationException(
                    "Notification type is required",
                    {"type": ["This field is required"]},
                )

            if "title" not in data:
                raise ValidationException(
                    "Notification title is required",
                    {"title": ["This field is required"]},
                )

            if "message" not in data:
                raise ValidationException(
                    "Notification message is required",
                    {"message": ["This field is required"]},
                )

            # Generate ID if not provided
            if "id" not in data:
                data["id"] = str(uuid.uuid4())

            # Set default values
            if "priority" not in data:
                data["priority"] = "NORMAL"

            if "created_at" not in data:
                data["created_at"] = datetime.now()

            # Set default delivery channels if not provided
            if "delivery_channels" not in data:
                # Default to in-app notification
                data["delivery_channels"] = ["in_app"]

            # Convert metadata to JSON string if it's a dict
            if "metadata" in data and isinstance(data["metadata"], dict):
                data["metadata"] = json.dumps(data["metadata"])

            # Create notification in repository if available
            notification = None
            if self.repository:
                notification = self.repository.create(data)
                notification_id = notification.id
            else:
                # Without repository, just use the data dictionary
                notification = data
                notification_id = data["id"]

            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish(
                    NotificationCreated(
                        notification_id=notification_id,
                        notification_type=data["type"],
                        user_id=data.get("user_id"),
                        priority=data.get("priority", "NORMAL"),
                    )
                )

            # Attempt delivery through specified channels
            delivery_results = {}

            for channel in data.get("delivery_channels", []):
                delivery_result = self._deliver_notification(notification, channel)
                delivery_results[channel] = delivery_result

                # Publish delivery event if event bus exists
                if self.event_bus:
                    self.event_bus.publish(
                        NotificationSent(
                            notification_id=notification_id,
                            user_id=data.get("user_id"),
                            channel=channel,
                            successful=delivery_result.get("success", False),
                            error=delivery_result.get("error"),
                        )
                    )

            # Return notification with delivery results
            result = (
                notification.to_dict()
                if hasattr(notification, "to_dict")
                else dict(notification)
            )
            result["delivery_results"] = delivery_results

            # Invalidate cache if cache service exists
            if self.cache_service and data.get("user_id"):
                self.cache_service.invalidate(f"Notifications:user:{data['user_id']}")

            return result

    def create_bulk_notifications(
        self, template: Dict[str, Any], user_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Create notifications for multiple users based on a template.

        Args:
            template: Notification template
            user_ids: List of user IDs to send to

        Returns:
            Dictionary with creation results

        Raises:
            ValidationException: If validation fails
        """
        # Validate template
        if "type" not in template:
            raise ValidationException(
                "Notification type is required", {"type": ["This field is required"]}
            )

        if "title" not in template:
            raise ValidationException(
                "Notification title is required", {"title": ["This field is required"]}
            )

        if "message" not in template:
            raise ValidationException(
                "Notification message is required",
                {"message": ["This field is required"]},
            )

        results = {"total": len(user_ids), "succeeded": 0, "failed": 0, "details": []}

        # Create notification for each user
        for user_id in user_ids:
            try:
                # Create notification data from template
                notification_data = dict(template)
                notification_data["user_id"] = user_id

                # Create notification
                notification = self.create_notification(notification_data)

                results["succeeded"] += 1
                results["details"].append(
                    {
                        "user_id": user_id,
                        "notification_id": (
                            notification.get("id")
                            if isinstance(notification, dict)
                            else notification.id
                        ),
                        "success": True,
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to create notification for user {user_id}: {str(e)}",
                    exc_info=True,
                )

                results["failed"] += 1
                results["details"].append(
                    {"user_id": user_id, "success": False, "error": str(e)}
                )

        return results

    def get_user_notifications(
        self, user_id: str, include_read: bool = False, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get notifications for a specific user.

        Args:
            user_id: ID of the user
            include_read: Whether to include read notifications
            limit: Maximum number of notifications to return
            offset: Offset for pagination

        Returns:
            List of notifications for the user
        """
        # Check cache first if cache service exists
        cache_key = f"Notifications:user:{user_id}:read:{include_read}:limit:{limit}:offset:{offset}"

        if self.cache_service:
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get notifications from repository if available
        if self.repository:
            filters = {"user_id": user_id}

            if not include_read:
                filters["read"] = False

            notifications = self.repository.list(
                limit=limit,
                offset=offset,
                sort_by="created_at",
                sort_dir="desc",
                **filters,
            )

            # Convert to list of dictionaries
            result = [n.to_dict() for n in notifications]
        else:
            # If no repository, return empty list
            result = []

        # Cache result if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=60)  # Short TTL

        return result

    def mark_as_read(self, notification_id: str) -> Dict[str, Any]:
        """
        Mark a notification as read.

        Args:
            notification_id: ID of the notification

        Returns:
            Updated notification

        Raises:
            EntityNotFoundException: If notification not found
        """
        with self.transaction():
            # Get notification from repository if available
            if self.repository:
                notification = self.repository.get_by_id(notification_id)

                if not notification:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("Notification", notification_id)

                # Skip if already read
                if hasattr(notification, "read") and notification.read:
                    return notification.to_dict()

                # Update notification
                updated = self.repository.update(
                    notification_id, {"read": True, "read_at": datetime.now()}
                )

                # Publish event if event bus exists
                if self.event_bus:
                    user_id = (
                        notification.user_id
                        if hasattr(notification, "user_id")
                        else None
                    )
                    self.event_bus.publish(
                        NotificationRead(
                            notification_id=notification_id,
                            user_id=user_id,
                            read_at=datetime.now(),
                        )
                    )

                # Invalidate cache if cache service exists
                if (
                    self.cache_service
                    and hasattr(notification, "user_id")
                    and notification.user_id
                ):
                    self.cache_service.invalidate(
                        f"Notifications:user:{notification.user_id}"
                    )

                return updated.to_dict()
            else:
                # Without repository, return empty dict
                return {"id": notification_id, "read": True, "read_at": datetime.now()}

    def mark_all_as_read(self, user_id: str) -> Dict[str, Any]:
        """
        Mark all notifications for a user as read.

        Args:
            user_id: ID of the user

        Returns:
            Dictionary with operation results
        """
        with self.transaction():
            # Get unread notifications for user if repository available
            if self.repository:
                unread_notifications = self.repository.list(user_id=user_id, read=False)

                # Update each notification
                updated_count = 0
                for notification in unread_notifications:
                    self.repository.update(
                        notification.id, {"read": True, "read_at": datetime.now()}
                    )

                    # Publish event if event bus exists
                    if self.event_bus:
                        self.event_bus.publish(
                            NotificationRead(
                                notification_id=notification.id,
                                user_id=user_id,
                                read_at=datetime.now(),
                            )
                        )

                    updated_count += 1

                # Invalidate cache if cache service exists
                if self.cache_service:
                    self.cache_service.invalidate(f"Notifications:user:{user_id}")

                return {
                    "success": True,
                    "user_id": user_id,
                    "updated_count": updated_count,
                }
            else:
                # Without repository, return empty result
                return {"success": True, "user_id": user_id, "updated_count": 0}

    def archive_notification(self, notification_id: str) -> Dict[str, Any]:
        """
        Archive a notification.

        Args:
            notification_id: ID of the notification

        Returns:
            Updated notification

        Raises:
            EntityNotFoundException: If notification not found
        """
        with self.transaction():
            # Get notification from repository if available
            if self.repository:
                notification = self.repository.get_by_id(notification_id)

                if not notification:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("Notification", notification_id)

                # Skip if already archived
                if hasattr(notification, "archived") and notification.archived:
                    return notification.to_dict()

                # Update notification
                updated = self.repository.update(
                    notification_id, {"archived": True, "archived_at": datetime.now()}
                )

                # Publish event if event bus exists
                if self.event_bus:
                    user_id = (
                        notification.user_id
                        if hasattr(notification, "user_id")
                        else None
                    )
                    self.event_bus.publish(
                        NotificationArchived(
                            notification_id=notification_id, user_id=user_id
                        )
                    )

                # Invalidate cache if cache service exists
                if (
                    self.cache_service
                    and hasattr(notification, "user_id")
                    and notification.user_id
                ):
                    self.cache_service.invalidate(
                        f"Notifications:user:{notification.user_id}"
                    )

                return updated.to_dict()
            else:
                # Without repository, return empty dict
                return {
                    "id": notification_id,
                    "archived": True,
                    "archived_at": datetime.now(),
                }

    def delete_notification(self, notification_id: str) -> bool:
        """
        Delete a notification.

        Args:
            notification_id: ID of the notification

        Returns:
            True if deletion was successful

        Raises:
            EntityNotFoundException: If notification not found
        """
        with self.transaction():
            # Get notification from repository if available
            if self.repository:
                notification = self.repository.get_by_id(notification_id)

                if not notification:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("Notification", notification_id)

                # Store user_id for cache invalidation
                user_id = (
                    notification.user_id if hasattr(notification, "user_id") else None
                )

                # Delete notification
                result = self.repository.delete(notification_id)

                # Invalidate cache if cache service exists
                if self.cache_service and user_id:
                    self.cache_service.invalidate(f"Notifications:user:{user_id}")

                return result
            else:
                # Without repository, return True
                return True

    def get_notification_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get notification statistics for a user.

        Args:
            user_id: ID of the user

        Returns:
            Dictionary with notification statistics
        """
        # Get stats from repository if available
        if self.repository:
            # Get total counts
            total_count = self.repository.count(user_id=user_id)
            unread_count = self.repository.count(user_id=user_id, read=False)
            archived_count = self.repository.count(user_id=user_id, archived=True)

            # Get counts by priority
            high_priority_count = self.repository.count(
                user_id=user_id, priority="HIGH", read=False
            )
            normal_priority_count = self.repository.count(
                user_id=user_id, priority="NORMAL", read=False
            )
            low_priority_count = self.repository.count(
                user_id=user_id, priority="LOW", read=False
            )

            # Get counts by type
            type_counts = self.repository.group_count("type", user_id=user_id)

            return {
                "user_id": user_id,
                "total_count": total_count,
                "unread_count": unread_count,
                "archived_count": archived_count,
                "by_priority": {
                    "high": high_priority_count,
                    "normal": normal_priority_count,
                    "low": low_priority_count,
                },
                "by_type": type_counts,
            }
        else:
            # Without repository, return empty stats
            return {
                "user_id": user_id,
                "total_count": 0,
                "unread_count": 0,
                "archived_count": 0,
                "by_priority": {"high": 0, "normal": 0, "low": 0},
                "by_type": {},
            }

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get notification preferences for a user.

        Args:
            user_id: ID of the user

        Returns:
            Dictionary with notification preferences
        """
        # Return user preferences if user service is available
        if self.user_service:
            try:
                return self.user_service.get_notification_preferences(user_id)
            except Exception as e:
                logger.warning(f"Failed to get notification preferences: {str(e)}")

        # Default preferences if user service not available
        return {
            "user_id": user_id,
            "delivery_channels": {"in_app": True, "email": True, "sms": False},
            "notification_types": {
                "project_updates": True,
                "inventory_alerts": True,
                "system_announcements": True,
                "order_updates": True,
                "task_reminders": True,
            },
            "quiet_hours": {
                "enabled": False,
                "start_time": "22:00",
                "end_time": "08:00",
            },
        }

    def update_user_preferences(
        self, user_id: str, preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update notification preferences for a user.

        Args:
            user_id: ID of the user
            preferences: Updated notification preferences

        Returns:
            Updated notification preferences
        """
        # Update user preferences if user service is available
        if self.user_service:
            try:
                return self.user_service.update_notification_preferences(
                    user_id, preferences
                )
            except Exception as e:
                logger.warning(f"Failed to update notification preferences: {str(e)}")

        # Return provided preferences if user service not available
        return preferences

    def clean_old_notifications(self, days_threshold: int = 30) -> Dict[str, Any]:
        """
        Clean up old notifications.

        Args:
            days_threshold: Age in days for notifications to be eligible for deletion

        Returns:
            Dictionary with cleanup results
        """
        with self.transaction():
            # Clean old notifications if repository available
            if self.repository:
                cutoff_date = datetime.now() - timedelta(days=days_threshold)

                # Delete read and archived notifications older than threshold
                deleted_count = self.repository.delete_where(
                    created_at_lt=cutoff_date, read=True, archived=True
                )

                # Archive read notifications older than threshold
                archived_count = self.repository.update_where(
                    {"archived": True, "archived_at": datetime.now()},
                    created_at_lt=cutoff_date,
                    read=True,
                    archived=False,
                )

                return {
                    "success": True,
                    "deleted_count": deleted_count,
                    "archived_count": archived_count,
                    "threshold_days": days_threshold,
                    "cutoff_date": cutoff_date.isoformat(),
                }
            else:
                # Without repository, return empty result
                return {
                    "success": True,
                    "deleted_count": 0,
                    "archived_count": 0,
                    "threshold_days": days_threshold,
                    "cutoff_date": (
                        datetime.now() - timedelta(days=days_threshold)
                    ).isoformat(),
                }

    def _deliver_notification(self, notification: Any, channel: str) -> Dict[str, Any]:
        """
        Deliver a notification through a specific channel.

        Args:
            notification: Notification to deliver
            channel: Delivery channel to use

        Returns:
            Dictionary with delivery result
        """
        try:
            # Get notification data
            notification_dict = (
                notification.to_dict()
                if hasattr(notification, "to_dict")
                else notification
            )

            # Get user preferences if user service is available
            user_preferences = None
            user_id = notification_dict.get("user_id")

            if user_id and self.user_service:
                try:
                    user_preferences = self.get_user_preferences(user_id)
                except Exception as e:
                    logger.warning(f"Failed to get user preferences: {str(e)}")

            # Check if user has opted out of this channel
            if user_preferences and "delivery_channels" in user_preferences:
                if (
                    channel in user_preferences["delivery_channels"]
                    and not user_preferences["delivery_channels"][channel]
                ):
                    return {
                        "success": False,
                        "channel": channel,
                        "error": f"User has opted out of {channel} notifications",
                    }

            # Check if user has opted out of this notification type
            notification_type = notification_dict.get("type", "").lower()
            if user_preferences and "notification_types" in user_preferences:
                for pref_type, enabled in user_preferences[
                    "notification_types"
                ].items():
                    if notification_type.startswith(pref_type.lower()) and not enabled:
                        return {
                            "success": False,
                            "channel": channel,
                            "error": f"User has opted out of {notification_type} notifications",
                        }

            # Check quiet hours if applicable
            if (
                user_preferences
                and "quiet_hours" in user_preferences
                and user_preferences["quiet_hours"]["enabled"]
            ):
                # Skip quiet hours check for high priority notifications
                if notification_dict.get("priority") != "HIGH":
                    # Check if current time is within quiet hours
                    quiet_start = user_preferences["quiet_hours"]["start_time"]
                    quiet_end = user_preferences["quiet_hours"]["end_time"]

                    current_time = datetime.now().strftime("%H:%M")

                    # Basic string comparison works for 24-hour time format
                    if quiet_start <= current_time <= quiet_end:
                        return {
                            "success": False,
                            "channel": channel,
                            "error": "Notification delivery deferred due to quiet hours",
                        }

            # Deliver based on channel
            if channel == "in_app":
                # In-app notifications are stored in the repository, no extra delivery needed
                return {"success": True, "channel": channel}
            elif channel == "email" and self.email_service:
                # Deliver via email
                return self._deliver_email(notification_dict)
            elif channel == "sms" and self.sms_service:
                # Deliver via SMS
                return self._deliver_sms(notification_dict)
            else:
                # Unsupported channel or missing service
                return {
                    "success": False,
                    "channel": channel,
                    "error": f"Unsupported channel or missing service for {channel}",
                }
        except Exception as e:
            logger.error(
                f"Failed to deliver notification through {channel}: {str(e)}",
                exc_info=True,
            )
            return {"success": False, "channel": channel, "error": str(e)}

    def _deliver_email(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deliver a notification via email.

        Args:
            notification: Notification to deliver

        Returns:
            Dictionary with delivery result
        """
        if not self.email_service:
            return {
                "success": False,
                "channel": "email",
                "error": "Email service not available",
            }

        user_id = notification.get("user_id")
        if not user_id:
            return {
                "success": False,
                "channel": "email",
                "error": "No user specified for email delivery",
            }

        # Get user email if user service is available
        user_email = None
        if self.user_service:
            try:
                user = self.user_service.get_by_id(user_id)
                if user and hasattr(user, "email"):
                    user_email = user.email
            except Exception as e:
                logger.warning(f"Failed to get user email: {str(e)}")

        if not user_email:
            return {
                "success": False,
                "channel": "email",
                "error": "User email not available",
            }

        # Prepare email data
        email_data = {
            "to": user_email,
            "subject": notification.get("title", "HideSync Notification"),
            "body": notification.get("message", ""),
            "html_body": notification.get("html_body"),
        }

        # Add link if available
        if notification.get("link"):
            if email_data.get("html_body"):
                email_data[
                    "html_body"
                ] += f'<p><a href="{notification["link"]}">View Details</a></p>'
            else:
                email_data["body"] += f'\n\nView Details: {notification["link"]}'

        # Send email
        try:
            self.email_service.send_email(email_data)
            return {"success": True, "channel": "email", "recipient": user_email}
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}", exc_info=True)
            return {"success": False, "channel": "email", "error": str(e)}

    def _deliver_sms(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deliver a notification via SMS.

        Args:
            notification: Notification to deliver

        Returns:
            Dictionary with delivery result
        """
        if not self.sms_service:
            return {
                "success": False,
                "channel": "sms",
                "error": "SMS service not available",
            }

        user_id = notification.get("user_id")
        if not user_id:
            return {
                "success": False,
                "channel": "sms",
                "error": "No user specified for SMS delivery",
            }

        # Get user phone if user service is available
        user_phone = None
        if self.user_service:
            try:
                user = self.user_service.get_by_id(user_id)
                if user and hasattr(user, "phone"):
                    user_phone = user.phone
            except Exception as e:
                logger.warning(f"Failed to get user phone: {str(e)}")

        if not user_phone:
            return {
                "success": False,
                "channel": "sms",
                "error": "User phone not available",
            }

        # Prepare SMS message (keep it concise)
        title = notification.get("title", "HideSync")
        message = notification.get("message", "")

        # Truncate if too long for SMS
        if len(message) > 140:
            message = message[:137] + "..."

        sms_text = f"{title}: {message}"

        # Add link if space allows
        if (
            notification.get("link")
            and len(sms_text) + len(notification["link"]) + 4 <= 160
        ):
            sms_text += f" {notification['link']}"

        # Send SMS
        try:
            self.sms_service.send_sms(user_phone, sms_text)
            return {"success": True, "channel": "sms", "recipient": user_phone}
        except Exception as e:
            logger.error(f"Failed to send SMS: {str(e)}", exc_info=True)
            return {"success": False, "channel": "sms", "error": str(e)}
