from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.stock.repository import StockRepository
from app.modules.stock.service import StockService
from app.modules.user.models import User

from .mapper import PaymentMapper
from .repository import PaymentRepository
from .schemas import PaymentOut, PaymentWebhookRequest
from .service import PaymentService

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)

CurrentUser = Annotated[User, Depends(get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _build_payment_service(session: AsyncSession) -> PaymentService:
    return PaymentService(
        PaymentRepository(session),
        StockService(StockRepository(session)),
    )


@router.post(
    "/webhook/mock",
    response_model=PaymentOut,
)
async def process_mock_webhook(
    data: PaymentWebhookRequest,
    session: SessionDep,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=100,
        ),
    ],
) -> PaymentOut:
    service = _build_payment_service(session)
    payment = await service.process_webhook(
        data.payment_id,
        data.status,
        idempotency_key,
        data.gateway_transaction_id,
    )

    await session.commit()
    await session.refresh(payment)

    return PaymentMapper.to_output(payment)


@router.post(
    "/{payment_id}/approve",
    response_model=PaymentOut,
)
async def approve_payment(
    payment_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> PaymentOut:
    service = _build_payment_service(session)
    payment = await service.approve(
        payment_id,
        user_id=current_user.id,
    )

    await session.commit()
    await session.refresh(payment)

    return PaymentMapper.to_output(payment)


@router.post(
    "/{payment_id}/refuse",
    response_model=PaymentOut,
)
async def refuse_payment(
    payment_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> PaymentOut:
    service = _build_payment_service(session)
    payment = await service.refuse(
        payment_id,
        user_id=current_user.id,
    )

    await session.commit()
    await session.refresh(payment)

    return PaymentMapper.to_output(payment)
