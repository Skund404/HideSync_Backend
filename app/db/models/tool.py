# File: app/db/models/tool.py
"""
Tool management models for the Leathercraft ERP system.

This module defines the Tool model representing equipment used in
leatherworking, along with the ToolMaintenance model for tracking
maintenance activities and the ToolCheckout model for tracking usage.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime, date, timedelta

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Enum,
    Integer,
    ForeignKey,
    DateTime,
    Boolean,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import ToolCategory


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
        purchase_date: Date of purchase
        specifications: Detailed specifications
        status: Current tool status
        location: Storage location
        image: Image path/URL
        last_maintenance: Last maintenance date
        next_maintenance: Next scheduled maintenance
        maintenance_interval: Days between maintenance
        supplier_id: ID of the supplier
        supplier: Supplier name (denormalized)
        checked_out_to: Current holder (if checked out)
        checked_out_date: Date checked out
        due_date: Return due date
    """

    __tablename__ = "tools"
    __validated_fields__: ClassVar[Set[str]] = {"name", "category"}

    # Basic information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(Enum(ToolCategory), nullable=False)

    # Product information
    brand = Column(String(100))
    model = Column(String(100))
    serial_number = Column(String(100))

    # Purchase information
    purchase_price = Column(Float)
    purchase_date = Column(String(50))  # ISO date string

    # Technical information
    specifications = Column(Text)

    # Status and location
    status = Column(
        String(50), default="IN_STOCK"
    )  # IN_STOCK, CHECKED_OUT, MAINTENANCE, etc.
    location = Column(String(100))
    image = Column(String(255))

    # Maintenance information
    last_maintenance = Column(String(50))  # ISO date string
    next_maintenance = Column(String(50))  # ISO date string
    maintenance_interval = Column(Integer)  # Days

    # Supplier information
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier = Column(String(255))

    # Checkout information
    checked_out_to = Column(String(100))
    checked_out_date = Column(String(50))  # ISO date string
    due_date = Column(String(50))  # ISO date string

    # Relationships
    supplier_rel = relationship("Supplier", back_populates="tools")
    maintenance_history = relationship(
        "ToolMaintenance", back_populates="tool", cascade="all, delete-orphan"
    )
    checkouts = relationship(
        "ToolCheckout", back_populates="tool", cascade="all, delete-orphan"
    )
    inventory = relationship(
        "Inventory",
        primaryjoin="and_(Inventory.item_type=='tool', Inventory.item_id==Tool.id)",
        foreign_keys="[Inventory.item_id]",
        viewonly=True,
    )

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate tool name.

        Args:
            key: Field name ('name')
            name: Tool name to validate

        Returns:
            Validated name

        Raises:
            ValueError: If name is empty or too short
        """
        if not name or len(name.strip()) < 3:
            raise ValueError("Tool name must be at least 3 characters")
        return name.strip()

    @validates("purchase_price")
    def validate_purchase_price(
        self, key: str, price: Optional[float]
    ) -> Optional[float]:
        """
        Validate purchase price.

        Args:
            key: Field name ('purchase_price')
            price: Price to validate

        Returns:
            Validated price

        Raises:
            ValueError: If price is negative
        """
        if price is not None and price < 0:
            raise ValueError("Purchase price cannot be negative")
        return price

    @hybrid_property
    def is_checked_out(self) -> bool:
        """
        Check if tool is currently checked out.

        Returns:
            True if tool is checked out, False otherwise
        """
        return self.status == "CHECKED_OUT" and bool(self.checked_out_to)

    @hybrid_property
    def maintenance_due(self) -> bool:
        """
        Check if maintenance is due.

        Returns:
            True if maintenance is due, False otherwise
        """
        if not self.next_maintenance:
            return False

        try:
            next_date = datetime.fromisoformat(self.next_maintenance)
            return next_date <= datetime.now()
        except (ValueError, TypeError):
            return False

    @hybrid_property
    def days_since_purchase(self) -> Optional[int]:
        """
        Calculate days since purchase.

        Returns:
            Number of days since purchase, or None if no purchase date
        """
        if not self.purchase_date:
            return None

        try:
            purchase_date = datetime.fromisoformat(self.purchase_date)
            delta = datetime.now() - purchase_date
            return delta.days
        except (ValueError, TypeError):
            return None

    def schedule_maintenance(self, date: datetime) -> None:
        """
        Schedule maintenance for this tool.

        Args:
            date: Scheduled maintenance date
        """
        self.next_maintenance = date.isoformat()

        # Update status if appropriate
        if self.status == "IN_STOCK":
            self.status = "MAINTENANCE_SCHEDULED"

    def perform_maintenance(
        self,
        performed_by: str,
        maintenance_type: str,
        details: str,
        cost: Optional[float] = None,
    ) -> "ToolMaintenance":
        """
        Record completed maintenance.

        Args:
            performed_by: Person who performed maintenance
            maintenance_type: Type of maintenance
            details: Maintenance details
            cost: Maintenance cost

        Returns:
            Created ToolMaintenance record
        """
        now = datetime.now()

        # Create maintenance record
        maintenance = ToolMaintenance(
            tool_id=self.id,
            tool_name=self.name,
            maintenance_type=maintenance_type,
            date=now.isoformat(),
            performed_by=performed_by,
            cost=cost or 0,
            details=details,
            status="COMPLETED",
        )

        # Update tool records
        self.last_maintenance = now.isoformat()

        # Schedule next maintenance if interval is set
        if self.maintenance_interval:
            next_date = now + timedelta(days=self.maintenance_interval)
            self.next_maintenance = next_date.isoformat()

        # Update status
        self.status = "IN_STOCK"

        return maintenance

    def checkout(
        self,
        checked_out_by: str,
        project_id: Optional[int] = None,
        project_name: Optional[str] = None,
        due_date: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> "ToolCheckout":
        """
        Check out this tool to a user.

        Args:
            checked_out_by: Person checking out the tool
            project_id: Associated project ID
            project_name: Associated project name
            due_date: Return due date
            notes: Additional notes

        Returns:
            Created ToolCheckout record

        Raises:
            ValueError: If tool is already checked out
        """
        if self.is_checked_out:
            raise ValueError(f"Tool is already checked out to {self.checked_out_to}")

        now = datetime.now()
        due = due_date or (now + timedelta(days=7))  # Default to 7 days

        # Create checkout record
        checkout = ToolCheckout(
            tool_id=self.id,
            tool_name=self.name,
            checked_out_by=checked_out_by,
            checked_out_date=now.isoformat(),
            due_date=due.isoformat(),
            project_id=project_id,
            project_name=project_name,
            notes=notes,
            status="CHECKED_OUT",
        )

        # Update tool status
        self.status = "CHECKED_OUT"
        self.checked_out_to = checked_out_by
        self.checked_out_date = now.isoformat()
        self.due_date = due.isoformat()

        return checkout

    def return_tool(
        self, condition: str = "GOOD", issues: Optional[str] = None
    ) -> None:
        """
        Return this tool from checkout.

        Args:
            condition: Condition upon return
            issues: Any issues found
        """
        if not self.is_checked_out:
            return

        # Update the active checkout record
        active_checkout = next(
            (c for c in self.checkouts if c.status == "CHECKED_OUT"), None
        )
        if active_checkout:
            return_status = "RETURNED"
            if issues:
                return_status = "RETURNED_WITH_ISSUES"

            active_checkout.returned_date = datetime.now().isoformat()
            active_checkout.condition_after = condition
            active_checkout.issue_description = issues
            active_checkout.status = return_status

        # Update tool status
        self.status = "IN_STOCK" if condition == "GOOD" else "NEEDS_MAINTENANCE"
        self.checked_out_to = None
        self.checked_out_date = None
        self.due_date = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Tool instance to a dictionary.

        Returns:
            Dictionary representation of the tool
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.category:
            result["category"] = self.category.name

        # Add calculated properties
        result["is_checked_out"] = self.is_checked_out
        result["maintenance_due"] = self.maintenance_due
        result["days_since_purchase"] = self.days_since_purchase

        return result

    def __repr__(self) -> str:
        """Return string representation of the Tool."""
        return f"<Tool(id={self.id}, name='{self.name}', status='{self.status}')>"


class ToolMaintenance(AbstractBase, ValidationMixin, TimestampMixin):
    """
    ToolMaintenance model for tracking tool maintenance activities.

    This model records maintenance performed on tools, including
    details, costs, and outcomes.

    Attributes:
        tool_id: ID of the associated tool
        tool_name: Tool name (denormalized)
        maintenance_type: Type of maintenance
        date: Maintenance date
        performed_by: Person who performed maintenance
        cost: Maintenance cost
        internal_service: Whether maintenance was internal
        details: Maintenance details
        parts: Parts used
        condition_before: Condition before maintenance
        condition_after: Condition after maintenance
        status: Maintenance status
        next_date: Next scheduled maintenance
    """

    __tablename__ = "tool_maintenance"
    __validated_fields__: ClassVar[Set[str]] = {"tool_id", "maintenance_type"}

    # Relationships
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)

    # Basic information
    tool_name = Column(String(255))
    maintenance_type = Column(String(50), nullable=False)
    date = Column(String(50))  # ISO date string
    performed_by = Column(String(100))

    # Cost information
    cost = Column(Float, default=0)
    internal_service = Column(Boolean, default=True)

    # Details
    details = Column(Text)
    parts = Column(Text)
    condition_before = Column(String(100))
    condition_after = Column(String(100))

    # Status
    status = Column(
        String(50), default="SCHEDULED"
    )  # SCHEDULED, IN_PROGRESS, COMPLETED, etc.
    next_date = Column(String(50))  # ISO date string

    # Relationships
    tool = relationship("Tool", back_populates="maintenance_history")

    @validates("cost")
    def validate_cost(self, key: str, cost: float) -> float:
        """
        Validate maintenance cost.

        Args:
            key: Field name ('cost')
            cost: Cost to validate

        Returns:
            Validated cost

        Raises:
            ValueError: If cost is negative
        """
        if cost < 0:
            raise ValueError("Maintenance cost cannot be negative")
        return cost

    def mark_completed(
        self, condition_after: str, details: Optional[str] = None
    ) -> None:
        """
        Mark maintenance as completed.

        Args:
            condition_after: Tool condition after maintenance
            details: Additional details
        """
        self.status = "COMPLETED"
        self.condition_after = condition_after

        if details:
            if self.details:
                self.details += f"\n\nCompletion notes: {details}"
            else:
                self.details = details

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert ToolMaintenance instance to a dictionary.

        Returns:
            Dictionary representation of the maintenance record
        """
        result = super().to_dict()

        # Format dates for display
        for date_field in ["date", "next_date"]:
            if result.get(date_field):
                try:
                    dt = datetime.fromisoformat(result[date_field])
                    result[f"{date_field}_formatted"] = dt.strftime("%b %d, %Y")
                except (ValueError, TypeError):
                    pass

        return result

    def __repr__(self) -> str:
        """Return string representation of the ToolMaintenance."""
        return f"<ToolMaintenance(id={self.id}, tool_id={self.tool_id}, type='{self.maintenance_type}', status='{self.status}')>"


