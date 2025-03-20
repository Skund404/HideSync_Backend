# File: db/models/supplier_rating.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.models.base import AbstractBase, TimestampMixin, ValidationMixin


class SupplierRating(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Model for tracking supplier rating history changes.

    This model records each rating change for suppliers, including
    the previous and new rating values, optional comments explaining
    the rating, and the user who made the rating change.
    """

    __tablename__ = "supplier_rating"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("supplier.id"), nullable=False, index=True)
    previous_rating = Column(Integer, nullable=False)
    new_rating = Column(Integer, nullable=False)
    comments = Column(Text, nullable=True)
    rated_by = Column(Integer, nullable=True)  # User ID who rated
    rating_date = Column(DateTime, default=datetime.now, nullable=False, index=True)

    # Relationship
    supplier = relationship("Supplier", back_populates="rating_history")
