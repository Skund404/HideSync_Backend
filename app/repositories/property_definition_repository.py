# app/repositories/property_definition_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func

from app.db.models.dynamic_material import (
    PropertyDefinition, PropertyDefinitionTranslation, PropertyEnumOption
)
from app.repositories.base_repository import BaseRepository


class PropertyDefinitionRepository(BaseRepository[PropertyDefinition]):
    """
    Repository for PropertyDefinition entity operations.
    """

    def __init__(self, session: Session, encryption_service=None):
        super().__init__(session, encryption_service)
        self.model = PropertyDefinition

    def list_with_translations(self, skip: int = 0, limit: int = 100, **filters) -> List[PropertyDefinition]:
        """
        List property definitions with their translations, with pagination and filtering.
        """
        query = self.session.query(self.model)

        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)

        # Apply eager loading of related entities
        query = query.options(
            joinedload(self.model.translations),
            joinedload(self.model.enum_options)
        )

        # Apply pagination
        result = query.offset(skip).limit(limit).all()

        return [self._decrypt_sensitive_fields(item) for item in result]

    def get_by_id_with_translations(self, id: int) -> Optional[PropertyDefinition]:
        """
        Get a property definition by ID with eager loading of related translations.
        """
        item = self.session.query(self.model).filter(
            self.model.id == id
        ).options(
            joinedload(self.model.translations),
            joinedload(self.model.enum_options)
        ).first()

        return self._decrypt_sensitive_fields(item) if item else None

    def create_with_translations(self, data: Dict[str, Any]) -> PropertyDefinition:
        """
        Create a property definition with translations and enum options.
        """
        # Extract nested data
        translations_data = data.pop('translations', {})
        enum_options_data = data.pop('enum_options', [])

        # Create the property definition
        property_def = self.model(**data)
        self.session.add(property_def)
        self.session.flush()  # Get the ID

        # Create translations
        for locale, translation_data in translations_data.items():
            translation = PropertyDefinitionTranslation(
                property_id=property_def.id,
                locale=locale,
                display_name=translation_data.get("display_name"),
                description=translation_data.get("description")
            )
            self.session.add(translation)

        # Create enum options if applicable
        if enum_options_data and property_def.data_type == 'enum' and not property_def.enum_type_id:
            for idx, option_data in enumerate(enum_options_data):
                enum_option = PropertyEnumOption(
                    property_id=property_def.id,
                    value=option_data.get("value"),
                    display_value=option_data.get("display_value"),
                    color=option_data.get("color"),
                    display_order=option_data.get("display_order", idx)
                )
                self.session.add(enum_option)

        self.session.commit()
        self.session.refresh(property_def)

        return property_def

    def update_with_translations(self, id: int, data: Dict[str, Any]) -> Optional[PropertyDefinition]:
        """
        Update a property definition with translations and enum options.
        """
        property_def = self.get_by_id(id)
        if not property_def:
            return None

        # Extract nested data
        translations_data = data.pop('translations', {})
        enum_options_data = data.pop('enum_options', None)

        # Update base fields
        for key, value in data.items():
            if hasattr(property_def, key):
                setattr(property_def, key, value)

        # Update translations
        if translations_data:
            # Get existing translations
            existing_translations = {
                t.locale: t for t in property_def.translations
            }

            # Update or create translations
            for locale, translation_data in translations_data.items():
                if locale in existing_translations:
                    # Update existing
                    translation = existing_translations[locale]
                    translation.display_name = translation_data.get("display_name", translation.display_name)
                    translation.description = translation_data.get("description", translation.description)
                else:
                    # Create new
                    translation = PropertyDefinitionTranslation(
                        property_id=property_def.id,
                        locale=locale,
                        display_name=translation_data.get("display_name"),
                        description=translation_data.get("description")
                    )
                    self.session.add(translation)

        # Update enum options if provided
        if enum_options_data is not None and property_def.data_type == 'enum' and not property_def.enum_type_id:
            # Remove existing enum options
            self.session.query(PropertyEnumOption).filter(
                PropertyEnumOption.property_id == property_def.id
            ).delete()

            # Create new enum options
            for idx, option_data in enumerate(enum_options_data):
                enum_option = PropertyEnumOption(
                    property_id=property_def.id,
                    value=option_data.get("value"),
                    display_value=option_data.get("display_value"),
                    color=option_data.get("color"),
                    display_order=option_data.get("display_order", idx)
                )
                self.session.add(enum_option)

        self.session.commit()
        self.session.refresh(property_def)

        return property_def

    def add_enum_option(self, property_id: int, value: str, display_value: str, color: Optional[str] = None,
                        display_order: Optional[int] = None) -> PropertyEnumOption:
        """
        Add an enum option to a property.
        """
        property_def = self.get_by_id(property_id)
        if not property_def or property_def.data_type != 'enum' or property_def.enum_type_id:
            return None

        # Get highest display order if not provided
        if display_order is None:
            max_order = self.session.query(func.max(PropertyEnumOption.display_order)).filter(
                PropertyEnumOption.property_id == property_id
            ).scalar() or -1
            display_order = max_order + 1

        # Create new enum option
        enum_option = PropertyEnumOption(
            property_id=property_id,
            value=value,
            display_value=display_value,
            color=color,
            display_order=display_order
        )
        self.session.add(enum_option)
        self.session.commit()
        self.session.refresh(enum_option)

        return enum_option