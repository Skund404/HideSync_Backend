# File: app/api/endpoints/workflows.py

import logging
from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.workflow import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse, WorkflowListResponse,
    WorkflowExecutionCreate, WorkflowExecutionResponse, WorkflowSearchParams,
    WorkflowImportData, WorkflowExportResponse, WorkflowStatistics,
    WorkflowStepCreate, WorkflowStepUpdate, WorkflowStepResponse,
    WorkflowStepConnectionCreate, WorkflowStepConnectionResponse,
    WorkflowOutcomeCreate, WorkflowOutcomeUpdate, WorkflowOutcomeResponse,
    WorkflowDecisionRequest, WorkflowNavigationRequest, WorkflowStepCompletionRequest,
    WorkflowProgressSummary
)
from app.services.workflow_service import WorkflowService
from app.services.workflow_execution_service import WorkflowExecutionService
from app.services.workflow_import_export_service import WorkflowImportExportService
from app.db.models.user import User
from app.core.exceptions import EntityNotFoundException, ValidationException, BusinessRuleException

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Core Workflow Endpoints ====================

@router.get("/", response_model=WorkflowListResponse)
def list_workflows(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service),
        search: Optional[str] = Query(None, description="Search term for workflow name/description"),
        status: Optional[str] = Query(None, description="Filter by workflow status"),
        is_template: Optional[bool] = Query(None, description="Filter by template status"),
        difficulty_level: Optional[str] = Query(None, description="Filter by difficulty level"),
        project_id: Optional[int] = Query(None, description="Filter by project ID"),
        limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
        offset: int = Query(0, ge=0, description="Number of items to skip"),
        order_by: str = Query("updated_at", description="Field to order by"),
        order_dir: str = Query("desc", regex="^(asc|desc)$", description="Order direction")
) -> Any:
    """
    Retrieve workflows with filtering and pagination.
    """
    try:
        search_params = {
            'search_term': search,
            'status': status,
            'is_template': is_template,
            'difficulty_level': difficulty_level,
            'project_id': project_id,
            'limit': limit,
            'offset': offset,
            'order_by': order_by,
            'order_dir': order_dir
        }

        result = workflow_service.search_workflows(search_params, current_user.id)

        logger.info(f"User {current_user.id} retrieved {len(result['items'])} workflows")

        return WorkflowListResponse(
            items=result['items'],
            total=result['total'],
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Error listing workflows for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving workflows"
        )


@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service),
        workflow_in: WorkflowCreate
) -> Any:
    """
    Create a new workflow.
    """
    try:
        # Convert Pydantic model to dict
        workflow_data = workflow_in.model_dump(exclude_unset=True)

        workflow = workflow_service.create_workflow(workflow_data, current_user.id)

        logger.info(f"User {current_user.id} created workflow {workflow.id}")

        return WorkflowResponse.model_validate(workflow)

    except ValidationException as e:
        logger.warning(f"Validation error creating workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except BusinessRuleException as e:
        logger.warning(f"Business logic error creating workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating workflow"
        )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service),
        workflow_id: int = Path(..., description="ID of the workflow to retrieve")
) -> Any:
    """
    Get a specific workflow by ID.
    """
    try:
        workflow = workflow_service.get_workflow(workflow_id, current_user.id)

        logger.info(f"User {current_user.id} retrieved workflow {workflow_id}")

        return WorkflowResponse.model_validate(workflow)

    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    except BusinessRuleException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving workflow {workflow_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving workflow"
        )


@router.put("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service),
        workflow_id: int = Path(..., description="ID of the workflow to update"),
        workflow_update: WorkflowUpdate
) -> Any:
    """
    Update an existing workflow.
    """
    try:
        update_data = workflow_update.model_dump(exclude_unset=True)

        workflow = workflow_service.update_workflow(workflow_id, update_data, current_user.id)

        logger.info(f"User {current_user.id} updated workflow {workflow_id}")

        return WorkflowResponse.model_validate(workflow)

    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except BusinessRuleException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating workflow {workflow_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating workflow"
        )


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service),
        workflow_id: int = Path(..., description="ID of the workflow to delete")
) -> Any:
    """
    Delete a workflow.
    """
    try:
        workflow_service.delete_workflow(workflow_id, current_user.id)

        logger.info(f"User {current_user.id} deleted workflow {workflow_id}")

        return None

    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    except BusinessRuleException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting workflow {workflow_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting workflow"
        )


