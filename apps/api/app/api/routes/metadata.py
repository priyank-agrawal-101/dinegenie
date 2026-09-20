"""Active-dataset metadata endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.api.contracts import (
    BudgetBand,
    BudgetBandDefinition,
    BudgetBandsResponse,
    ErrorResponse,
    MetadataResponse,
)

router = APIRouter(prefix="/api/v1/metadata", tags=["metadata"])


@router.get(
    "/locations",
    response_model=MetadataResponse,
    responses={503: {"model": ErrorResponse}},
)
def locations(
    request: Request,
    query: str = Query(default="", max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
) -> MetadataResponse:
    version, values = request.app.state.metadata_service.locations(query, limit)
    return MetadataResponse(dataset_version=version, values=values)


@router.get(
    "/cuisines",
    response_model=MetadataResponse,
    responses={503: {"model": ErrorResponse}},
)
def cuisines(
    request: Request,
    location: str | None = Query(default=None, min_length=1, max_length=80),
    limit: int = Query(default=100, ge=1, le=250),
) -> MetadataResponse:
    version, values = request.app.state.metadata_service.cuisines(location, limit)
    return MetadataResponse(dataset_version=version, values=values)


@router.get("/budget-bands", response_model=BudgetBandsResponse)
def budget_bands(request: Request) -> BudgetBandsResponse:
    settings = request.app.state.settings
    return BudgetBandsResponse(
        bands=[
            BudgetBandDefinition(
                id=BudgetBand.LOW,
                label=f"Low (up to INR {settings.budget_low_max:,})",
                minimum_exclusive=None,
                maximum_inclusive=settings.budget_low_max,
                currency="INR",
                basis="for_two",
            ),
            BudgetBandDefinition(
                id=BudgetBand.MEDIUM,
                label=(
                    f"Medium (over INR {settings.budget_low_max:,} "
                    f"to INR {settings.budget_medium_max:,})"
                ),
                minimum_exclusive=settings.budget_low_max,
                maximum_inclusive=settings.budget_medium_max,
                currency="INR",
                basis="for_two",
            ),
            BudgetBandDefinition(
                id=BudgetBand.HIGH,
                label=f"High (over INR {settings.budget_medium_max:,})",
                minimum_exclusive=settings.budget_medium_max,
                maximum_inclusive=None,
                currency="INR",
                basis="for_two",
            ),
        ]
    )
