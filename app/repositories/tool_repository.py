# File: app/repositories/tool_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime, date # Import date

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
        """ Get tools by category. """
        query = self.session.query(self.model).filter(self.model.category == category)
        entities = query.offset(skip).limit(limit).all()
        # Decryption handled in BaseRepository potentially, or remove if not needed
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_tools_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[Tool]:
        """ Get tools by status. """
        query = self.session.query(self.model).filter(self.model.status == status)
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_tools_by_location(
        self, location: str, skip: int = 0, limit: int = 100
    ) -> List[Tool]:
        """ Get tools by storage location. """
        query = self.session.query(self.model).filter(self.model.location == location)
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_tools_due_for_maintenance(
        self, skip: int = 0, limit: int = 100
    ) -> List[Tool]:
        """ Get tools that are due for maintenance (using date comparison). """
        # Compare against today's date object
        today = date.today()
        query = self.session.query(self.model).filter(
            and_(
                self.model.next_maintenance != None, # Ensure next_maintenance is not NULL
                self.model.next_maintenance <= today
            )
        )
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_checked_out_tools(self, skip: int = 0, limit: int = 100) -> List[Tool]:
        """ Get tools that are currently checked out. """
        query = self.session.query(self.model).filter(
            self.model.status == "CHECKED_OUT"
        )
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_tool_status(self, tool_id: int, status: str) -> Optional[Tool]:
        """ Update a tool's status. """
        tool = self.get_by_id(tool_id)
        if not tool:
            return None
        tool.status = status
        # self.session.commit() # BaseRepository handles commit/refresh
        # self.session.refresh(tool)
        # return self._decrypt_sensitive_fields(tool)
        return self.update(tool_id, {"status": status}) # Use BaseRepository update

    def update_tool_maintenance_schedule(
        self, tool_id: int, last_maintenance: date, next_maintenance: Optional[date] # Use date objects
    ) -> Optional[Tool]:
        """ Update a tool's maintenance schedule using date objects. """
        tool = self.get_by_id(tool_id)
        if not tool:
            return None

        update_data = {
            "last_maintenance": last_maintenance,
            "next_maintenance": next_maintenance
        }
        # Use BaseRepository update
        return self.update(tool_id, update_data)


    def search_tools(self, query: str, skip: int = 0, limit: int = 100, **filters) -> List[Tool]:
        """ Search for tools by name, description, model, brand, with optional filters. """
        search_filter = or_(
            self.model.name.ilike(f"%{query}%"),
            self.model.description.ilike(f"%{query}%"),
            self.model.model.ilike(f"%{query}%"),
            self.model.brand.ilike(f"%{query}%"),
        )

        # Start query with the search filter
        db_query = self.session.query(self.model).filter(search_filter)

        # Apply additional filters passed via **filters
        for key, value in filters.items():
             if hasattr(self.model, key) and value is not None:
                 db_query = db_query.filter(getattr(self.model, key) == value)

        entities = db_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]


class ToolMaintenanceRepository(BaseRepository[ToolMaintenance]):
    """ Repository for ToolMaintenance entity operations. """
    def __init__(self, session: Session, encryption_service=None):
        super().__init__(session, encryption_service)
        self.model = ToolMaintenance

    def get_maintenance_by_tool(
        self, tool_id: int, skip: int = 0, limit: int = 100
    ) -> List[ToolMaintenance]:
        """ Get maintenance records for a specific tool. """
        query = (
            self.session.query(self.model)
            .filter(self.model.tool_id == tool_id) # Corrected column name
            .order_by(desc(self.model.date))
        )
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_maintenance_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[ToolMaintenance]:
        """ Get maintenance records by status. """
        query = self.session.query(self.model).filter(self.model.status == status)
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_maintenance_by_date_range(
        self, start_date: date, end_date: date, skip: int = 0, limit: int = 100, status: Optional[str] = None
    ) -> List[ToolMaintenance]:
        """ Get maintenance records within a specific date range (using date objects). """
        query = self.session.query(self.model).filter(
            and_(
                self.model.date != None, # Ensure date is not NULL
                self.model.date >= start_date,
                self.model.date <= end_date
            )
        )
        if status:
             query = query.filter(self.model.status == status)

        entities = query.order_by(self.model.date).offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_scheduled_maintenance(
        self, skip: int = 0, limit: int = 100
    ) -> List[ToolMaintenance]:
        """ Get scheduled maintenance records. """
        query = self.session.query(self.model).filter(self.model.status == "SCHEDULED")
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_maintenance_status(
        self, maintenance_id: int, status: str
    ) -> Optional[ToolMaintenance]:
        """ Update a maintenance record's status. """
        maintenance = self.get_by_id(maintenance_id)
        if not maintenance:
            return None

        update_data = {"status": status}
        if status == "COMPLETED":
            update_data["updated_at"] = datetime.now() # Update timestamp if completed

        # Use BaseRepository update
        return self.update(maintenance_id, update_data)

    def create_maintenance_record(
        self,
        tool_id: int,
        tool_name: str,
        maintenance_type: str,
        performed_by: Optional[str], # Allow Optional
        date: date, # Expect date object
        status: str = "SCHEDULED",
    ) -> ToolMaintenance:
        """ Create a new maintenance record using date object. """
        maintenance_data = {
            "tool_id": tool_id,
            "tool_name": tool_name,
            "maintenance_type": maintenance_type,
            "performed_by": performed_by,
            "date": date,
            "status": status,
            # createdAt/updatedAt handled by TimestampMixin in BaseRepository create
        }
        return self.create(maintenance_data)