@router.post("/{workflow_id}/duplicate", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def duplicate_workflow(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service),
        workflow_id: int = Path(..., description="ID of the workflow to duplicate"),
        new_name: str = Body(..., description="Name for the duplicated workflow"),
        as_template: bool = Body(False, description="Whether to create as template")
) -> Any:
    """
    Create a duplicate of an existing workflow.
    """
    try:
        duplicate = workflow_service.duplicate_workflow(
            workflow_id, new_name, current_user.id, as_template
        )

        logger.info(f"User {current_user.id} duplicated workflow {workflow_id} as {duplicate.id}")

        return WorkflowResponse.model_validate(duplicate)

    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    except BusinessRuleException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error duplicating workflow {workflow_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error duplicating workflow"
        )


# ==================== Template Endpoints ====================

@router.get("/templates/", response_model=List[WorkflowResponse])
def get_workflow_templates(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service)
) -> Any:
    """
    Get all available workflow templates.
    """
    try:
        templates = workflow_service.get_workflow_templates(current_user.id)

        logger.info(f"User {current_user.id} retrieved {len(templates)} workflow templates")

        return [WorkflowResponse.model_validate(template) for template in templates]

    except Exception as e:
        logger.error(f"Error retrieving workflow templates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving workflow templates"
        )


@router.post("/{workflow_id}/publish", response_model=WorkflowResponse)
def publish_as_template(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service),
        workflow_id: int = Path(..., description="ID of the workflow to publish"),
        visibility: str = Body("public", regex="^(public|private)$", description="Template visibility")
) -> Any:
    """
    Publish a workflow as a template.
    """
    try:
        template = workflow_service.publish_as_template(workflow_id, current_user.id, visibility)

        logger.info(f"User {current_user.id} published workflow {workflow_id} as template")

        return WorkflowResponse.model_validate(template)

    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except BusinessRuleException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error publishing workflow {workflow_id} as template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error publishing workflow as template"
        )


# ==================== Execution Endpoints ====================

@router.post("/{workflow_id}/start", response_model=WorkflowExecutionResponse, status_code=status.HTTP_201_CREATED)
def start_workflow_execution(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service),
        workflow_id: int = Path(..., description="ID of the workflow to start"),
        execution_data: WorkflowExecutionCreate = Body(...)
) -> Any:
    """
    Start a new workflow execution.
    """
    try:
        execution = workflow_service.start_workflow_execution(
            workflow_id=workflow_id,
            user_id=current_user.id,
            selected_outcome_id=execution_data.selected_outcome_id
        )

        logger.info(f"User {current_user.id} started execution {execution.id} for workflow {workflow_id}")

        return WorkflowExecutionResponse.model_validate(execution)

    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except BusinessRuleException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error starting workflow execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error starting workflow execution"
        )


@router.get("/executions/active", response_model=List[WorkflowExecutionResponse])
def get_active_executions(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service)
) -> Any:
    """
    Get user's active workflow executions.
    """
    try:
        # This would use WorkflowExecutionService when implemented
        # For now, using a placeholder
        executions = []  # workflow_service.get_active_executions(current_user.id)

        logger.info(f"User {current_user.id} retrieved {len(executions)} active executions")

        return [WorkflowExecutionResponse.model_validate(execution) for execution in executions]

    except Exception as e:
        logger.error(f"Error retrieving active executions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving active executions"
        )


# ==================== Statistics Endpoints ====================

