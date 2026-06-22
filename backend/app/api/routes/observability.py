from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.contracts import WorkflowStatus
from app.core.errors import safe_http_exception
from app.core.security import require_admin_token
from app.services import observability

router = APIRouter(
    prefix="/observability",
    tags=["observability"],
    dependencies=[Depends(require_admin_token)],
)


@router.get("/runs")
def list_runs(
    workflow_type: str | None = None,
    status_filter: Annotated[
        WorkflowStatus | None,
        Query(alias="status"),
    ] = None,
    limit: int = 50,
) -> dict[str, object]:
    clamped_limit = max(1, min(int(limit), 100))
    return {
        "runs": observability.list_workflow_runs(
            workflow_type=workflow_type,
            status=status_filter.value if status_filter is not None else None,
            limit=clamped_limit,
        )
    }


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    run = observability.get_workflow_run(run_id)
    if run is None:
        raise safe_http_exception(
            status.HTTP_404_NOT_FOUND,
            f"Workflow run {run_id} not found",
        )
    return run