class ToolCheckoutRepository(BaseRepository[ToolCheckout]):
    """ Repository for ToolCheckout entity operations. """
    def __init__(self, session: Session, encryption_service=None):
        super().__init__(session, encryption_service)
        self.model = ToolCheckout

    def get_checkouts_by_tool(
        self, tool_id: int, skip: int = 0, limit: int = 100
    ) -> List[ToolCheckout]:
        """ Get checkout records for a specific tool. """
        query = (
            self.session.query(self.model)
            .filter(self.model.tool_id == tool_id) # Corrected column name
            .order_by(desc(self.model.checked_out_date)) # Corrected column name
        )
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_checkouts_by_project(
        self, project_id: int, skip: int = 0, limit: int = 100
    ) -> List[ToolCheckout]:
        """ Get checkout records for a specific project. """
        query = self.session.query(self.model).filter(
            self.model.project_id == project_id # Corrected column name
        )
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_checkouts_by_user(
        self, checked_out_by: str, skip: int = 0, limit: int = 100
    ) -> List[ToolCheckout]:
        """ Get checkout records for a specific user. """
        query = self.session.query(self.model).filter(
            self.model.checked_out_by == checked_out_by # Corrected column name
        )
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_active_checkouts(
        self, skip: int = 0, limit: int = 100
    ) -> List[ToolCheckout]:
        """ Get active checkout records (tools currently checked out). """
        query = self.session.query(self.model).filter(
            self.model.status == "CHECKED_OUT"
        )
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_overdue_checkouts(
        self, skip: int = 0, limit: int = 100
    ) -> List[ToolCheckout]:
        """ Get overdue checkout records (using date comparison). """
        # Compare against today's date object
        today = date.today()
        query = self.session.query(self.model).filter(
            and_(
                self.model.status == "CHECKED_OUT",
                self.model.due_date != None, # Ensure due_date is not NULL
                self.model.due_date < today
            )
        )
        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def create_checkout(
        self,
        tool_id: int,
        tool_name: str,
        checked_out_by: str,
        checked_out_date: datetime, # Expect datetime object
        due_date: date,           # Expect date object
        project_id: Optional[int] = None,
        project_name: Optional[str] = None,
    ) -> ToolCheckout:
        """ Create a new checkout record using datetime/date objects. """
        checkout_data = {
            "tool_id": tool_id,
            "tool_name": tool_name,
            "checked_out_by": checked_out_by,
            "checked_out_date": checked_out_date,
            "due_date": due_date,
            "project_id": project_id,
            "project_name": project_name,
            "status": "CHECKED_OUT",
            # createdAt/updatedAt handled by TimestampMixin in BaseRepository create
        }
        return self.create(checkout_data)

    def return_tool(
        self,
        checkout_id: int,
        returned_date: datetime, # Expect datetime object
        condition_after: Optional[str] = None,
        issue_description: Optional[str] = None,
    ) -> Optional[ToolCheckout]:
        """ Record a tool return using datetime object. """
        checkout = self.get_by_id(checkout_id)
        if not checkout:
            return None

        update_data = {
            "returned_date": returned_date,
            # "updated_at": returned_date, # Use BaseRepository update which handles this
            "status": "RETURNED_WITH_ISSUES" if issue_description else "RETURNED"
        }

        if condition_after:
            update_data["condition_after"] = condition_after
        if issue_description:
            update_data["issue_description"] = issue_description

        # Use BaseRepository update
        return self.update(checkout_id, update_data)