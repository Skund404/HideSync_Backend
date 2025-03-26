# File: app/api/endpoints/reports.py
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse

from app.api import deps
from app.schemas.report import (
    ReportRequest,
    ReportResponse,
    ReportTemplate
)
from app.services.report_service import ReportService
from app.schemas.picking_list import PickingListReportResponse

router = APIRouter()


@router.post("/generate", response_model=ReportResponse)
def generate_report(
        request: ReportRequest,
        session: Session = Depends(deps.get_db),
        current_user: dict = Depends(deps.get_current_user)
):
    """
    Generate a custom report based on the specified parameters.
    """
    service = ReportService(session=session)

    try:
        report = service.generate_report(
            report_type=request.report_type,
            parameters=request.parameters,
            format=request.format,
            include_metadata=request.include_metadata
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/templates", response_model=List[ReportTemplate])
def list_report_templates(
        session: Session = Depends(deps.get_db),
        current_user: dict = Depends(deps.get_current_user)
):
    """
    Get available report templates with their parameters.
    """
    service = ReportService(session=session)
    return service.get_available_reports()


@router.get("/{report_id}/download")
def download_report(
        report_id: str,
        session: Session = Depends(deps.get_db),
        current_user: dict = Depends(deps.get_current_user)
):
    """
    Download a previously generated report file.
    """
    service = ReportService(session=session)

    try:
        file_data, filename, content_type = service.download_report(report_id)

        return StreamingResponse(
            iter([file_data]),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
        report_id: str,
        include_data: bool = True,
        session: Session = Depends(deps.get_db),
        current_user: dict = Depends(deps.get_current_user)
):
    """
    Get a previously generated report by ID.
    """
    service = ReportService(session=session)

    try:
        report = service.get_report(report_id, include_data)
        return report
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/recent", response_model=List[Dict[str, Any]])
def get_recent_reports(
        limit: int = 10,
        session: Session = Depends(deps.get_db),
        current_user: dict = Depends(deps.get_current_user)
):
    """
    Get recently generated reports.
    """
    service = ReportService(session=session)
    return service.get_recent_reports(limit)


@router.get("/picking-lists/{picking_list_id}", response_model=PickingListReportResponse)
def generate_picking_list_report(
        picking_list_id: str,
        session: Session = Depends(deps.get_db),
        current_user: dict = Depends(deps.get_current_user)
):
    """
    Generate a comprehensive report for a picking list.

    This endpoint creates a detailed report with statistics about material usage,
    picking progress, and completion status.
    """
    service = ReportService(session=session)

    try:
        # Create a picking list service to generate the report
        from app.services.picking_list_service import PickingListService
        picking_list_service = PickingListService(session=session)

        # Generate the report
        report = picking_list_service.generate_picking_list_report(picking_list_id)

        # Save the report to the reports collection
        report_id = service.save_report(
            report_type="picking_list_report",
            report_data=report,
            parameters={"picking_list_id": picking_list_id},
            format="json"
        )

        return report
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))