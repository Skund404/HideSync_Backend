# app/db/models/preset.py

from sqlalchemy import (
    Column, String, Integer, Boolean, Text, ForeignKey, DateTime,
    UniqueConstraint, Table
)
from sqlalchemy.orm import relationship
from datetime import datetime
import json

from app.db.models.base import Base, TimestampMixin


class MaterialPreset(Base, TimestampMixin):
    """
    Stores material presets for sharing configurations.
    """
    __tablename__ = "material_presets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    author = Column(String(255))
    is_public = Column(Boolean, default=False)
    _config = Column("config", Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    applications = relationship(
        "PresetApplication",
        back_populates="preset",
        cascade="all, delete-orphan"
    )

    # JSON property handlers
    @property
    def config(self):
        if self._config:
            try:
                return json.loads(self._config)
            except:
                return {}
        return {}

    @config.setter
    def config(self, value):
        if value is not None:
            self._config = json.dumps(value)
        else:
            self._config = None


class PresetApplication(Base):
    """
    Records the application of a preset by a user.
    """
    __tablename__ = "preset_applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    preset_id = Column(Integer, ForeignKey("material_presets.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    _options_used = Column("options_used", Text)
    created_property_definitions = Column(Integer, default=0)
    updated_property_definitions = Column(Integer, default=0)
    created_material_types = Column(Integer, default=0)
    updated_material_types = Column(Integer, default=0)
    created_materials = Column(Integer, default=0)
    error_count = Column(Integer, default=0)

    # Relationships
    preset = relationship("MaterialPreset", back_populates="applications")

    # JSON property handlers
    @property
    def options_used(self):
        if self._options_used:
            try:
                return json.loads(self._options_used)
            except:
                return {}
        return {}

    @options_used.setter
    def options_used(self, value):
        if value is not None:
            self._options_used = json.dumps(value)
        else:
            self._options_used = None


class PresetApplicationError(Base):
    """
    Records errors that occurred during preset application.
    """
    __tablename__ = "preset_application_errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("preset_applications.id", ondelete="CASCADE"), nullable=False)
    error_type = Column(String(50), nullable=False)
    entity_type = Column(String(50))
    entity_name = Column(String(255))
    error_message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)