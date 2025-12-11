"""Audit log and monitoring endpoints"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.core.firestore_client import firestore_manager
from app.models.schemas import ErrorResponse
from app.routes.proxy import verify_token_dependency

router = APIRouter()


@router.get(
    "/api/audit/logs",
    responses={
        200: {"description": "Audit logs retrieved successfully"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    summary="Get audit logs",
    description="Retrieve audit logs with optional filters (requires authentication)"
)
async def get_audit_logs(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    days: Optional[int] = Query(7, description="Number of days to look back"),
    limit: Optional[int] = Query(100, description="Maximum number of logs to return"),
    token_payload: dict = Depends(verify_token_dependency)
):
    """
    Get audit logs with filtering options.
    Only returns logs for the authenticated user's project unless they are an admin.
    """
    # Extract user info from token
    _requester_email = token_payload.get("email", "")  # Reserved for future admin checks
    requester_project = token_payload.get("project_id", "")

    # For non-admin users, restrict to their own logs
    # TODO: Add admin check when admin functionality is implemented
    if not project_id:
        project_id = requester_project
    elif project_id != requester_project:
        # Check if user is admin (placeholder for future implementation)
        # For now, restrict to own project
        raise HTTPException(
            status_code=403,
            detail={
                "error": "AUTH_403",
                "message": "Access denied to other project's logs"
            }
        )

    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days) if days else None

    # Get logs from Firestore
    logs = await firestore_manager.get_audit_logs(
        project_id=project_id,
        user_email=user_email,
        event_type=event_type,
        start_date=start_date,
        end_date=end_date,
        limit=limit or 100
    )

    return JSONResponse(content={"logs": logs, "count": len(logs)})


@router.get(
    "/api/audit/login-history",
    responses={
        200: {"description": "Login history retrieved successfully"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    summary="Get login history",
    description="Retrieve login history for the authenticated user"
)
async def get_login_history(
    days: Optional[int] = Query(30, description="Number of days to look back"),
    token_payload: dict = Depends(verify_token_dependency)
):
    """
    Get login history for the authenticated user.
    """
    user_email = token_payload.get("email", "")

    # Get login history from Firestore
    history = await firestore_manager.get_login_history(
        user_email=user_email,
        days=days or 30
    )

    return JSONResponse(content={
        "history": history,
        "count": len(history),
        "user": user_email,
        "days": days
    })


@router.get(
    "/api/audit/statistics",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    summary="Get audit statistics",
    description="Retrieve audit statistics for monitoring"
)
async def get_audit_statistics(
    project_id: Optional[str] = Query(None, description="Project ID for project-specific stats"),
    days: Optional[int] = Query(7, description="Number of days to analyze"),
    token_payload: dict = Depends(verify_token_dependency)
):
    """
    Get audit statistics for monitoring purposes.
    """
    requester_project = token_payload.get("project_id", "")

    # For non-admin users, restrict to their own project
    if not project_id:
        project_id = requester_project
    elif project_id != requester_project:
        # Check if user is admin (placeholder for future implementation)
        raise HTTPException(
            status_code=403,
            detail={
                "error": "AUTH_403",
                "message": "Access denied to other project's statistics"
            }
        )

    # Get statistics from Firestore
    stats = await firestore_manager.get_audit_statistics(
        project_id=project_id,
        days=days or 7
    )

    return JSONResponse(content={
        "statistics": stats,
        "project_id": project_id,
        "period_days": days
    })


@router.post(
    "/api/audit/cleanup",
    responses={
        200: {"description": "Cleanup completed successfully"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden - Admin only", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    summary="Cleanup old audit logs",
    description="Delete audit logs older than retention period (admin only)"
)
async def cleanup_old_logs(
    retention_days: Optional[int] = Query(90, description="Number of days to retain logs"),
    token_payload: dict = Depends(verify_token_dependency)
):
    """
    Cleanup old audit logs.
    This endpoint should be restricted to administrators only.
    """
    # TODO: Implement proper admin check
    # For now, this is a placeholder that checks for a specific email pattern
    user_email = token_payload.get("email", "")

    # Simple admin check (should be replaced with proper admin role check)
    if not user_email.endswith("@i-seifu.jp") or "admin" not in user_email.lower():
        raise HTTPException(
            status_code=403,
            detail={
                "error": "AUTH_403",
                "message": "This operation requires administrator privileges"
            }
        )

    # Perform cleanup
    deleted_count = await firestore_manager.cleanup_old_logs(retention_days=retention_days or 90)

    return JSONResponse(content={
        "message": "Cleanup completed successfully",
        "deleted_count": deleted_count,
        "retention_days": retention_days
    })


@router.get(
    "/api/audit/export",
    responses={
        200: {"description": "Audit logs exported successfully"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    summary="Export audit logs",
    description="Export audit logs in JSON format"
)
async def export_audit_logs(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    token_payload: dict = Depends(verify_token_dependency)
):
    """
    Export audit logs for backup or analysis.
    """
    requester_project = token_payload.get("project_id", "")

    # For non-admin users, restrict to their own project
    if not project_id:
        project_id = requester_project
    elif project_id != requester_project:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "AUTH_403",
                "message": "Access denied to other project's logs"
            }
        )

    # Parse dates if provided
    start_datetime = None
    end_datetime = None

    if start_date:
        try:
            start_datetime = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_DATE",
                    "message": "Invalid start_date format. Use YYYY-MM-DD"
                }
            )

    if end_date:
        try:
            end_datetime = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_DATE",
                    "message": "Invalid end_date format. Use YYYY-MM-DD"
                }
            )

    # Get all logs for export (higher limit)
    logs = await firestore_manager.get_audit_logs(
        project_id=project_id,
        start_date=start_datetime,
        end_date=end_datetime,
        limit=10000  # Higher limit for export
    )

    return JSONResponse(content={
        "export_date": datetime.utcnow().isoformat(),
        "project_id": project_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_records": len(logs),
        "logs": logs
    })