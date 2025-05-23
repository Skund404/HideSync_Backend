# File: app/db/models/tool.py
"""
Tool management models for the Leathercraft ERP system.
... (rest of docstring) ...
"""

from typing import List, Optional, Dict, Any, ClassVar, Set, TYPE_CHECKING
from datetime import datetime, date, timedelta # Keep datetime, date imports

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Enum as SQLAlchemyEnum,
    Integer,
    ForeignKey,
    DateTime, # Use standard DateTime
    Date,     # Use standard Date
    Boolean,
    and_,
)
from sqlalchemy.orm import relationship, validates, configure_mappers, foreign, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import ToolCategory
# --- REMOVE THIS IMPORT ---
# from app.db.custom_types import SafeDate, SafeDateTime # No longer needed for dates

# --- KEEP THIS IMPORT IF YOU USE CaseInsensitiveEnum ---
# from app.db.custom_types import CaseInsensitiveEnum # Keep if used elsewhere in models

import logging

logger = logging.getLogger(__name__)

# Use TYPE_CHECKING block for imports needed only for type hinting
if TYPE_CHECKING:
    from app.db.models.inventory import Inventory
    from app.db.models.supplier import Supplier
    from app.db.models.project import Project
    from app.db.models.tool import ToolMaintenance, ToolCheckout


