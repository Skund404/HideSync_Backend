# File: app/db/models/tool.py
"""
Tool management models for the Leathercraft ERP system.

This module defines the Tool model representing equipment used in
leatherworking, along with the ToolMaintenance model for tracking
maintenance activities and the ToolCheckout model for tracking usage.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime, date, timedelta  # Import date

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Enum,
    Integer,
    ForeignKey,
    DateTime,
    Date,  # <-- Import Date type
    Boolean,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import ToolCategory

import logging

logger = logging.getLogger(__name__)


class Tool(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Tool model representing leatherworking equipment.

    This model tracks tools and equipment used in leatherworking,
    including specifications, maintenance history, and checkout status.

    Attributes:
        name: Tool name/description
        description: Detailed tool description
        category: Tool category
        brand: Manufacturer brand
        model: Model number/name
        serial_number: Serial number
        purchase_price: Purchase price
        purchase_date: Date of purchase (Date type)
        specifications: Detailed specifications
        status: Current tool status
        location: Storage location
        image: Image path/URL
        last_maintenance: Last maintenance date (Date type)
        next_maintenance: Next scheduled maintenance (Date type)
        maintenance_interval: Days between maintenance
        supplier_id: ID of the supplier
        supplier: Supplier name (denormalized)
        checked_out_to: Current holder (if checked out)
        checked_out_date: Date checked out (DateTime type)
        due_date: Return due date (Date type)
    """

    __tablename__ = "tools"
    __validated_fields__: ClassVar[Set[str]] = {
        "name",
        "category",
    }  # Add more if needed

    # Basic information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(Enum(ToolCategory), nullable=False)

    # Product information
    brand = Column(String(100))
    model = Column(String(100))
    serial_number = Column(
        String(100), unique=True, nullable=True
    )  # Make unique if applicable

    # Purchase information
    purchase_price = Column(Float, nullable=True)
    # --- MODIFIED: Use Date type ---
    purchase_date = Column(Date, nullable=True)

    # Technical information
    specifications = Column(Text, nullable=True)

    # Status and location
    status = Column(
        String(50), default="IN_STOCK", nullable=False
    )  # IN_STOCK, CHECKED_OUT, MAINTENANCE, etc.
    location = Column(String(100), nullable=True)
    image = Column(String(255), nullable=True)  # Image URL/path

    # Maintenance information
    # --- MODIFIED: Use Date type ---
    last_maintenance = Column(Date, nullable=True)
    next_maintenance = Column(Date, nullable=True)
    maintenance_interval = Column(Integer, nullable=True)  # Days

    # Supplier information
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier = Column(
        String(255), nullable=True
    )  # Denormalized, maybe remove if always joining

    # Checkout information
    checked_out_to = Column(String(100), nullable=True)  # Name or ID of user/project
    # --- MODIFIED: Use DateTime type ---
    checked_out_date = Column(DateTime, nullable=True)
    # --- MODIFIED: Use Date type ---
    due_date = Column(Date, nullable=True)

    # Relationships (keep as before)
    supplier_rel = relationship("Supplier", back_populates="tools")
    maintenance_history = relationship(
        "ToolMaintenance",
        back_populates="tool",
        cascade="all, delete-orphan",
        lazy="dynamic",  # Use lazy="dynamic" if history can be large
    )
    checkouts = relationship(
        "ToolCheckout",
        back_populates="tool",
        cascade="all, delete-orphan",
        lazy="dynamic",  # Use lazy="dynamic" if history can be large
    )
    # Overlap definition seems okay if needed for inventory relationship specifics
    inventory = relationship(
        "Inventory",
        primaryjoin="and_(Inventory.item_type=='tool', foreign(Inventory.item_id)==Tool.id)",
        back_populates="tool",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
        passive_deletes=True,
        overlaps="inventory",
    )
    # Timestamps created_at, updated_at are handled by TimestampMixin

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        if not name or len(name.strip()) < 3:
            raise ValueError("Tool name must be at least 3 characters")
        return name.strip()

    @validates("purchase_price")
    def validate_purchase_price(
        self, key: str, price: Optional[float]
    ) -> Optional[float]:
        if price is not None and price < 0:
            raise ValueError("Purchase price cannot be negative")
        return price

    @validates("maintenance_interval")
    def validate_maintenance_interval(
        self, key: str, interval: Optional[int]
    ) -> Optional[int]:
        if interval is not None and interval <= 0:
            raise ValueError("Maintenance interval must be a positive number of days")
        return interval

    # --- Hybrid Properties - Adjust date comparisons ---
    @hybrid_property
    def is_checked_out(self) -> bool:
        return self.status == "CHECKED_OUT"  # Simplified based on status

    @hybrid_property
    def maintenance_due(self) -> bool:
        if not self.next_maintenance:
            return False
        # Compare date objects directly
        return self.next_maintenance <= date.today()

    @hybrid_property
    def days_since_purchase(self) -> Optional[int]:
        if not self.purchase_date:
            return None
        # Calculate delta using date objects
        delta = date.today() - self.purchase_date
        return delta.days

    # --- Methods - Adjust date handling ---

    def schedule_maintenance(self, schedule_date: date) -> None:
        """Schedule maintenance for this tool using a date object."""
        if not isinstance(schedule_date, date):
            raise TypeError("schedule_date must be a date object")
        self.next_maintenance = schedule_date
        if self.status == "IN_STOCK":
            self.status = (
                "MAINTENANCE_SCHEDULED"  # Consider if this status exists/is needed
            )

    def perform_maintenance(
        self,
        performed_by: str,
        maintenance_type: str,
        details: str,
        cost: Optional[float] = None,
    ) -> "ToolMaintenance":
        """Record completed maintenance. Updates dates using date/datetime objects."""
        now_dt = datetime.now()
        today_date = now_dt.date()  # Use date object for date-only fields

        # --- Assume ToolMaintenance model uses Date/DateTime ---
        # Need to verify ToolMaintenance model definition
        maintenance = ToolMaintenance(
            tool_id=self.id,
            tool_name=self.name,
            maintenance_type=maintenance_type,
            date=today_date,  # Pass date object if ToolMaintenance.date is Date
            performed_by=performed_by,
            cost=cost or 0,
            details=details,
            status="COMPLETED",  # Use string status consistent with service/schema
            # Add created_at/updated_at if ToolMaintenance has TimestampMixin
        )

        self.last_maintenance = today_date  # Update with date object

        if self.maintenance_interval:
            next_date_obj = today_date + timedelta(days=self.maintenance_interval)
            self.next_maintenance = next_date_obj  # Update with date object
        else:
            self.next_maintenance = None  # Clear if no interval

        self.status = "IN_STOCK"  # Assume maintenance completion returns to stock
        # Add the maintenance record to the session implicitly via relationship?
        # Or return it to be added by the service layer. Returning is often cleaner.
        return maintenance  # Service layer should add this to session

    def checkout(
        self,
        checked_out_by: str,
        due_date_obj: date,  # Expect date object
        project_id: Optional[int] = None,
        project_name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> "ToolCheckout":
        """Check out this tool. Expects date objects."""
        if self.is_checked_out:
            raise ValueError(
                f"Tool {self.id} already checked out to {self.checked_out_to}"
            )
        if not isinstance(due_date_obj, date):
            raise TypeError("due_date_obj must be a date object")

        now_dt = datetime.now()

        # --- Assume ToolCheckout model uses Date/DateTime ---
        checkout = ToolCheckout(
            tool_id=self.id,
            tool_name=self.name,
            checked_out_by=checked_out_by,
            checked_out_date=now_dt,  # Pass datetime object
            due_date=due_date_obj,  # Pass date object
            project_id=project_id,
            project_name=project_name,
            notes=notes,
            status="CHECKED_OUT",  # Use string status
            # Add created_at/updated_at if ToolCheckout has TimestampMixin
        )

        self.status = "CHECKED_OUT"
        self.checked_out_to = checked_out_by
        self.checked_out_date = now_dt  # datetime object
        self.due_date = due_date_obj  # date object

        return checkout  # Service layer should add this to session

    def return_tool(
        self, condition: str = "GOOD", issues: Optional[str] = None
    ) -> None:
        """Return this tool from checkout. Updates associated checkout record."""
        if not self.is_checked_out:
            return  # Nothing to return

        now_dt = datetime.now()
        return_status = "RETURNED_WITH_ISSUES" if issues else "RETURNED"

        # Find the active checkout record to update
        # Using lazy="dynamic" allows filtering here
        active_checkout: Optional[ToolCheckout] = self.checkouts.filter(
            ToolCheckout.status == "CHECKED_OUT"
        ).first()

        if active_checkout:
            active_checkout.returned_date = now_dt  # Assume DateTime field
            active_checkout.condition_after = condition
            active_checkout.issue_description = issues
            active_checkout.status = return_status
            # active_checkout.updated_at = now_dt # If it has TimestampMixin
            logger.info(
                f"Updated active checkout {active_checkout.id} for tool {self.id} on return."
            )
        else:
            logger.warning(
                f"Could not find active checkout record for tool {self.id} during return."
            )
            # Decide how critical this is. Maybe just update tool status anyway?

        # Update tool status
        self.status = "MAINTENANCE" if issues else "IN_STOCK"  # Or DAMAGED
        self.checked_out_to = None
        self.checked_out_date = None
        self.due_date = None
        # self.updated_at will be updated by TimestampMixin

    def to_dict(self) -> Dict[str, Any]:
        """Convert Tool instance to a dictionary for API responses."""
        result = super().to_dict()  # Gets id, created_at, updated_at

        # Convert enums to strings
        if self.category:
            result["category"] = self.category.name
        # status is already string

        # Convert date/datetime objects to ISO strings for JSON
        date_fields = [
            "purchase_date",
            "last_maintenance",
            "next_maintenance",
            "due_date",
        ]
        datetime_fields = [
            "checked_out_date"
        ]  # Add created_at, updated_at if not handled by super

        for field in date_fields:
            value = getattr(self, field, None)
            if isinstance(value, date):
                result[field] = value.isoformat()
            elif value is None:
                result[field] = None  # Ensure None is explicit if applicable
            # Handle case where it might still be a string if loaded incorrectly? Defensive.
            # elif isinstance(value, str):
            #      result[field] = value

        for field in datetime_fields:
            value = getattr(self, field, None)
            if isinstance(value, datetime):
                result[field] = value.isoformat()
            elif value is None:
                result[field] = None

        # Add calculated properties
        result["is_checked_out"] = self.is_checked_out
        result["maintenance_due"] = self.maintenance_due
        result["days_since_purchase"] = self.days_since_purchase

        # Explicitly include potentially None fields if schema expects them
        for field in [
            "description",
            "brand",
            "model",
            "serial_number",
            "purchase_price",
            "specifications",
            "location",
            "image",
            "maintenance_interval",
            "supplier_id",
            "supplier",
            "checked_out_to",
        ]:
            result.setdefault(field, getattr(self, field, None))

        return result

    def __repr__(self) -> str:
        """Return string representation of the Tool."""
        return f"<Tool(id={self.id}, name='{self.name}', status='{self.status}')>"


# --- IMPORTANT: Update ToolMaintenance and ToolCheckout Models Similarly ---

# It's crucial that the 'date' fields in ToolMaintenance and the date fields
# ('checked_out_date', 'due_date', 'returned_date') in ToolCheckout are also
# changed from String to Date or DateTime as appropriate.


# Example Snippet for ToolMaintenance (ASSUMING it should use Date/DateTime)
class ToolMaintenance(
    AbstractBase, ValidationMixin, TimestampMixin
):  # Assuming it has TimestampMixin
    __tablename__ = "tool_maintenance"
    __validated_fields__: ClassVar[Set[str]] = {
        "tool_id",
        "maintenance_type",
        "cost",
    }  # Added cost

    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    tool_name = Column(String(255), nullable=True)  # Denormalized
    maintenance_type = Column(String(50), nullable=False)
    # --- MODIFIED: Use Date or DateTime ---
    date = Column(
        Date, nullable=True
    )  # Date maintenance *occurred* or is *scheduled* for
    performed_by = Column(String(100), nullable=True)
    cost = Column(Float, default=0)
    internal_service = Column(Boolean, default=True)
    details = Column(Text, nullable=True)
    parts = Column(Text, nullable=True)
    condition_before = Column(String(100), nullable=True)
    condition_after = Column(String(100), nullable=True)
    status = Column(
        String(50), default="SCHEDULED", nullable=False
    )  # SCHEDULED, IN_PROGRESS, COMPLETED, etc.
    # --- MODIFIED: Use Date or DateTime ---
    next_date = Column(
        Date, nullable=True
    )  # Next date *based on this specific maintenance event*? Often set on Tool directly.

    tool = relationship("Tool", back_populates="maintenance_history")
    # created_at, updated_at from TimestampMixin

    @validates("cost")
    def validate_cost(self, key: str, cost: Optional[float]) -> Optional[float]:
        if cost is not None and cost < 0:
            raise ValueError("Maintenance cost cannot be negative")
        return cost if cost is not None else 0.0  # Ensure default if None

    def __repr__(self) -> str:
        return f"<ToolMaintenance(id={self.id}, tool_id={self.tool_id}, type='{self.maintenance_type}', status='{self.status}')>"


# Example Snippet for ToolCheckout (ASSUMING it should use Date/DateTime)
class ToolCheckout(
    AbstractBase, ValidationMixin, TimestampMixin
):  # Assuming it has TimestampMixin
    __tablename__ = "tool_checkouts"
    __validated_fields__: ClassVar[Set[str]] = {"tool_id", "checked_out_by"}

    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    tool_name = Column(String(255), nullable=True)  # Denormalized
    checked_out_by = Column(String(100), nullable=False)
    # --- MODIFIED: Use DateTime ---
    checked_out_date = Column(DateTime, nullable=False)
    # --- MODIFIED: Use Date ---
    due_date = Column(Date, nullable=False)
    # --- MODIFIED: Use DateTime ---
    returned_date = Column(DateTime, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    project_name = Column(String(255), nullable=True)  # Denormalized
    notes = Column(Text, nullable=True)
    status = Column(
        String(50), default="CHECKED_OUT", nullable=False
    )  # CHECKED_OUT, RETURNED, RETURNED_WITH_ISSUES, OVERDUE
    condition_before = Column(String(100), nullable=True)
    condition_after = Column(String(100), nullable=True)
    issue_description = Column(Text, nullable=True)

    tool = relationship("Tool", back_populates="checkouts")
    project = relationship(
        "Project", back_populates="tool_checkouts"
    )  # Assuming Project model exists
    # created_at, updated_at from TimestampMixin

    # --- Hybrid Properties - Adjust date comparisons ---
    @hybrid_property
    def is_overdue(self) -> bool:
        if not self.due_date or self.status != "CHECKED_OUT":
            return False
        # Compare date objects
        return self.due_date < date.today()

    @hybrid_property
    def days_overdue(self) -> Optional[int]:
        if not self.is_overdue:
            return None
        # Calculate delta using date objects
        delta = date.today() - self.due_date
        return delta.days

    def __repr__(self) -> str:
        return f"<ToolCheckout(id={self.id}, tool_id={self.tool_id}, by='{self.checked_out_by}', status='{self.status}')>"
