# app/api/endpoints/enums.py
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user
from app.services.enum_service import EnumService

router = APIRouter()

@router.get("/")
def get_all_enums(
    locale: str = Query("en", description="Locale code for translations"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
) -> Dict[str, List[Dict]]:
    """Get all enum values with translations for the specified locale"""
    enum_service = EnumService(db)
    return enum_service.get_all_enums(locale)

@router.get("/{enum_type}")
def get_enum_values(
    enum_type: str,
    locale: str = Query("en", description="Locale code for translations"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
) -> List[Dict]:
    """Get values for a specific enum type with translations"""
    enum_service = EnumService(db)
    return enum_service.get_enum_values(enum_type, locale)