class Tool(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Tool model representing leatherworking equipment.
    """
    __tablename__ = "tools"
    __validated_fields__: ClassVar[Set[str]] = {"name", "category"}

    # --- Columns ---
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    # If you *were* using CaseInsensitiveEnum for category, it would look like:
    # category = Column(CaseInsensitiveEnum(ToolCategory), nullable=False)
    # But your original model used standard SQLAlchemyEnum, so keep that:
    category = Column(SQLAlchemyEnum(ToolCategory), nullable=False)
    brand = Column(String(100))
    model = Column(String(100))
    serial_number = Column(String(100), unique=True, nullable=True)
    purchase_price = Column(Float, nullable=True)

    # --- CHANGE BACK TO STANDARD Date/DateTime ---
    purchase_date = Column(Date, nullable=True)
    specifications = Column(Text, nullable=True)
    status = Column(String(50), default="IN_STOCK", nullable=False)
    location = Column(String(100), nullable=True)
    image = Column(String(255), nullable=True)
    last_maintenance = Column(Date, nullable=True)
    next_maintenance = Column(Date, nullable=True)
    maintenance_interval = Column(Integer, nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier = Column(String(255), nullable=True) # Denormalized? Okay if intended.
    checked_out_to = Column(String(100), nullable=True)
    checked_out_date = Column(DateTime, nullable=True)
    due_date = Column(Date, nullable=True)

    # --- CHANGE BACK TO STANDARD DateTime for TimestampMixin ---
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # --- Relationships (No changes needed here) ---
    supplier_rel: Mapped[Optional["Supplier"]] = relationship("Supplier", back_populates="tools")
    maintenance_history: Mapped[List["ToolMaintenance"]] = relationship(
        "ToolMaintenance", back_populates="tool", cascade="all, delete-orphan", lazy="dynamic",
    )
    checkouts: Mapped[List["ToolCheckout"]] = relationship(
        "ToolCheckout", back_populates="tool", cascade="all, delete-orphan", lazy="dynamic",
    )
    inventory: Mapped[Optional["Inventory"]] = relationship(
        "Inventory",
        primaryjoin="and_(foreign(Inventory.item_type)=='tool', foreign(Inventory.item_id)==Tool.id)",
        back_populates="tool", uselist=False, cascade="all, delete-orphan", lazy="joined",
        passive_deletes=True, overlaps="inventory",
    )

    # --- Validators (No changes needed here) ---
    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        if not name or len(name.strip()) < 3: raise ValueError("Tool name must be >= 3 chars")
        return name.strip()

    @validates("purchase_price")
    def validate_purchase_price(self, key: str, price: Optional[float]) -> Optional[float]:
        if price is not None and price < 0: raise ValueError("Price cannot be negative")
        return price

    @validates("maintenance_interval")
    def validate_maintenance_interval(self, key: str, interval: Optional[int]) -> Optional[int]:
        if interval is not None and interval <= 0: raise ValueError("Interval must be positive")
        return interval

    # --- Hybrid Properties (No changes needed here) ---
    @hybrid_property
    def is_checked_out(self) -> bool:
        return self.status == "CHECKED_OUT"

    @hybrid_property
    def maintenance_due(self) -> bool:
        if not self.next_maintenance or not isinstance(self.next_maintenance, date): return False
        return self.next_maintenance <= date.today()

    @hybrid_property
    def days_since_purchase(self) -> Optional[int]:
        if not self.purchase_date or not isinstance(self.purchase_date, date): return None
        delta = date.today() - self.purchase_date
        return delta.days

    # --- Methods (No changes needed, assuming they use standard date/datetime) ---
    def schedule_maintenance(self, schedule_date: date) -> None:
        if not isinstance(schedule_date, date): raise TypeError("schedule_date must be date object")
        self.next_maintenance = schedule_date

    def perform_maintenance(self, performed_by: str, maintenance_type: str, details: str,
                            cost: Optional[float] = None) -> "ToolMaintenance":
        now_dt = datetime.now()
        today_date = now_dt.date()
        # Assumes ToolMaintenance model also uses standard Date/DateTime
        maintenance = ToolMaintenance(tool_id=self.id, tool_name=self.name, maintenance_type=maintenance_type,
                                      date=today_date, performed_by=performed_by, cost=cost or 0.0, details=details,
                                      status="COMPLETED", created_at=now_dt, updated_at=now_dt)
        self.last_maintenance = today_date
        if self.maintenance_interval:
            self.next_maintenance = today_date + timedelta(days=self.maintenance_interval)
        else:
            self.next_maintenance = None
        if self.status == "MAINTENANCE": self.status = "IN_STOCK"
        return maintenance

    def checkout(self, checked_out_by: str, due_date_obj: date, project_id: Optional[int] = None,
                 project_name: Optional[str] = None, notes: Optional[str] = None) -> "ToolCheckout":
        if self.is_checked_out: raise ValueError(f"Tool {self.id} already checked out")
        if not isinstance(due_date_obj, date): raise TypeError("due_date_obj must be date object")
        now_dt = datetime.now()
        # Assumes ToolCheckout model also uses standard Date/DateTime
        checkout = ToolCheckout(tool_id=self.id, tool_name=self.name, checked_out_by=checked_out_by,
                                checked_out_date=now_dt, due_date=due_date_obj, project_id=project_id,
                                project_name=project_name, notes=notes, status="CHECKED_OUT", created_at=now_dt,
                                updated_at=now_dt)
        self.status = "CHECKED_OUT"
        self.checked_out_to = checked_out_by
        self.checked_out_date = now_dt
        self.due_date = due_date_obj
        return checkout

    def return_tool(self, condition: str = "GOOD", issues: Optional[str] = None) -> None:
        if not self.is_checked_out: return
        now_dt = datetime.now()
        return_status = "RETURNED_WITH_ISSUES" if issues else "RETURNED"
        active_checkout: Optional[ToolCheckout] = self.checkouts.filter(
            ToolCheckout.status == "CHECKED_OUT").first()
        if active_checkout:
            active_checkout.returned_date = now_dt
            active_checkout.condition_after = condition
            active_checkout.issue_description = issues
            active_checkout.status = return_status
            active_checkout.updated_at = now_dt
            logger.info(f"Updated active checkout {active_checkout.id} for tool {self.id} on return.")
        else:
            logger.warning(f"Could not find active checkout record for tool {self.id} during return.")
        self.status = "MAINTENANCE" if issues else "IN_STOCK"
        self.checked_out_to = None
        self.checked_out_date = None
        self.due_date = None

    # --- to_dict & __repr__ (No changes needed here) ---
    def to_dict(self) -> Dict[str, Any]:
        # This method should correctly handle standard date/datetime objects now
        result = super().to_dict()
        if isinstance(self.category, ToolCategory):
             result["category"] = self.category.value
        elif self.category:
             result["category"] = str(self.category) # Fallback
        # ... rest of the to_dict method ...
        date_fields = ["purchase_date", "last_maintenance", "next_maintenance", "due_date"]
        datetime_fields = ["checked_out_date", "created_at", "updated_at"]
        for field in date_fields:
            value = getattr(self, field, None)
            result[field] = value.isoformat() if isinstance(value, date) else None
        for field in datetime_fields:
            value = getattr(self, field, None)
            result[field] = value.isoformat() if isinstance(value, datetime) else None

        # Include other simple fields
        all_fields = ["name", "description", "brand", "model", "serial_number", "purchase_price", "specifications",
                      "status", "location", "image", "maintenance_interval", "supplier_id", "supplier",
                      "checked_out_to"]
        for field in all_fields:
            if field not in result:
                result[field] = getattr(self, field, None)

        # Add hybrid properties safely
        try: result["is_checked_out"] = self.is_checked_out
        except Exception: result["is_checked_out"] = None
        try: result["maintenance_due"] = self.maintenance_due
        except Exception: result["maintenance_due"] = None
        try: result["days_since_purchase"] = self.days_since_purchase
        except Exception: result["days_since_purchase"] = None

        # Add supplier summary if relation is loaded
        if hasattr(self, 'supplier_rel') and self.supplier_rel:
             result["supplier_rel"] = {
                 "id": self.supplier_rel.id,
                 "name": self.supplier_rel.name,
                 "category": self.supplier_rel.category
             }
        else:
             result["supplier_rel"] = None

        return result

    def __repr__(self) -> str:
        return f"<Tool(id={self.id}, name='{self.name}', status='{self.status}')>"


# --- ToolMaintenance Model ---
class ToolMaintenance(AbstractBase, ValidationMixin, TimestampMixin):
    __tablename__ = "tool_maintenance"
    __validated_fields__: ClassVar[Set[str]] = {"tool_id", "maintenance_type", "cost"}
    id = Column(Integer, primary_key=True, index=True)
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    tool_name = Column(String(255), nullable=True)
    maintenance_type = Column(String(50), nullable=False)
    # --- CHANGE BACK TO STANDARD Date/DateTime ---
    date = Column(Date, nullable=True)
    performed_by = Column(String(100), nullable=True)
    cost = Column(Float, default=0.0)
    internal_service = Column(Boolean, default=True)
    details = Column(Text, nullable=True)
    parts = Column(Text, nullable=True)
    condition_before = Column(String(100), nullable=True)
    condition_after = Column(String(100), nullable=True)
    status = Column(String(50), default="SCHEDULED", nullable=False)
    next_date = Column(Date, nullable=True)

    # --- CHANGE BACK TO STANDARD DateTime ---
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    tool: Mapped["Tool"] = relationship("Tool", back_populates="maintenance_history")

    @validates("cost")
    def validate_cost(self, key: str, cost: Optional[float]) -> float:
        if cost is not None and cost < 0: raise ValueError("Cost cannot be negative")
        return cost if cost is not None else 0.0

    def __repr__(self) -> str:
        return f"<ToolMaintenance(id={self.id}, tool_id={self.tool_id}, type='{self.maintenance_type}', status='{self.status}')>"


# --- ToolCheckout Model ---
class ToolCheckout(AbstractBase, ValidationMixin, TimestampMixin):
    __tablename__ = "tool_checkouts"
    __validated_fields__: ClassVar[Set[str]] = {"tool_id", "checked_out_by"}
    id = Column(Integer, primary_key=True, index=True)
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    tool_name = Column(String(255), nullable=True)
    checked_out_by = Column(String(100), nullable=False)
    # --- CHANGE BACK TO STANDARD Date/DateTime ---
    checked_out_date = Column(DateTime, nullable=False)
    due_date = Column(Date, nullable=False)
    returned_date = Column(DateTime, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    project_name = Column(String(255), nullable=True) # Denormalized? Okay if intended.
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="CHECKED_OUT", nullable=False)
    condition_before = Column(String(100), nullable=True)
    condition_after = Column(String(100), nullable=True)
    issue_description = Column(Text, nullable=True)

    # --- CHANGE BACK TO STANDARD DateTime ---
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    tool: Mapped["Tool"] = relationship("Tool", back_populates="checkouts")
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="tool_checkouts")

    # --- Hybrid Properties (No changes needed here) ---
    @hybrid_property
    def is_overdue(self) -> bool:
        if not self.due_date or not isinstance(self.due_date, date) or self.status != "CHECKED_OUT": return False
        return self.due_date < date.today()

    @hybrid_property
    def days_overdue(self) -> Optional[int]:
        if not self.is_overdue: return None
        if not self.due_date or not isinstance(self.due_date, date): return None
        delta = date.today() - self.due_date
        return delta.days

    def __repr__(self) -> str:
        return f"<ToolCheckout(id={self.id}, tool_id={self.tool_id}, by='{self.checked_out_by}', status='{self.status}')>"

# configure_mappers() # Usually not needed explicitly