# File: app/db/models/user.py

# Keep necessary imports
from sqlalchemy import Boolean, Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
import datetime

from app.db.models.base import Base, AuditMixin, TimestampMixin

# --- Import the user_role association table from associations.py ---
from app.db.models.associations import user_role


class User(Base, AuditMixin, TimestampMixin):
    """
    User model for authentication and authorization in the HideSync system.

    Stores user account information, credentials, and permission levels.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    customer_communications = relationship(
        "CustomerCommunication", back_populates="staff"
    )  # Assuming CustomerCommunication model exists and has 'staff' relationship
    files = relationship(
        "FileMetadata", back_populates="user", cascade="all, delete-orphan"
    )  # Assuming FileMetadata model exists and has 'user' relationship
    annotations = relationship(
        "Annotation", back_populates="user", cascade="all, delete-orphan"
    )

    # --- Relationship uses the imported user_role table ---
    roles = relationship(
        "Role",
        secondary=user_role,  # Use the imported association table
        back_populates="users",
        lazy="selectin",
    )

    # Add sensitive fields marker for encryption
    SENSITIVE_FIELDS = ["hashed_password"]

    def __repr__(self):
        return f"User(id={self.id}, email={self.email}, username={self.username})"
