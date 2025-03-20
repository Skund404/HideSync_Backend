# File: db/models/supplier_history.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.models.base import AbstractBase, TimestampMixin, ValidationMixin


class SupplierHistory(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Model for tracking supplier status history changes.

    This model records each status change for suppliers, including
    the previous and new status, reason for the change, and the user
    who made the change.
    """

    __tablename__ = "supplier_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("supplier.id"), nullable=False, index=True)
    previous_status = Column(String(50), nullable=False)
    new_status = Column(String(50), nullable=False)
    reason = Column(Text, nullable=True)
    changed_by = Column(Integer, nullable=True)  # User ID who made the change
    change_date = Column(DateTime, default=datetime.now, nullable=False, index=True)

    # Relationship
    supplier = relationship("Supplier", back_populates="status_history")
