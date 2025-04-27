# app/db/models/settings.py

"""
Settings database models for HideSync.

This module defines the models for storing and managing application settings:
- SettingsDefinition: Defines available settings and their metadata
- SettingsValue: Stores actual setting values for system, organization or users
- SettingsTemplate: Defines templates that can be applied to users or organizations
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import json

from app.db.models.base import Base, TimestampMixin


class SettingsDefinition(Base, TimestampMixin):
    """
    Definition of available settings in the system.

    Each setting definition describes a configurable aspect of the system,
    including its data type, default value, and applicable scope.
    """
    __tablename__ = "settings_definitions"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    data_type = Column(String(50), nullable=False)  # string, number, boolean, json, enum, etc.
    _default_value = Column("default_value", Text)
    category = Column(String(100))
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
        primaryjoin="SettingsValue.setting_key == SettingsDefinition.key",
        cascade="all, delete-orphan",
        overlaps="definitions"
    )

    # JSON property handling for SQLite
    @property
    def default_value(self):
        if self._default_value:
            return json.loads(self._default_value)
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
            return json.loads(self._validation_rules)
        return {}

    @validation_rules.setter
    def validation_rules(self, value):
        if value is not None:
            self._validation_rules = json.dumps(value)
        else:
            self._validation_rules = None

    def get_display_name(self, locale="en"):
        """Get the localized display name"""
        for translation in self.translations:
            if translation.locale == locale:
                return translation.display_name
        # Fallback to first translation or name
        return self.translations[0].display_name if self.translations else self.name


class SettingsDefinitionTranslation(Base):
    """
    Localized translations for settings definitions.
    """
    __tablename__ = "settings_definition_translations"

    id = Column(Integer, primary_key=True, index=True)
    definition_id = Column(Integer, ForeignKey("settings_definitions.id", ondelete="CASCADE"), nullable=False)
    locale = Column(String(10), nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)

    definition = relationship("SettingsDefinition", back_populates="translations")

    __table_args__ = (
        UniqueConstraint('definition_id', 'locale', name='uq_settings_definition_translation'),
    )


class SettingsValue(Base, TimestampMixin):
    """
    Stores setting values for different scopes.

    A scope can be:
    - System (global)
    - Organization (applies to an organization)
    - User (applies to a specific user)
    """
    __tablename__ = "settings_values"

    # Compound primary key
    scope_type = Column(String(50), primary_key=True)  # "system", "organization", "user"
    scope_id = Column(String(36), primary_key=True)  # ID of the scope entity, or "1" for system
    setting_key = Column(String(100), ForeignKey("settings_definitions.key"), primary_key=True)

    _value = Column("value", Text, nullable=False)  # JSON serialized value

    # Relationships
    definition = relationship(
        "SettingsDefinition",
        foreign_keys=[setting_key],
        primaryjoin="SettingsValue.setting_key == SettingsDefinition.key",
        overlaps="values"
    )

    # JSON property handling for SQLite
    @property
    def value(self):
        if self._value:
            return json.loads(self._value)
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
    _value = Column("value", Text, nullable=False)  # JSON serialized value

    # Relationships
    template = relationship("SettingsTemplate", back_populates="items")
    definition = relationship("SettingsDefinition", foreign_keys=[setting_key])

    # JSON property handling for SQLite
    @property
    def value(self):
        if self._value:
            return json.loads(self._value)
        return None

    @value.setter
    def value(self, value):
        if value is not None:
            self._value = json.dumps(value)
        else:
            self._value = None

    __table_args__ = (
        UniqueConstraint('template_id', 'setting_key', name='uq_template_setting'),
    )