# app/services/enum_service.py
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from app.db.models.dynamic_enum import EnumType, EnumTranslation
from sqlalchemy import text


class EnumService:
    def __init__(self, db: Session):
        self.db = db

    def get_enum_types(self) -> List[Dict]:
        """Get all registered enum types"""
        enum_types = self.db.query(EnumType).all()
        return [{"id": et.id, "name": et.name, "system_name": et.system_name} for et in enum_types]

    def get_enum_values(self, enum_type: str, locale: str = "en") -> List[Dict]:
        """Get values for a specific enum type with translations"""
        enum_type_record = self.db.query(EnumType).filter(EnumType.name == enum_type).first()
        if not enum_type_record:
            return []

        # Dynamic SQL to get values from the specific enum table
        sql = f"""
        SELECT ev.id, ev.code, ev.display_order, ev.is_system, ev.parent_id,
               COALESCE(et.display_text, ev.code) as display_text, 
               et.description
        FROM {enum_type_record.table_name} ev
        LEFT JOIN enum_translations et ON 
            et.enum_type = :enum_type AND 
            et.enum_value = ev.code AND 
            et.locale = :locale
        WHERE ev.is_active = TRUE
        ORDER BY ev.display_order, ev.code
        """

        result = self.db.execute(text(sql), {"enum_type": enum_type, "locale": locale})

        return [dict(row) for row in result]

    def get_all_enums(self, locale: str = "en") -> Dict[str, List[Dict]]:
        """Get all enums with their values for a specific locale"""
        enum_types = self.get_enum_types()
        result = {}

        for enum_type in enum_types:
            result[enum_type["system_name"]] = self.get_enum_values(enum_type["name"], locale)

        return result