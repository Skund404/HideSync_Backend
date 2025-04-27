# app/repositories/material_type_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_

from app.db.models.dynamic_material import (
    MaterialType, MaterialTypeTranslation, MaterialTypeProperty,
    PropertyDefinition, PropertyDefinitionTranslation, PropertyEnumOption
)
from app.repositories.base_repository import BaseRepository


class MaterialTypeRepository(BaseRepository[MaterialType]):
    """
    Repository for MaterialType entity operations.
    """

    def __init__(self, session: Session, encryption_service=None):
        super().__init__(session, encryption_service)
        self.model = MaterialType

    def list_with_properties(self, skip: int = 0, limit: int = 100, **filters) -> List[MaterialType]:
        """
        List material types with their properties, with pagination and filtering.
        """
        query = self.session.query(self.model)

        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)

        # Apply eager loading of related entities
        query = query.options(
            joinedload(self.model.properties),
            joinedload(self.model.translations)
        )

        # Apply pagination
        result = query.offset(skip).limit(limit).all()

        return [self._decrypt_sensitive_fields(item) for item in result]

    def get_by_id_with_properties(self, id: int) -> Optional[MaterialType]:
        """
        Get a material type by ID with eager loading of related properties.
        """
        item = self.session.query(self.model).filter(
            self.model.id == id
        ).options(
            joinedload(self.model.properties),
            joinedload(self.model.translations)
        ).first()

        return self._decrypt_sensitive_fields(item) if item else None

    def create_with_properties(self, data: Dict[str, Any]) -> MaterialType:
        """
        Create a material type with translations and property assignments.
        """
        # Extract nested data
        translations_data = data.pop('translations', {})
        properties_data = data.pop('properties', [])

        # Create the material type
        material_type = self.model(**data)
        self.session.add(material_type)
        self.session.flush()  # Get the ID

        # Create translations
        for locale, translation_data in translations_data.items():
            translation = MaterialTypeTranslation(
                material_type_id=material_type.id,
                locale=locale,
                display_name=translation_data.get("display_name"),
                description=translation_data.get("description")
            )
            self.session.add(translation)

        # Assign properties
        for idx, prop_data in enumerate(properties_data):
            material_type_property = MaterialTypeProperty(
                material_type_id=material_type.id,
                property_id=prop_data.get("property_id"),
                display_order=prop_data.get("display_order", idx),
                is_required=prop_data.get("is_required", False),
                is_filterable=prop_data.get("is_filterable", True),
                is_displayed_in_list=prop_data.get("is_displayed_in_list", True),
                is_displayed_in_card=prop_data.get("is_displayed_in_card", True),
                default_value=prop_data.get("default_value")
            )
            self.session.add(material_type_property)

        self.session.commit()
        self.session.refresh(material_type)

        return material_type

    def update_with_properties(self, id: int, data: Dict[str, Any]) -> Optional[MaterialType]:
        """
        Update a material type with translations and property assignments.
        """
        material_type = self.get_by_id(id)
        if not material_type:
            return None

        # Extract nested data
        translations_data = data.pop('translations', {})
        properties_data = data.pop('properties', None)

        # Update base fields
        for key, value in data.items():
            if hasattr(material_type, key):
                setattr(material_type, key, value)

        # Update translations
        if translations_data:
            # Get existing translations
            existing_translations = {
                t.locale: t for t in material_type.translations
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
                    translation = MaterialTypeTranslation(
                        material_type_id=material_type.id,
                        locale=locale,
                        display_name=translation_data.get("display_name"),
                        description=translation_data.get("description")
                    )
                    self.session.add(translation)

        # Update properties if provided
        if properties_data is not None:
            # Remove existing property assignments
            self.session.query(MaterialTypeProperty).filter(
                MaterialTypeProperty.material_type_id == material_type.id
            ).delete()

            # Create new property assignments
            for idx, prop_data in enumerate(properties_data):
                material_type_property = MaterialTypeProperty(
                    material_type_id=material_type.id,
                    property_id=prop_data.get("property_id"),
                    display_order=prop_data.get("display_order", idx),
                    is_required=prop_data.get("is_required", False),
                    is_filterable=prop_data.get("is_filterable", True),
                    is_displayed_in_list=prop_data.get("is_displayed_in_list", True),
                    is_displayed_in_card=prop_data.get("is_displayed_in_card", True),
                    default_value=prop_data.get("default_value")
                )
                self.session.add(material_type_property)

        self.session.commit()
        self.session.refresh(material_type)

        return material_type

    def convert_to_export_format(self, material_type: MaterialType) -> Dict[str, Any]:
        """
        Convert a material type to export format.
        """
        # Create base export data
        export_data = {
            "name": material_type.name,
            "icon": material_type.icon,
            "color_scheme": material_type.color_scheme,
            "ui_config": material_type.ui_config,
            "storage_config": material_type.storage_config,
            "visibility_level": material_type.visibility_level,
            "translations": {},
            "properties": []
        }

        # Add translations
        for translation in material_type.translations:
            export_data["translations"][translation.locale] = {
                "display_name": translation.display_name,
                "description": translation.description
            }

        # Add properties
        property_assignments = self.session.query(MaterialTypeProperty).filter(
            MaterialTypeProperty.material_type_id == material_type.id
        ).all()

        for assignment in property_assignments:
            export_data["properties"].append({
                "property_id": assignment.property_id,
                "display_order": assignment.display_order,
                "is_required": assignment.is_required,
                "is_filterable": assignment.is_filterable,
                "is_displayed_in_list": assignment.is_displayed_in_list,
                "is_displayed_in_card": assignment.is_displayed_in_card,
                "default_value": assignment.default_value
            })

        return export_data

    def convert_from_export_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert an export format to a create format.
        """
        return {
            "name": data.get("name"),
            "icon": data.get("icon"),
            "color_scheme": data.get("color_scheme"),
            "ui_config": data.get("ui_config"),
            "storage_config": data.get("storage_config"),
            "visibility_level": data.get("visibility_level", "all"),
            "translations": data.get("translations", {}),
            "properties": data.get("properties", [])
        }