@router.get("/{workflow_id}/statistics", response_model=WorkflowStatistics)
def get_workflow_statistics(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service),
        workflow_id: int = Path(..., description="ID of the workflow")
) -> Any:
    """
    Get comprehensive statistics for a workflow.
    """
    try:
        stats = workflow_service.get_workflow_statistics(workflow_id, current_user.id)

        logger.info(f"User {current_user.id} retrieved statistics for workflow {workflow_id}")

        return WorkflowStatistics(**stats)

    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    except BusinessRuleException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving workflow statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving workflow statistics"
        )


# ==================== Import/Export Endpoints (Admin Only) ====================

@router.post("/import", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def import_workflow(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_superuser),  # Superuser required
        import_export_service: WorkflowImportExportService = Depends(deps.get_workflow_import_export_service),
        import_data: WorkflowImportData = Body(...)
) -> Any:
    """
    Import a workflow from JSON data.
    Requires superuser privileges.
    """
    try:
        workflow = import_export_service.import_workflow(
            import_data.model_dump(), current_user.id
        )

        logger.info(f"Superuser {current_user.id} imported workflow {workflow.id}")

        return WorkflowResponse.model_validate(workflow)

    except ValidationException as e:
        logger.warning(f"Validation error importing workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import validation failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error importing workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error importing workflow"
        )


@router.get("/{workflow_id}/export", response_model=WorkflowExportResponse)
def export_workflow(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_superuser),  # Superuser required
        import_export_service: WorkflowImportExportService = Depends(deps.get_workflow_import_export_service),
        workflow_id: int = Path(..., description="ID of the workflow to export")
) -> Any:
    """
    Export a workflow as JSON data.
    Requires superuser privileges.
    """
    try:
        export_data = import_export_service.export_workflow(workflow_id)

        logger.info(f"Superuser {current_user.id} exported workflow {workflow_id}")

        return WorkflowExportResponse(**export_data)

    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    except Exception as e:
        logger.error(f"Error exporting workflow {workflow_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error exporting workflow"
        )


# ==================== Step Management Endpoints ====================

@router.get("/{workflow_id}/steps", response_model=List[WorkflowStepResponse])
def get_workflow_steps(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service),
        workflow_id: int = Path(..., description="ID of the workflow")
) -> Any:
    """
    Get all steps for a workflow.
    """
    try:
        workflow = workflow_service.get_workflow(workflow_id, current_user.id)

        logger.info(f"User {current_user.id} retrieved {len(workflow.steps)} steps for workflow {workflow_id}")

        return [WorkflowStepResponse.model_validate(step) for step in workflow.steps]

    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    except BusinessRuleException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving workflow steps: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving workflow steps"
        )


# ==================== Health Check Endpoint ====================

@router.get("/health", status_code=status.HTTP_200_OK)
def workflow_health_check() -> Dict[str, Any]:
    """
    Health check endpoint for workflow system.
    """
    return {
        "status": "healthy",
        "service": "workflow_management",
        "timestamp": datetime.now().isoformat()
    }


# ==================== Bulk Operations ====================

@router.delete("/bulk", status_code=status.HTTP_204_NO_CONTENT)
def bulk_delete_workflows(
        *,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_active_user),
        workflow_service: WorkflowService = Depends(deps.get_workflow_service),
        workflow_ids: List[int] = Body(..., description="List of workflow IDs to delete")
) -> Any:
    """
    Bulk delete multiple workflows.
    """
    try:
        deleted_count = 0
        errors = []

        for workflow_id in workflow_ids:
            try:
                workflow_service.delete_workflow(workflow_id, current_user.id)
                deleted_count += 1
            except Exception as e:
                errors.append(f"Workflow {workflow_id}: {str(e)}")

        logger.info(f"User {current_user.id} bulk deleted {deleted_count} workflows")

        if errors:
            return JSONResponse(
                status_code=status.HTTP_207_MULTI_STATUS,
                content={
                    "deleted_count": deleted_count,
                    "errors": errors
                }
            )

        return None

    except Exception as e:
        logger.error(f"Error in bulk delete: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error performing bulk delete"
        )