class ToolCheckout(AbstractBase, ValidationMixin, TimestampMixin):
    """
    ToolCheckout model for tracking tool usage.

    This model records tool checkouts to users and projects, including
    checkout dates, return dates, and condition information.

    Attributes:
        tool_id: ID of the associated tool
        tool_name: Tool name (denormalized)
        checked_out_by: Person who checked out the tool
        checked_out_date: Date checked out
        due_date: Return due date
        returned_date: Date returned
        project_id: Associated project ID
        project_name: Associated project name
        notes: Additional notes
        status: Checkout status
        condition_before: Condition when checked out
        condition_after: Condition when returned
        issue_description: Description of any issues
    """

    __tablename__ = "tool_checkouts"
    __validated_fields__: ClassVar[Set[str]] = {"tool_id", "checked_out_by"}

    # Relationships
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)

    # Checkout information
    tool_name = Column(String(255))
    checked_out_by = Column(String(100), nullable=False)
    checked_out_date = Column(String(50))  # ISO date string
    due_date = Column(String(50))  # ISO date string
    returned_date = Column(String(50))  # ISO date string

    # Project information
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    project_name = Column(String(255))
    notes = Column(Text)

    # Status
    status = Column(
        String(50), default="CHECKED_OUT"
    )  # CHECKED_OUT, RETURNED, RETURNED_WITH_ISSUES, OVERDUE
    condition_before = Column(String(100))
    condition_after = Column(String(100))
    issue_description = Column(Text)

    # Relationships
    tool = relationship("Tool", back_populates="checkouts")
    project = relationship("Project", back_populates="tool_checkouts")

    @hybrid_property
    def is_overdue(self) -> bool:
        """
        Check if checkout is overdue.

        Returns:
            True if checkout is overdue, False otherwise
        """
        if not self.due_date or self.status != "CHECKED_OUT":
            return False

        try:
            due_date = datetime.fromisoformat(self.due_date)
            return due_date < datetime.now()
        except (ValueError, TypeError):
            return False

    @hybrid_property
    def days_overdue(self) -> Optional[int]:
        """
        Calculate days overdue.

        Returns:
            Number of days overdue, or None if not overdue
        """
        if not self.is_overdue:
            return None

        try:
            due_date = datetime.fromisoformat(self.due_date)
            delta = datetime.now() - due_date
            return delta.days
        except (ValueError, TypeError):
            return None

    def extend_due_date(self, new_due_date: datetime, reason: str) -> None:
        """
        Extend the due date.

        Args:
            new_due_date: New due date
            reason: Reason for extension
        """
        old_due_date = self.due_date
        self.due_date = new_due_date.isoformat()

        # Update tool due date as well
        if self.tool and hasattr(self.tool, "due_date"):
            self.tool.due_date = new_due_date.isoformat()

        # Add note about extension
        extension_note = f"Due date extended from {old_due_date} to {self.due_date}. Reason: {reason}"
        if self.notes:
            self.notes += f"\n\n{extension_note}"
        else:
            self.notes = extension_note

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert ToolCheckout instance to a dictionary.

        Returns:
            Dictionary representation of the checkout record
        """
        result = super().to_dict()

        # Format dates for display
        for date_field in ["checked_out_date", "due_date", "returned_date"]:
            if result.get(date_field):
                try:
                    dt = datetime.fromisoformat(result[date_field])
                    result[f"{date_field}_formatted"] = dt.strftime("%b %d, %Y")
                except (ValueError, TypeError):
                    pass

        # Add calculated properties
        result["is_overdue"] = self.is_overdue
        result["days_overdue"] = self.days_overdue

        return result

    def __repr__(self) -> str:
        """Return string representation of the ToolCheckout."""
        return f"<ToolCheckout(id={self.id}, tool_id={self.tool_id}, checked_out_by='{self.checked_out_by}', status='{self.status}')>"
