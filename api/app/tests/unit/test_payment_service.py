from decimal import Decimal
from unittest.mock import AsyncMock, call
from uuid import UUID, uuid4

import pytest

from app.modules.order.enums import OrderStatus
from app.modules.order.models import Order, OrderItem
from app.modules.payment.enums import PaymentMethod, PaymentStatus
from app.modules.payment.models import Payment
from app.modules.payment.repository import PaymentRepository
from app.modules.payment.service import PaymentService
from app.modules.stock.service import StockService
from app.shared.exceptions import ConflictException, NotFoundException


def make_payment() -> Payment:
    order = Order(
        id=uuid4(),
        usuario_id=uuid4(),
        status=OrderStatus.PENDING_PAYMENT,
        valor_produtos=Decimal("400.00"),
        valor_frete=Decimal("20.00"),
        valor_total=Decimal("420.00"),
        endereco_snapshot={},
        itens=[
            OrderItem(
                produto_id=UUID(int=2),
                nome_produto_snapshot="Mouse sem fio",
                sku_snapshot="MOU-001",
                quantidade=2,
                preco_unitario_snapshot=Decimal("100.00"),
                preco_total=Decimal("200.00"),
            ),
            OrderItem(
                produto_id=UUID(int=1),
                nome_produto_snapshot="Teclado mecanico",
                sku_snapshot="TEC-001",
                quantidade=1,
                preco_unitario_snapshot=Decimal("200.00"),
                preco_total=Decimal("200.00"),
            ),
        ],
    )
    return Payment(
        id=uuid4(),
        pedido=order,
        metodo=PaymentMethod.PIX,
        status=PaymentStatus.PENDING,
        valor=order.valor_total,
        gateway="MOCK",
    )


def make_service() -> tuple[PaymentService, AsyncMock, AsyncMock]:
    repository = AsyncMock(spec=PaymentRepository)
    stock_service = AsyncMock(spec=StockService)
    service = PaymentService(repository, stock_service)
    return service, repository, stock_service


async def test_approve_confirms_stock_and_marks_payment_and_order_as_paid() -> None:
    service, repository, stock_service = make_service()
    payment = make_payment()
    repository.get_by_id_for_update.return_value = payment
    repository.update.side_effect = lambda updated_payment: updated_payment

    result = await service.approve(payment.id)

    assert result is payment
    assert payment.status is PaymentStatus.APPROVED
    assert payment.pedido.status is OrderStatus.PAID
    stock_service.confirm_reservation.assert_has_awaits(
        [
            call(UUID(int=1), 1),
            call(UUID(int=2), 2),
        ]
    )
    repository.update.assert_awaited_once_with(payment)


async def test_refuse_releases_stock_and_cancels_payment_order() -> None:
    service, repository, stock_service = make_service()
    payment = make_payment()
    repository.get_by_id_for_update.return_value = payment
    repository.update.side_effect = lambda updated_payment: updated_payment

    result = await service.refuse(payment.id)

    assert result is payment
    assert payment.status is PaymentStatus.REFUSED
    assert payment.pedido.status is OrderStatus.CANCELED
    stock_service.release_reservation.assert_has_awaits(
        [
            call(UUID(int=1), 1),
            call(UUID(int=2), 2),
        ]
    )
    repository.update.assert_awaited_once_with(payment)


async def test_refund_restores_stock_and_marks_payment_as_refunded() -> None:
    service, repository, stock_service = make_service()
    payment = make_payment()
    payment.status = PaymentStatus.APPROVED
    payment.pedido.status = OrderStatus.PAID
    repository.get_by_id_for_update.return_value = payment
    repository.update.side_effect = lambda updated_payment: updated_payment

    result = await service.refund(payment.id)

    assert result is payment
    assert payment.status is PaymentStatus.REFUNDED
    assert payment.pedido.status is OrderStatus.CANCELED
    stock_service.increase.assert_has_awaits(
        [
            call(UUID(int=1), 1),
            call(UUID(int=2), 2),
        ]
    )
    repository.update.assert_awaited_once_with(payment)


async def test_payment_not_found_stops_processing() -> None:
    service, repository, stock_service = make_service()
    payment_id = uuid4()
    repository.get_by_id_for_update.return_value = None

    with pytest.raises(NotFoundException) as exc_info:
        await service.approve(payment_id)

    assert exc_info.value.code == "PAYMENT_NOT_FOUND"
    assert exc_info.value.details == {"payment_id": str(payment_id)}
    stock_service.confirm_reservation.assert_not_awaited()
    repository.update.assert_not_awaited()


@pytest.mark.parametrize(
    ("method_name", "current_status", "target_status"),
    [
        ("approve", PaymentStatus.APPROVED, PaymentStatus.APPROVED),
        ("approve", PaymentStatus.REFUSED, PaymentStatus.APPROVED),
        ("approve", PaymentStatus.REFUNDED, PaymentStatus.APPROVED),
        ("refuse", PaymentStatus.APPROVED, PaymentStatus.REFUSED),
        ("refuse", PaymentStatus.REFUSED, PaymentStatus.REFUSED),
        ("refuse", PaymentStatus.REFUNDED, PaymentStatus.REFUSED),
        ("refund", PaymentStatus.PENDING, PaymentStatus.REFUNDED),
        ("refund", PaymentStatus.REFUSED, PaymentStatus.REFUNDED),
        ("refund", PaymentStatus.REFUNDED, PaymentStatus.REFUNDED),
    ],
)
async def test_invalid_payment_transitions_are_blocked_before_stock_changes(
    method_name: str,
    current_status: PaymentStatus,
    target_status: PaymentStatus,
) -> None:
    service, repository, stock_service = make_service()
    payment = make_payment()
    payment.status = current_status
    repository.get_by_id_for_update.return_value = payment

    with pytest.raises(ConflictException) as exc_info:
        await getattr(service, method_name)(payment.id)

    assert exc_info.value.code == "INVALID_PAYMENT_TRANSITION"
    assert exc_info.value.details == {
        "payment_id": str(payment.id),
        "current_status": current_status.value,
        "target_status": target_status.value,
    }
    stock_service.confirm_reservation.assert_not_awaited()
    stock_service.release_reservation.assert_not_awaited()
    stock_service.increase.assert_not_awaited()
    repository.update.assert_not_awaited()
