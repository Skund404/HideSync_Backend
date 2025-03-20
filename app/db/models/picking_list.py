# File: app/db/models/picking_list.py
"""
Picking list models for the Leathercraft ERP system.

This module defines the PickingList and PickingListItem models for
tracking materials needed for projects and their collection status.
These models are used to prepare materials for production.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime

from sqlalchemy import Column, String, Text, Float, Enum, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import PickingListStatus


class PickingList(AbstractBase, ValidationMixin, TimestampMixin):
    """
    PickingList model for tracking materials needed for a project.

    This model represents a list of materials that need to be collected
    from inventory for a specific project, including their status and
    assignment information.

    Attributes:
        project_id: ID of the associated project
        sale_id: ID of the associated sale
        status: Current picking list status
        assigned_to: Person assigned to pick the items
        completed_at: Completion date/time
        notes: Additional notes
    """

    __tablename__ = "picking_lists"
    __validated_fields__: ClassVar[Set[str]] = {"project_id"}

    # Relationships
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)

    # Status information
    status = Column(Enum(PickingListStatus), default=PickingListStatus.PENDING)
    assigned_to = Column(String(100))
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text)

    # Relationships
    project = relationship("Project", back_populates="picking_lists")
    sale = relationship("Sale", back_populates="picking_list")
    items = relationship(
        "PickingListItem", back_populates="picking_list", cascade="all, delete-orphan"
    )

    @hybrid_property
    def is_complete(self) -> bool:
        """
        Check if picking list is complete.

        Returns:
            True if status is COMPLETED, False otherwise
        """
        return self.status == PickingListStatus.COMPLETED

    @hybrid_property
    def progress_percentage(self) -> float:
        """
        Calculate completion percentage.

        Returns:
            Percentage of items that have been picked
        """
        if not self.items:
            return 0.0

        total_items = len(self.items)
        complete_items = sum(1 for item in self.items if item.status == "complete")
        partial_items = sum(1 for item in self.items if item.status == "partial")

        # Count partial items as 0.5 for calculation
        return ((complete_items + (partial_items * 0.5)) / total_items) * 100

    def mark_complete(self, completed_by: str) -> None:
        """
        Mark picking list as complete.

        Args:
            completed_by: Person completing the list

        Raises:
            ValueError: If not all items are picked
        """
        # Check if all items are picked
        if self.progress_percentage < 100:
            raise ValueError("Cannot mark as complete: not all items are picked")

        self.status = PickingListStatus.COMPLETED
        self.assigned_to = completed_by
        self.completed_at = datetime.now()

    def add_item(
        self,
        material_id: Optional[int] = None,
        component_id: Optional[int] = None,
        quantity_ordered: int = 1,
        notes: Optional[str] = None,
    ) -> "PickingListItem":
        """
        Add an item to the picking list.

        Args:
            material_id: ID of the material
            component_id: ID of the component
            quantity_ordered: Quantity needed
            notes: Additional notes

        Returns:
            Created PickingListItem

        Raises:
            ValueError: If neither material_id nor component_id is provided
        """
        if not material_id and not component_id:
            raise ValueError("Either material_id or component_id must be provided")

        item = PickingListItem(
            picking_list_id=self.id,
            material_id=material_id,
            component_id=component_id,
            quantity_ordered=quantity_ordered,
            quantity_picked=0,
            status="pending",
            notes=notes,
        )

        return item

    def update_status_from_items(self) -> None:
        """
        Update status based on item statuses.
        """
        if not self.items:
            self.status = PickingListStatus.PENDING
            return

        all_complete = all(item.status == "complete" for item in self.items)
        any_picked = any(item.status in ["partial", "complete"] for item in self.items)

        if all_complete:
            self.status = PickingListStatus.COMPLETED
            if not self.completed_at:
                self.completed_at = datetime.now()
        elif any_picked:
            self.status = PickingListStatus.PARTIALLY_PICKED
        else:
            self.status = PickingListStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert PickingList instance to a dictionary.

        Returns:
            Dictionary representation of the picking list
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.status:
            result["status"] = self.status.name

        # Add calculated properties
        result["is_complete"] = self.is_complete
        result["progress_percentage"] = self.progress_percentage

        return result

    def __repr__(self) -> str:
        """Return string representation of the PickingList."""
        return f"<PickingList(id={self.id}, project_id={self.project_id}, status={self.status})>"


class PickingListItem(AbstractBase, ValidationMixin):
    """
    PickingListItem model for individual items in a picking list.

    This model represents an individual material or component that needs to be
    picked from inventory for a project, along with its status and quantities.

    Attributes:
        picking_list_id: ID of the parent picking list
        material_id: ID of the material to pick
        component_id: ID of the component requiring material
        quantity_ordered: Quantity needed
        quantity_picked: Quantity picked so far
        status: Picking status (pending/partial/complete)
        notes: Additional notes
    """

    __tablename__ = "picking_list_items"
    __validated_fields__: ClassVar[Set[str]] = {"picking_list_id", "quantity_ordered"}

    # Relationships
    picking_list_id = Column(String(36), ForeignKey("picking_lists.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)
    component_id = Column(Integer, ForeignKey("components.id"), nullable=True)

    # Item information
    quantity_ordered = Column(Integer, nullable=False)
    quantity_picked = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending/partial/complete
    notes = Column(Text)

    # Relationships
    picking_list = relationship("PickingList", back_populates="items")
    material = relationship("Material", back_populates="picking_list_items")
    component = relationship("Component", back_populates="picking_list_items")

    @validates("quantity_ordered")
    def validate_quantity_ordered(self, key: str, quantity: int) -> int:
        """
        Validate ordered quantity.

        Args:
            key: Field name ('quantity_ordered')
            quantity: Quantity to validate

        Returns:
            Validated quantity

        Raises:
            ValueError: If quantity is less than 1
        """
        if quantity < 1:
            raise ValueError("Ordered quantity must be at least 1")
        return quantity

    @validates("quantity_picked")
    def validate_quantity_picked(self, key: str, quantity: int) -> int:
        """
        Validate picked quantity and update status.

        Args:
            key: Field name ('quantity_picked')
            quantity: Quantity to validate

        Returns:
            Validated quantity

        Raises:
            ValueError: If quantity is negative or exceeds ordered quantity
        """
        if quantity < 0:
            raise ValueError("Picked quantity cannot be negative")

        if hasattr(self, "quantity_ordered") and quantity > self.quantity_ordered:
            raise ValueError("Picked quantity cannot exceed ordered quantity")

        # Update status based on quantity
        if hasattr(self, "quantity_ordered"):
            if quantity == 0:
                self.status = "pending"
            elif quantity < self.quantity_ordered:
                self.status = "partial"
            else:
                self.status = "complete"

        return quantity

    def pick(self, quantity: int) -> None:
        """
        Record picked quantity.

        Args:
            quantity: Quantity picked

        Raises:
            ValueError: If total would exceed ordered quantity
        """
        total_picked = self.quantity_picked + quantity

        if total_picked > self.quantity_ordered:
            raise ValueError(
                f"Cannot pick {quantity} more items: would exceed ordered quantity"
            )

        self.quantity_picked = total_picked

        # Update parent picking list status
        if self.picking_list and hasattr(self.picking_list, "update_status_from_items"):
            self.picking_list.update_status_from_items()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert PickingListItem instance to a dictionary.

        Returns:
            Dictionary representation of the picking list item
        """
        result = super().to_dict()

        # Add material and component names if available
        if hasattr(self, "material") and self.material:
            result["material_name"] = self.material.name

        if hasattr(self, "component") and self.component:
            result["component_name"] = self.component.name

        return result

    def __repr__(self) -> str:
        """Return string representation of the PickingListItem."""
        return f"<PickingListItem(id={self.id}, status='{self.status}', picked={self.quantity_picked}/{self.quantity_ordered})>"
