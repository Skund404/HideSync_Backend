# File: app/repositories/tool_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime, timedelta

from app.db.models.tool import Tool, ToolMaintenance, ToolCheckout
from app.db.models.enums import ToolCategory
from app.repositories.base_repository import BaseRepository


class ToolRepository(BaseRepository[Tool]):
    """
    Repository for Tool entity operations.

    Handles data access for leatherworking tools, including
    tool inventory, specifications, and status management.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ToolRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Tool

    def get_tools_by_category(
        self, category: ToolCategory, skip: int = 0, limit: int = 100
    ) -> List[Tool]:
        """
        Get tools by category.

        Args:
            category (ToolCategory): The tool category to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Tool]: List of tools in the specified category
        """
        query = self.session.query(self.model).filter(self.model.category == category)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_tools_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[Tool]:
        """
        Get tools by status.

        Args:
            status (str): The tool status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Tool]: List of tools with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_tools_by_location(
        self, location: str, skip: int = 0, limit: int = 100
    ) -> List[Tool]:
        """
        Get tools by storage location.

        Args:
            location (str): The storage location to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Tool]: List of tools in the specified location
        """
        query = self.session.query(self.model).filter(self.model.location == location)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_tools_due_for_maintenance(
        self, skip: int = 0, limit: int = 100
    ) -> List[Tool]:
        """
        Get tools that are due for maintenance.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Tool]: List of tools due for maintenance
        """
        now = datetime.now()

        query = self.session.query(self.model).filter(
            self.model.nextMaintenance <= now.isoformat()
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_checked_out_tools(self, skip: int = 0, limit: int = 100) -> List[Tool]:
        """
        Get tools that are currently checked out.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Tool]: List of checked out tools
        """
        query = self.session.query(self.model).filter(
            self.model.status == "CHECKED_OUT"
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_tool_status(self, tool_id: int, status: str) -> Optional[Tool]:
        """
        Update a tool's status.

        Args:
            tool_id (int): ID of the tool
            status (str): New status to set

        Returns:
            Optional[Tool]: Updated tool if found, None otherwise
        """
        tool = self.get_by_id(tool_id)
        if not tool:
            return None

        tool.status = status

        self.session.commit()
        self.session.refresh(tool)
        return self._decrypt_sensitive_fields(tool)

    def update_tool_maintenance_schedule(
        self, tool_id: int, last_maintenance: str, next_maintenance: str
    ) -> Optional[Tool]:
        """
        Update a tool's maintenance schedule.

        Args:
            tool_id (int): ID of the tool
            last_maintenance (str): Date of the last maintenance
            next_maintenance (str): Date of the next scheduled maintenance

        Returns:
            Optional[Tool]: Updated tool if found, None otherwise
        """
        tool = self.get_by_id(tool_id)
        if not tool:
            return None

        tool.lastMaintenance = last_maintenance
        tool.nextMaintenance = next_maintenance

        self.session.commit()
        self.session.refresh(tool)
        return self._decrypt_sensitive_fields(tool)

    def search_tools(self, query: str, skip: int = 0, limit: int = 100) -> List[Tool]:
        """
        Search for tools by name, description, or model.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Tool]: List of matching tools
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.description.ilike(f"%{query}%"),
                self.model.model.ilike(f"%{query}%"),
                self.model.brand.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]


class ToolMaintenanceRepository(BaseRepository[ToolMaintenance]):
    """
    Repository for ToolMaintenance entity operations.

    Handles data access for tool maintenance records, including
    maintenance scheduling, history, and performance tracking.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ToolMaintenanceRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = ToolMaintenance

    def get_maintenance_by_tool(
        self, tool_id: int, skip: int = 0, limit: int = 100
    ) -> List[ToolMaintenance]:
        """
        Get maintenance records for a specific tool.

        Args:
            tool_id (int): ID of the tool
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ToolMaintenance]: List of maintenance records for the tool
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.toolId == tool_id)
            .order_by(desc(self.model.date))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_maintenance_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[ToolMaintenance]:
        """
        Get maintenance records by status.

        Args:
            status (str): The maintenance status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ToolMaintenance]: List of maintenance records with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_maintenance_by_date_range(
        self, start_date: str, end_date: str, skip: int = 0, limit: int = 100
    ) -> List[ToolMaintenance]:
        """
        Get maintenance records within a specific date range.

        Args:
            start_date (str): Start of the date range
            end_date (str): End of the date range
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ToolMaintenance]: List of maintenance records within the date range
        """
        query = self.session.query(self.model).filter(
            and_(self.model.date >= start_date, self.model.date <= end_date)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_scheduled_maintenance(
        self, skip: int = 0, limit: int = 100
    ) -> List[ToolMaintenance]:
        """
        Get scheduled maintenance records.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ToolMaintenance]: List of scheduled maintenance records
        """
        query = self.session.query(self.model).filter(self.model.status == "SCHEDULED")

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_maintenance_status(
        self, maintenance_id: int, status: str
    ) -> Optional[ToolMaintenance]:
        """
        Update a maintenance record's status.

        Args:
            maintenance_id (int): ID of the maintenance record
            status (str): New status to set

        Returns:
            Optional[ToolMaintenance]: Updated maintenance record if found, None otherwise
        """
        maintenance = self.get_by_id(maintenance_id)
        if not maintenance:
            return None

        maintenance.status = status

        # If maintenance is completed, update related fields
        if status == "COMPLETED":
            maintenance.updatedAt = datetime.now()

        self.session.commit()
        self.session.refresh(maintenance)
        return self._decrypt_sensitive_fields(maintenance)

    def create_maintenance_record(
        self,
        tool_id: int,
        tool_name: str,
        maintenance_type: str,
        performed_by: str,
        status: str = "SCHEDULED",
        date: Optional[str] = None,
    ) -> ToolMaintenance:
        """
        Create a new maintenance record.

        Args:
            tool_id (int): ID of the tool
            tool_name (str): Name of the tool
            maintenance_type (str): Type of maintenance
            performed_by (str): Name or ID of who performed or will perform the maintenance
            status (str, optional): Status of the maintenance record
            date (Optional[str], optional): Date of the maintenance

        Returns:
            ToolMaintenance: The created maintenance record
        """
        if date is None:
            date = datetime.now().isoformat()

        maintenance_data = {
            "toolId": tool_id,
            "toolName": tool_name,
            "maintenanceType": maintenance_type,
            "performedBy": performed_by,
            "date": date,
            "status": status,
            "createdAt": datetime.now(),
            "updatedAt": datetime.now(),
        }

        return self.create(maintenance_data)


class ToolCheckoutRepository(BaseRepository[ToolCheckout]):
    """
    Repository for ToolCheckout entity operations.

    Manages tool checkout records, including current checkouts,
    checkout history, and overdue tools tracking.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ToolCheckoutRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = ToolCheckout

    def get_checkouts_by_tool(
        self, tool_id: int, skip: int = 0, limit: int = 100
    ) -> List[ToolCheckout]:
        """
        Get checkout records for a specific tool.

        Args:
            tool_id (int): ID of the tool
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ToolCheckout]: List of checkout records for the tool
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.toolId == tool_id)
            .order_by(desc(self.model.checkedOutDate))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_checkouts_by_project(
        self, project_id: int, skip: int = 0, limit: int = 100
    ) -> List[ToolCheckout]:
        """
        Get checkout records for a specific project.

        Args:
            project_id (int): ID of the project
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ToolCheckout]: List of checkout records for the project
        """
        query = self.session.query(self.model).filter(
            self.model.projectId == project_id
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_checkouts_by_user(
        self, checked_out_by: str, skip: int = 0, limit: int = 100
    ) -> List[ToolCheckout]:
        """
        Get checkout records for a specific user.

        Args:
            checked_out_by (str): Name or ID of the user
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ToolCheckout]: List of checkout records for the user
        """
        query = self.session.query(self.model).filter(
            self.model.checkedOutBy == checked_out_by
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_active_checkouts(
        self, skip: int = 0, limit: int = 100
    ) -> List[ToolCheckout]:
        """
        Get active checkout records (tools currently checked out).

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ToolCheckout]: List of active checkout records
        """
        query = self.session.query(self.model).filter(
            self.model.status == "CHECKED_OUT"
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_overdue_checkouts(
        self, skip: int = 0, limit: int = 100
    ) -> List[ToolCheckout]:
        """
        Get overdue checkout records (tools past their due date).

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ToolCheckout]: List of overdue checkout records
        """
        now = datetime.now().isoformat()

        query = self.session.query(self.model).filter(
            and_(self.model.status == "CHECKED_OUT", self.model.dueDate < now)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def create_checkout(
        self,
        tool_id: int,
        tool_name: str,
        checked_out_by: str,
        due_date: str,
        project_id: Optional[int] = None,
        project_name: Optional[str] = None,
    ) -> ToolCheckout:
        """
        Create a new checkout record.

        Args:
            tool_id (int): ID of the tool
            tool_name (str): Name of the tool
            checked_out_by (str): Name or ID of the user checking out the tool
            due_date (str): Date when the tool is due to be returned
            project_id (Optional[int], optional): ID of the associated project
            project_name (Optional[str], optional): Name of the associated project

        Returns:
            ToolCheckout: The created checkout record
        """
        checkout_data = {
            "toolId": tool_id,
            "toolName": tool_name,
            "checkedOutBy": checked_out_by,
            "checkedOutDate": datetime.now().isoformat(),
            "dueDate": due_date,
            "projectId": project_id,
            "projectName": project_name,
            "status": "CHECKED_OUT",
            "createdAt": datetime.now(),
        }

        return self.create(checkout_data)

    def return_tool(
        self,
        checkout_id: int,
        condition_after: Optional[str] = None,
        issue_description: Optional[str] = None,
    ) -> Optional[ToolCheckout]:
        """
        Record a tool return.

        Args:
            checkout_id (int): ID of the checkout record
            condition_after (Optional[str], optional): Condition of the tool after return
            issue_description (Optional[str], optional): Description of any issues with the tool

        Returns:
            Optional[ToolCheckout]: Updated checkout record if found, None otherwise
        """
        checkout = self.get_by_id(checkout_id)
        if not checkout:
            return None

        checkout.returnedDate = datetime.now().isoformat()
        checkout.updatedAt = datetime.now()

        if condition_after:
            checkout.conditionAfter = condition_after

        if issue_description:
            checkout.issueDescription = issue_description
            checkout.status = "RETURNED_WITH_ISSUES"
        else:
            checkout.status = "RETURNED"

        self.session.commit()
        self.session.refresh(checkout)
        return self._decrypt_sensitive_fields(checkout)
