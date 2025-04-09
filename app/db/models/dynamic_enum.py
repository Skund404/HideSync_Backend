# app/db/models/dynamic_enum.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.models.base import Base

class EnumType(Base):
    __tablename__ = "enum_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255))
    table_name = Column(String(100), unique=True, nullable=False)
    system_name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class EnumTranslation(Base):
    __tablename__ = "enum_translations"

    id = Column(Integer, primary_key=True, index=True)
    enum_type = Column(String(100), nullable=False)
    enum_value = Column(String(100), nullable=False)
    locale = Column(String(10), nullable=False)
    display_text = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('enum_type', 'enum_value', 'locale', name='uq_enum_translation'),
    )