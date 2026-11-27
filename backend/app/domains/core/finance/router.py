from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import (
    CommissionStatus,
    FinancialTransactionCategory,
    FinancialTransactionType,
    SaleStatus,
    StudioRole,
)
from app.core.rbac import TenantContext, get_active_tenant_context, require_roles
from app.domains.core.finance.ledger_service import (
    create_manual_financial_transaction,
    get_daily_operational_register,
    get_executive_dashboard,
    get_my_commissions_summary,
    list_commissions_for_owner,
    list_financial_transactions,
    payout_professional_commissions,
    reverse_financial_transaction,
)
from app.domains.core.finance.pos_service import (
    checkout_pos_sale,
    get_sale_detail,
    list_sales,
    refund_sale,
)
from app.domains.core.finance.schemas import (
    CashflowPeriodSummaryResponse,
    CommissionItemResponse,
    CommissionPayoutRequest,
    CommissionPayoutResponse,
    DailyRegisterResponse,
    ExecutiveDashboardResponse,
    FinancialTransactionResponse,
    ManualTransactionCreateRequest,
    MyCommissionsSummaryResponse,
    ReverseTransactionRequest,
    SaleCheckoutRequest,
    SaleOwnerResponse,
    SaleRefundRequest,
    SaleStaffResponse,
)

router = APIRouter(prefix="/finance", tags=["POS, Commissions, Cashflow & Dashboard"])


@router.post(
    "/sales",
    response_model=SaleOwnerResponse | SaleStaffResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sale_endpoint(
    payload: SaleCheckoutRequest,
    request: Request,
    tenant: TenantContext = Depends(
        require_roles(StudioRole.OWNER, StudioRole.RECEPTION)
    ),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    sale_dto = await checkout_pos_sale(db, tenant, payload, request=request)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=sale_dto.model_dump(mode="json"),
    )


@router.get(
    "/sales",
    response_model=list[SaleOwnerResponse | SaleStaffResponse],
)
async def list_sales_endpoint(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    status_filter: SaleStatus | None = Query(default=None, alias="status"),
    client_id: uuid.UUID | None = Query(default=None),
    tenant: TenantContext = Depends(
        require_roles(StudioRole.OWNER, StudioRole.RECEPTION)
    ),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    rows = await list_sales(
        db,
        tenant,
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
        client_id=client_id,
    )
    return JSONResponse(content=[r.model_dump(mode="json") for r in rows])


@router.get(
    "/sales/{sale_id}",
    response_model=SaleOwnerResponse | SaleStaffResponse,
)
async def get_sale_endpoint(
    sale_id: uuid.UUID,
    tenant: TenantContext = Depends(
        require_roles(StudioRole.OWNER, StudioRole.RECEPTION)
    ),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    item = await get_sale_detail(db, tenant, sale_id)
    return JSONResponse(content=item.model_dump(mode="json"))


@router.post(
    "/sales/{sale_id}/refund",
    response_model=SaleOwnerResponse,
)
async def refund_sale_endpoint(
    sale_id: uuid.UUID,
    payload: SaleRefundRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> SaleOwnerResponse:
    return await refund_sale(db, tenant, sale_id, payload, request=request)


@router.get(
    "/commissions",
    response_model=list[CommissionItemResponse],
)
async def list_commissions_endpoint(
    professional_id: uuid.UUID | None = Query(default=None),
    status_filter: CommissionStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> list[CommissionItemResponse]:
    return await list_commissions_for_owner(
        db,
        tenant,
        professional_id=professional_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
    )


@router.post(
    "/commissions/payout",
    response_model=CommissionPayoutResponse,
)
async def payout_commissions_endpoint(
    payload: CommissionPayoutRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> CommissionPayoutResponse:
    return await payout_professional_commissions(
        db, tenant, payload, request=request
    )


@router.get(
    "/my-commissions",
    response_model=MyCommissionsSummaryResponse,
)
async def my_commissions_endpoint(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    tenant: TenantContext = Depends(get_active_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> MyCommissionsSummaryResponse:
    return await get_my_commissions_summary(
        db, tenant, date_from=date_from, date_to=date_to
    )


@router.get(
    "/transactions",
    response_model=CashflowPeriodSummaryResponse,
)
async def list_transactions_endpoint(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    tx_type: FinancialTransactionType | None = Query(default=None, alias="type"),
    category: FinancialTransactionCategory | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> CashflowPeriodSummaryResponse:
    return await list_financial_transactions(
        db,
        tenant,
        date_from=date_from,
        date_to=date_to,
        tx_type=tx_type,
        category=category,
        offset=offset,
        limit=limit,
    )


@router.post(
    "/transactions",
    response_model=FinancialTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_transaction_endpoint(
    payload: ManualTransactionCreateRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> FinancialTransactionResponse:
    return await create_manual_financial_transaction(
        db, tenant, payload, request=request
    )


@router.post(
    "/transactions/{transaction_id}/reverse",
    response_model=FinancialTransactionResponse,
)
async def reverse_transaction_endpoint(
    transaction_id: uuid.UUID,
    payload: ReverseTransactionRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> FinancialTransactionResponse:
    return await reverse_financial_transaction(
        db, tenant, transaction_id, payload, request=request
    )


@router.get(
    "/daily-register",
    response_model=DailyRegisterResponse,
)
async def daily_register_endpoint(
    target_date: date | None = Query(default=None),
    tenant: TenantContext = Depends(
        require_roles(StudioRole.OWNER, StudioRole.RECEPTION)
    ),
    db: AsyncSession = Depends(get_db),
) -> DailyRegisterResponse:
    return await get_daily_operational_register(
        db, tenant, target_date=target_date
    )


@router.get(
    "/dashboard",
    response_model=ExecutiveDashboardResponse,
)
async def executive_dashboard_endpoint(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    tenant: TenantContext = Depends(require_roles(StudioRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> ExecutiveDashboardResponse:
    return await get_executive_dashboard(
        db, tenant, date_from=date_from, date_to=date_to
    )
