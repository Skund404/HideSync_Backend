# File: app/api/endpoints/qrcode.py
"""
QR code generation API endpoints for the HideSync system.

This module provides endpoints for generating QR codes for various entities
in the system, including storage locations, inventory items, and purchases.
QR codes can be used for quick scanning in mobile applications or printed
for physical tagging of inventory and storage locations.
"""

from typing import Any, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session
import qrcode
from io import BytesIO
import base64
import json

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.services.storage_location_service import StorageLocationService
from app.services.inventory_service import InventoryService
from app.services.purchase_service import PurchaseService
from app.core.exceptions import EntityNotFoundException

router = APIRouter()


@router.post("/generate")
def generate_qrcode(
        *,
        db: Session = Depends(get_db),
        data: Dict[str, Any],
        size: int = Query(10, ge=1, le=40, description="QR code size (1-40)"),
        format: str = Query("PNG", description="Output format (PNG, SVG, Base64)"),
        current_user=Depends(get_current_active_user)
) -> Response:
    """
    Generate a QR code for arbitrary data.

    Args:
        db: Database session
        data: Data to encode in the QR code
        size: QR code version (size) from 1 to 40
        format: Output format (PNG, SVG, or Base64)
        current_user: Currently authenticated user

    Returns:
        Response with the QR code in the specified format
    """
    try:
        # Convert data to JSON string
        json_data = json.dumps(data)

        # Create QR code
        qr = qrcode.QRCode(
            version=size,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(json_data)
        qr.make(fit=True)

        # Generate image
        img = qr.make_image(fill_color="black", back_color="white")

        # Output in requested format
        buffer = BytesIO()

        if format.upper() == "SVG":
            import qrcode.image.svg
            qr = qrcode.QRCode(
                version=size,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
                image_factory=qrcode.image.svg.SvgImage
            )
            qr.add_data(json_data)
            qr.make(fit=True)
            img = qr.make_image()
            img.save(buffer)
            return Response(content=buffer.getvalue(), media_type="image/svg+xml")

        elif format.upper() == "BASE64":
            img.save(buffer, format="PNG")
            base64_string = base64.b64encode(buffer.getvalue()).decode()
            return Response(content=base64_string, media_type="text/plain")

        else:  # Default to PNG
            img.save(buffer, format="PNG")
            return Response(content=buffer.getvalue(), media_type="image/png")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate QR code: {str(e)}"
        )


@router.get("/storage-location/{location_id}")
def get_storage_location_qrcode(
        *,
        db: Session = Depends(get_db),
        location_id: str = Path(..., description="The ID of the storage location"),
        size: int = Query(10, ge=1, le=40, description="QR code size (1-40)"),
        format: str = Query("PNG", description="Output format (PNG, SVG, Base64)"),
        include_metadata: bool = Query(True, description="Include location metadata in QR code"),
        current_user=Depends(get_current_active_user)
) -> Response:
    """
    Generate a QR code for a storage location.

    Args:
        db: Database session
        location_id: ID of the storage location
        size: QR code version (size) from 1 to 40
        format: Output format (PNG, SVG, or Base64)
        include_metadata: Whether to include metadata in the QR code
        current_user: Currently authenticated user

    Returns:
        Response with the QR code in the specified format
    """
    storage_service = StorageLocationService(db)

    try:
        # Get storage location
        location = storage_service.get_storage_location(location_id)

        # Prepare data for QR code
        if include_metadata:
            qr_data = {
                "type": "storage_location",
                "id": location_id,
                "name": location.name,
                "section": location.section,
                "status": location.status
            }
        else:
            qr_data = {
                "type": "storage_location",
                "id": location_id
            }

        # Convert data to JSON string
        json_data = json.dumps(qr_data)

        # Create QR code
        qr = qrcode.QRCode(
            version=size,
            error_correction=qrcode.constants.ERROR_CORRECT_M,  # Medium error correction for better scanning
            box_size=10,
            border=4,
        )
        qr.add_data(json_data)
        qr.make(fit=True)

        # Generate image
        img = qr.make_image(fill_color="black", back_color="white")

        # Output in requested format
        buffer = BytesIO()

        if format.upper() == "SVG":
            import qrcode.image.svg
            qr = qrcode.QRCode(
                version=size,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
                image_factory=qrcode.image.svg.SvgImage
            )
            qr.add_data(json_data)
            qr.make(fit=True)
            img = qr.make_image()
            img.save(buffer)
            return Response(content=buffer.getvalue(), media_type="image/svg+xml")

        elif format.upper() == "BASE64":
            img.save(buffer, format="PNG")
            base64_string = base64.b64encode(buffer.getvalue()).decode()
            return Response(content=base64_string, media_type="text/plain")

        else:  # Default to PNG
            img.save(buffer, format="PNG")
            return Response(content=buffer.getvalue(), media_type="image/png")

    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage location with ID {location_id} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate QR code: {str(e)}"
        )


