# app/db/models/settings.py
"""
Settings system for HideSync.

This module defines the models for storing application, organization,
and user settings, as well as setting templates.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import json

from app.db.models.base import Base, TimestampMixin


class SettingsDefinition(Base, TimestampMixin):
    """
    Definition of configurable settings available in the system.
    """
    __tablename__ = "settings_definitions"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    data_type = Column(String(50), nullable=False)  # string, number, boolean, json, etc.
    _default_value = Column("default_value", Text)
    category = Column(String(100))  # e.g., 'ui', 'system', 'materials'
    subcategory = Column(String(100))
    applies_to = Column(String(50))  # system, organization, user
    tier_availability = Column(String(100))  # comma-separated tiers or 'all'
    is_hidden = Column(Boolean, default=False)
    ui_component = Column(String(100))  # text, toggle, select, color-picker, etc.
    _validation_rules = Column("validation_rules", Text)

    # Relationships
    translations = relationship(
        "SettingsDefinitionTranslation",
        back_populates="definition",
        cascade="all, delete-orphan"
    )
    values = relationship(
        "SettingsValue",
        primaryjoin="SettingsValue.setting_key==SettingsDefinition.key",
        foreign_keys="SettingsValue.setting_key",
        backref="definition",
        cascade="all, delete-orphan",
        overlaps="definitions"
    )

    # JSON property handlers
    @property
    def default_value(self):
        if self._default_value:
            try:
                return json.loads(self._default_value)
            except:
                return None
        return None

    @default_value.setter
    def default_value(self, value):
        if value is not None:
            self._default_value = json.dumps(value)
        else:
            self._default_value = None

    @property
    def validation_rules(self):
        if self._validation_rules:
            try:
                return json.loads(self._validation_rules)
            except:
                return {}
        return {}

    @validation_rules.setter
    def validation_rules(self, value):
        if value is not None:
            self._validation_rules = json.dumps(value)
        else:
            self._validation_rules = None


class SettingsDefinitionTranslation(Base):
    """
    Translations for settings definitions.
    """
    __tablename__ = "settings_definition_translations"

    id = Column(Integer, primary_key=True, index=True)
    definition_id = Column(Integer, ForeignKey("settings_definitions.id", ondelete="CASCADE"), nullable=False)
    locale = Column(String(10), nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)

    # Relationships
    definition = relationship("SettingsDefinition", back_populates="translations")

    # Constraints
    __table_args__ = (
        UniqueConstraint('definition_id', 'locale', name='uq_settings_definition_translation'),
    )


class SettingsValue(Base, TimestampMixin):
    """
    Stores setting values for different scopes.
    """
    __tablename__ = "settings_values"

    # Composite primary key
    scope_type = Column(String(50), primary_key=True)  # "system", "organization", "user"
    scope_id = Column(String(36), primary_key=True)  # ID of the scope entity
    setting_key = Column(String(100), ForeignKey("settings_definitions.key"), primary_key=True)
    _value = Column("value", Text, nullable=False)

    # JSON property handlers
    @property
    def value(self):
        if self._value:
            try:
                return json.loads(self._value)
            except:
                return None
        return None

    @value.setter
    def value(self, value):
        if value is not None:
            self._value = json.dumps(value)
        else:
            self._value = None


class SettingsTemplate(Base, TimestampMixin):
    """
    Predefined templates of settings that can be applied to users or organizations.
    """
    __tablename__ = "settings_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    applies_to = Column(String(50))  # "user", "organization"
    tier_availability = Column(String(100))  # comma-separated tiers or 'all'
    is_system = Column(Boolean, default=False)

    # Relationships
    items = relationship(
        "SettingsTemplateItem",
        back_populates="template",
        cascade="all, delete-orphan"
    )


class SettingsTemplateItem(Base):
    """
    Individual settings within a template.
    """
    __tablename__ = "settings_template_items"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("settings_templates.id", ondelete="CASCADE"), nullable=False)
    setting_key = Column(String(100), ForeignKey("settings_definitions.key"), nullable=False)
    _value = Column("value", Text, nullable=False)

    # Relationships
    template = relationship("SettingsTemplate", back_populates="items")
    definition = relationship("SettingsDefinition")

    # JSON property handlers
    @property
    def value(self):
        if self._value:
            try:
                return json.loads(self._value)
            except:
                return None
        return None

    @value.setter
    def value(self, value):
        if value is not None:
            self._value = json.dumps(value)
        else:
            self._value = None

    # Constraints
    __table_args__ = (
        UniqueConstraint('template_id', 'setting_key', name='uq_template_setting'),
    )