# File: app/db/seed_db.py
"""
Database seeding functionality for HideSync.

This module provides functions for populating the database with initial
or sample data for development and testing purposes.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.db.session import SessionLocal
from app.db.models import (
    Customer, Supplier, Material, LeatherMaterial, HardwareMaterial, SuppliesMaterial,
    Tool, StorageLocation, Pattern, Project, ProjectComponent, Sale, SaleItem,
    Purchase, PurchaseItem, TimelineTask, StorageCell, StorageAssignment, ProjectTemplate,
    DocumentationCategory, DocumentationResource, PickingList, PickingListItem,
    ToolMaintenance, ToolCheckout
)

logger = logging.getLogger(__name__)


def seed_database(seed_data: Dict[str, Any]) -> None:
    """
    Seed the database with initial data.

    Args:
        seed_data: Dictionary containing seed data for various entities
    """
    # Create a database session using the configured session factory
    # This will use the encryption key already configured in session.py
    session = SessionLocal()

    try:
        # Process the seed data in a specific order to respect foreign key constraints
        entities_order = [
            "documentation_categories",
            "documentation_resources",
            "suppliers",
            "customers",
            "storage_locations",
            "storage_cells",
            "materials",
            "tools",
            "tool_maintenance",
            "patterns",
            "project_templates",
            "projects",
            "project_components",
            "timeline_tasks",
            "sales",
            "sale_items",
            "purchases",
            "purchase_items",
            "picking_lists",
            "picking_list_items",
            "storage_assignments",
            "tool_checkouts"
        ]

        # Dictionary to store created entity IDs for reference
        entity_ids = {}

        for entity_type in entities_order:
            if entity_type in seed_data:
                seed_entity(session, entity_type, seed_data[entity_type], entity_ids)

        # Commit all changes at once
        session.commit()
        logger.info("Database seeding completed successfully")

    except Exception as e:
        session.rollback()
        logger.error(f"Error seeding database: {str(e)}")
        raise
    finally:
        session.close()


def seed_entity(session, entity_type: str, entities_data: List[Dict[str, Any]],
                entity_ids: Dict[str, Dict[int, int]]) -> None:
    """
    Seed a specific entity type.

    Args:
        session: SQLAlchemy database session
        entity_type: Type of entity to seed
        entities_data: List of entity data dictionaries
        entity_ids: Dictionary to store created entity IDs
    """
    logger.info(f"Seeding {entity_type}...")

    # Get the appropriate model based on entity type
    model_map = {
        "documentation_categories": DocumentationCategory,
        "documentation_resources": DocumentationResource,
        "customers": Customer,
        "suppliers": Supplier,
        "materials": Material,  # Will handle subtypes separately
        "tools": Tool,
        "tool_maintenance": ToolMaintenance,
        "tool_checkouts": ToolCheckout,
        "storage_locations": StorageLocation,
        "storage_cells": StorageCell,
        "storage_assignments": StorageAssignment,
        "patterns": Pattern,
        "project_templates": ProjectTemplate,
        "projects": Project,
        "project_components": ProjectComponent,
        "timeline_tasks": TimelineTask,
        "sales": Sale,
        "sale_items": SaleItem,
        "purchases": Purchase,
        "purchase_items": PurchaseItem,
        "picking_lists": PickingList,
        "picking_list_items": PickingListItem,
    }

    if entity_type not in model_map:
        logger.warning(f"Unknown entity type: {entity_type}")
        return

    model = model_map[entity_type]
    entity_ids[entity_type] = {}

    # Special handling for materials and related types
    if entity_type == "materials":
        seed_materials(session, entities_data, entity_ids)
    else:
        # Standard entity creation
        for idx, item_data in enumerate(entities_data, 1):
            try:
                # Create a copy of the data to avoid modifying the original
                data = item_data.copy()

                # Handle dates and timestamps
                for key, value in item_data.items():
                    if isinstance(value, str) and (
                            key.endswith('Date') or key.endswith('At') or key == 'timestamp'
                    ):
                        try:
                            data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        except ValueError:
                            # If date parsing fails, keep as string
                            pass

                # Handle foreign key references
                data = resolve_foreign_keys(data, entity_ids)

                # Create and add the entity
                entity = model(**data)
                session.add(entity)
                session.flush()  # Flush to get the ID without committing

                # Store the created entity's ID
                entity_ids[entity_type][idx] = entity.id

            except Exception as e:
                logger.error(f"Error creating {entity_type} entity (index {idx}): {str(e)}")
                raise


def seed_materials(session, materials_data: List[Dict[str, Any]],
                   entity_ids: Dict[str, Dict[int, int]]) -> None:
    """
    Seed materials with appropriate handling for material types.

    Args:
        session: SQLAlchemy database session
        materials_data: List of material data dictionaries
        entity_ids: Dictionary to store created entity IDs
    """
    entity_ids["materials"] = {}

    for idx, material_data in enumerate(materials_data, 1):
        try:
            # Create a copy of the data to avoid modifying the original
            data = material_data.copy()

            # Handle foreign key references
            data = resolve_foreign_keys(data, entity_ids)

            # Determine material type and create the appropriate entity
            material_type = data.pop("materialType", "LEATHER")

            if material_type == "LEATHER":
                entity = LeatherMaterial(**data)
            elif material_type == "HARDWARE":
                entity = HardwareMaterial(**data)
            elif material_type == "SUPPLIES":
                entity = SuppliesMaterial(**data)
            else:
                # Default to base Material class
                entity = Material(**data)

            session.add(entity)
            session.flush()

            # Store the created entity's ID
            entity_ids["materials"][idx] = entity.id

        except Exception as e:
            logger.error(f"Error creating material entity (index {idx}): {str(e)}")
            raise


def resolve_foreign_keys(data: Dict[str, Any], entity_ids: Dict[str, Dict[int, int]]) -> Dict[str, Any]:
    """
    Resolve foreign key references in seed data.

    Args:
        data: Entity data dictionary
        entity_ids: Dictionary of created entity IDs

    Returns:
        Updated entity data with resolved foreign keys
    """
    # Create a copy to avoid modifying the original
    result = data.copy()

    # Define foreign key mappings (field name -> entity type)
    fk_mappings = {
        'supplierId': 'suppliers',
        'customerId': 'customers',
        'materialId': 'materials',
        'storageId': 'storage_locations',
        'patternId': 'patterns',
        'projectId': 'projects',
        'project_id': 'projects',
        'templateId': 'project_templates',
        'saleId': 'sales',
        'sale_id': 'sales',
        'purchaseId': 'purchases',
        'purchase_id': 'purchases',
        'toolId': 'tools',
        'picking_list_id': 'picking_lists',
        'component_id': 'components',
        'fromStorageId': 'storage_locations',
        'toStorageId': 'storage_locations',
        'categoryId': 'documentation_categories'
    }

    # Replace seed indices with actual database IDs
    for field, entity_type in fk_mappings.items():
        if field in result and isinstance(result[field], int) and entity_type in entity_ids:
            seed_index = result[field]
            if seed_index in entity_ids[entity_type]:
                result[field] = entity_ids[entity_type][seed_index]

    return result