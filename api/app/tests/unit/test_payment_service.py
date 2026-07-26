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
from app.shared.exceptions import (
    BusinessRuleException,
    ConflictException,
    NotFoundException,
)


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


async def test_approve_hides_payment_from_another_user() -> None:
    service, repository, stock_service = make_service()
    payment = make_payment()
    repository.get_by_id_for_update.return_value = payment
    other_user_id = uuid4()

    with pytest.raises(NotFoundException) as exc_info:
        await service.approve(
            payment.id,
            user_id=other_user_id,
        )

    assert exc_info.value.code == "PAYMENT_NOT_FOUND"
    assert exc_info.value.details == {"payment_id": str(payment.id)}
    stock_service.confirm_reservation.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_refuse_hides_payment_from_another_user() -> None:
    service, repository, stock_service = make_service()
    payment = make_payment()
    repository.get_by_id_for_update.return_value = payment
    other_user_id = uuid4()

    with pytest.raises(NotFoundException) as exc_info:
        await service.refuse(
            payment.id,
            user_id=other_user_id,
        )

    assert exc_info.value.code == "PAYMENT_NOT_FOUND"
    assert exc_info.value.details == {"payment_id": str(payment.id)}
    stock_service.release_reservation.assert_not_awaited()
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


@pytest.mark.parametrize(
    ("target_status", "stock_method_name", "expected_order_status"),
    [
        (
            PaymentStatus.APPROVED,
            "confirm_reservation",
            OrderStatus.PAID,
        ),
        (
            PaymentStatus.REFUSED,
            "release_reservation",
            OrderStatus.CANCELED,
        ),
    ],
)
async def test_webhook_processes_new_key_once(
    target_status: PaymentStatus,
    stock_method_name: str,
    expected_order_status: OrderStatus,
) -> None:
    service, repository, stock_service = make_service()
    payment = make_payment()
    repository.get_by_idempotency_key.return_value = None
    repository.get_by_id_for_update.return_value = payment
    repository.update.side_effect = lambda updated_payment: updated_payment

    result = await service.process_webhook(
        payment.id,
        target_status,
        " event-abc ",
    )

    assert result is payment
    assert payment.status is target_status
    assert payment.pedido.status is expected_order_status
    assert payment.idempotency_key == "event-abc"
    getattr(stock_service, stock_method_name).assert_has_awaits(
        [
            call(UUID(int=1), 1),
            call(UUID(int=2), 2),
        ]
    )
    repository.update.assert_awaited_once_with(payment)


async def test_repeated_webhook_returns_processed_payment_without_new_effects() -> None:
    service, repository, stock_service = make_service()
    payment = make_payment()
    payment.status = PaymentStatus.APPROVED
    payment.pedido.status = OrderStatus.PAID
    payment.idempotency_key = "event-abc"
    repository.get_by_idempotency_key.return_value = payment

    result = await service.process_webhook(
        payment.id,
        PaymentStatus.APPROVED,
        "event-abc",
    )

    assert result is payment
    repository.get_by_id_for_update.assert_not_awaited()
    stock_service.confirm_reservation.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_concurrent_duplicate_is_rechecked_after_payment_lock() -> None:
    service, repository, stock_service = make_service()
    payment = make_payment()
    payment.status = PaymentStatus.APPROVED
    payment.pedido.status = OrderStatus.PAID
    payment.idempotency_key = "event-abc"
    repository.get_by_idempotency_key.return_value = None
    repository.get_by_id_for_update.return_value = payment

    result = await service.process_webhook(
        payment.id,
        PaymentStatus.APPROVED,
        "event-abc",
    )

    assert result is payment
    stock_service.confirm_reservation.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_idempotency_key_cannot_be_reused_for_another_payment() -> None:
    service, repository, stock_service = make_service()
    processed_payment = make_payment()
    repository.get_by_idempotency_key.return_value = processed_payment
    requested_payment_id = uuid4()

    with pytest.raises(ConflictException) as exc_info:
        await service.process_webhook(
            requested_payment_id,
            PaymentStatus.APPROVED,
            "event-abc",
        )

    assert exc_info.value.code == "IDEMPOTENCY_KEY_CONFLICT"
    assert exc_info.value.details == {
        "payment_id": str(requested_payment_id),
        "idempotency_key": "event-abc",
    }
    repository.get_by_id_for_update.assert_not_awaited()
    stock_service.confirm_reservation.assert_not_awaited()
    repository.update.assert_not_awaited()


async def test_payment_cannot_replace_processed_idempotency_key() -> None:
    service, repository, stock_service = make_service()
    payment = make_payment()
    payment.idempotency_key = "event-original"
    repository.get_by_idempotency_key.return_value = None
    repository.get_by_id_for_update.return_value = payment

    with pytest.raises(ConflictException) as exc_info:
        await service.process_webhook(
            payment.id,
            PaymentStatus.APPROVED,
            "event-new",
        )

    assert exc_info.value.code == "IDEMPOTENCY_KEY_CONFLICT"
    stock_service.confirm_reservation.assert_not_awaited()
    repository.update.assert_not_awaited()


@pytest.mark.parametrize("idempotency_key", ["", "   ", "x" * 101])
async def test_webhook_rejects_invalid_idempotency_key(
    idempotency_key: str,
) -> None:
    service, repository, _stock_service = make_service()

    with pytest.raises(BusinessRuleException) as exc_info:
        await service.process_webhook(
            uuid4(),
            PaymentStatus.APPROVED,
            idempotency_key,
        )

    assert exc_info.value.code == "INVALID_IDEMPOTENCY_KEY"
    repository.get_by_idempotency_key.assert_not_awaited()


async def test_webhook_rejects_status_that_is_not_a_gateway_result() -> None:
    service, repository, _stock_service = make_service()

    with pytest.raises(BusinessRuleException) as exc_info:
        await service.process_webhook(
            uuid4(),
            PaymentStatus.PENDING,
            "event-abc",
        )

    assert exc_info.value.code == "INVALID_WEBHOOK_STATUS"
    assert exc_info.value.details == {"target_status": "PENDING"}
    repository.get_by_idempotency_key.assert_not_awaited()