@router.get("/purchase/{purchase_id}")
def get_purchase_qrcode(
        *,
        db: Session = Depends(get_db),
        purchase_id: str = Path(..., description="The ID of the purchase"),
        size: int = Query(10, ge=1, le=40, description="QR code size (1-40)"),
        format: str = Query("PNG", description="Output format (PNG, SVG, Base64)"),
        include_metadata: bool = Query(True, description="Include purchase metadata in QR code"),
        current_user=Depends(get_current_active_user)
) -> Response:
    """
    Generate a QR code for a purchase order.

    Args:
        db: Database session
        purchase_id: ID of the purchase
        size: QR code version (size) from 1 to 40
        format: Output format (PNG, SVG, or Base64)
        include_metadata: Whether to include metadata in the QR code
        current_user: Currently authenticated user

    Returns:
        Response with the QR code in the specified format
    """
    purchase_service = PurchaseService(db)

    try:
        # Get purchase
        purchase = purchase_service.get_by_id(purchase_id)

        if not purchase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase with ID {purchase_id} not found"
            )

        # Prepare data for QR code
        if include_metadata:
            qr_data = {
                "type": "purchase",
                "id": purchase_id,
                "supplier_id": purchase.supplier_id,
                "supplier": purchase.supplier if hasattr(purchase, "supplier") else None,
                "status": purchase.status.value if hasattr(purchase.status, "value") else purchase.status,
                "date": purchase.date.isoformat() if hasattr(purchase.date, "isoformat") else purchase.date
            }
        else:
            qr_data = {
                "type": "purchase",
                "id": purchase_id
            }

        # Convert data to JSON string
        json_data = json.dumps(qr_data)

        # Create QR code
        qr = qrcode.QRCode(
            version=size,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(json_data)
        qr.make(fit=True)

        # Generate image
        img = qr.make_image(fill_color="black", back_color="white")

        # Output in requested format
        buffer = BytesIO()

        if format.upper() == "SVG":
            import qrcode.image.svg
            qr = qrcode.QRCode(
                version=size,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
                image_factory=qrcode.image.svg.SvgImage
            )
            qr.add_data(json_data)
            qr.make(fit=True)
            img = qr.make_image()
            img.save(buffer)
            return Response(content=buffer.getvalue(), media_type="image/svg+xml")

        elif format.upper() == "BASE64":
            img.save(buffer, format="PNG")
            base64_string = base64.b64encode(buffer.getvalue()).decode()
            return Response(content=base64_string, media_type="text/plain")

        else:  # Default to PNG
            img.save(buffer, format="PNG")
            return Response(content=buffer.getvalue(), media_type="image/png")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate QR code: {str(e)}"
        )


@router.get("/inventory/{item_id}")
def get_inventory_qrcode(
        *,
        db: Session = Depends(get_db),
        item_id: int = Path(..., description="The ID of the inventory item"),
        item_type: str = Query(..., description="Type of inventory item (material, product, etc.)"),
        size: int = Query(10, ge=1, le=40, description="QR code size (1-40)"),
        format: str = Query("PNG", description="Output format (PNG, SVG, Base64)"),
        include_metadata: bool = Query(True, description="Include inventory metadata in QR code"),
        current_user=Depends(get_current_active_user)
) -> Response:
    """
    Generate a QR code for an inventory item.

    Args:
        db: Database session
        item_id: ID of the inventory item
        item_type: Type of inventory item
        size: QR code version (size) from 1 to 40
        format: Output format (PNG, SVG, or Base64)
        include_metadata: Whether to include metadata in the QR code
        current_user: Currently authenticated user

    Returns:
        Response with the QR code in the specified format
    """
    inventory_service = InventoryService(db)

    try:
        # Get inventory item (implementation depends on your inventory service)
        item = inventory_service.get_item(item_id, item_type)

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inventory item with ID {item_id} and type {item_type} not found"
            )

        # Prepare data for QR code
        if include_metadata and hasattr(item, 'to_dict'):
            item_dict = item.to_dict()
            # Limit the data to essential fields to keep QR code simple
            qr_data = {
                "type": "inventory",
                "id": item_id,
                "item_type": item_type,
                "name": item_dict.get("name", ""),
                "sku": item_dict.get("sku", ""),
                "quantity": item_dict.get("quantity", 0)
            }
        else:
            qr_data = {
                "type": "inventory",
                "id": item_id,
                "item_type": item_type
            }

        # Convert data to JSON string
        json_data = json.dumps(qr_data)

        # Create QR code
        qr = qrcode.QRCode(
            version=size,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(json_data)
        qr.make(fit=True)

        # Generate image
        img = qr.make_image(fill_color="black", back_color="white")

        # Output in requested format
        buffer = BytesIO()

        if format.upper() == "SVG":
            import qrcode.image.svg
            qr = qrcode.QRCode(
                version=size,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
                image_factory=qrcode.image.svg.SvgImage
            )
            qr.add_data(json_data)
            qr.make(fit=True)
            img = qr.make_image()
            img.save(buffer)
            return Response(content=buffer.getvalue(), media_type="image/svg+xml")

        elif format.upper() == "BASE64":
            img.save(buffer, format="PNG")
            base64_string = base64.b64encode(buffer.getvalue()).decode()
            return Response(content=base64_string, media_type="text/plain")

        else:  # Default to PNG
            img.save(buffer, format="PNG")
            return Response(content=buffer.getvalue(), media_type="image/png")

    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item with ID {item_id} and type {item_type} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate QR code: {str(e)}"
        )