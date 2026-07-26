from uuid import UUID

from app.modules.order.enums import OrderStatus
from app.modules.order.models import OrderItem
from app.modules.stock.service import StockService
from app.shared.exceptions import (
    BusinessRuleException,
    ConflictException,
    NotFoundException,
)

from .enums import PaymentStatus
from .models import Payment
from .repository import PaymentRepository

_ALLOWED_TRANSITIONS = {
    PaymentStatus.PENDING: {
        PaymentStatus.APPROVED,
        PaymentStatus.REFUSED,
    },
    PaymentStatus.APPROVED: {
        PaymentStatus.REFUNDED,
    },
    PaymentStatus.REFUSED: set(),
    PaymentStatus.REFUNDED: set(),
}
_WEBHOOK_TARGET_STATUSES = {
    PaymentStatus.APPROVED,
    PaymentStatus.REFUSED,
}


class PaymentService:
    def __init__(
        self,
        repository: PaymentRepository,
        stock_service: StockService,
    ) -> None:
        self.repository = repository
        self.stock_service = stock_service

    @staticmethod
    def _ordered_items(payment: Payment) -> list[OrderItem]:
        return sorted(
            payment.pedido.itens,
            key=lambda item: str(item.produto_id),
        )

    @staticmethod
    def _ensure_transition(
        payment: Payment,
        target_status: PaymentStatus,
    ) -> None:
        allowed_statuses = _ALLOWED_TRANSITIONS[payment.status]

        if target_status not in allowed_statuses:
            raise ConflictException(
                code="INVALID_PAYMENT_TRANSITION",
                message="Transicao de status do pagamento invalida.",
                details={
                    "payment_id": str(payment.id),
                    "current_status": payment.status.value,
                    "target_status": target_status.value,
                },
            )

    @staticmethod
    def _normalize_idempotency_key(idempotency_key: str) -> str:
        normalized_key = idempotency_key.strip()

        if not normalized_key or len(normalized_key) > 100:
            raise BusinessRuleException(
                code="INVALID_IDEMPOTENCY_KEY",
                message="Idempotency key invalida.",
            )

        return normalized_key

    @staticmethod
    def _ensure_webhook_status(target_status: PaymentStatus) -> None:
        if target_status not in _WEBHOOK_TARGET_STATUSES:
            raise BusinessRuleException(
                code="INVALID_WEBHOOK_STATUS",
                message="Status invalido para webhook de pagamento.",
                details={"target_status": target_status.value},
            )

    @staticmethod
    def _raise_idempotency_conflict(
        payment_id: UUID,
        idempotency_key: str,
    ) -> None:
        raise ConflictException(
            code="IDEMPOTENCY_KEY_CONFLICT",
            message="Idempotency key ja vinculada a outro processamento.",
            details={
                "payment_id": str(payment_id),
                "idempotency_key": idempotency_key,
            },
        )

    async def _get_payment_for_update(self, payment_id: UUID) -> Payment:
        payment = await self.repository.get_by_id_for_update(payment_id)

        if payment is None:
            raise NotFoundException(
                code="PAYMENT_NOT_FOUND",
                message="Pagamento nao encontrado.",
                details={"payment_id": str(payment_id)},
            )

        return payment

    @staticmethod
    def _ensure_payment_owner(payment: Payment, user_id: UUID) -> None:
        if payment.pedido.usuario_id != user_id:
            raise NotFoundException(
                code="PAYMENT_NOT_FOUND",
                message="Pagamento nao encontrado.",
                details={"payment_id": str(payment.id)},
            )

    async def _approve_payment(self, payment: Payment) -> None:
        self._ensure_transition(payment, PaymentStatus.APPROVED)

        for item in self._ordered_items(payment):
            await self.stock_service.confirm_reservation(
                item.produto_id,
                item.quantidade,
            )

        payment.status = PaymentStatus.APPROVED
        payment.pedido.status = OrderStatus.PAID

    async def approve(
        self,
        payment_id: UUID,
        *,
        user_id: UUID | None = None,
    ) -> Payment:
        payment = await self._get_payment_for_update(payment_id)

        if user_id is not None:
            self._ensure_payment_owner(payment, user_id)

        await self._approve_payment(payment)
        return await self.repository.update(payment)

    async def _refuse_payment(self, payment: Payment) -> None:
        self._ensure_transition(payment, PaymentStatus.REFUSED)

        for item in self._ordered_items(payment):
            await self.stock_service.release_reservation(
                item.produto_id,
                item.quantidade,
            )

        payment.status = PaymentStatus.REFUSED
        payment.pedido.status = OrderStatus.CANCELED

    async def refuse(
        self,
        payment_id: UUID,
        *,
        user_id: UUID | None = None,
    ) -> Payment:
        payment = await self._get_payment_for_update(payment_id)

        if user_id is not None:
            self._ensure_payment_owner(payment, user_id)

        await self._refuse_payment(payment)
        return await self.repository.update(payment)

    async def _refund_payment(self, payment: Payment) -> None:
        self._ensure_transition(payment, PaymentStatus.REFUNDED)

        for item in self._ordered_items(payment):
            await self.stock_service.increase(
                item.produto_id,
                item.quantidade,
            )

        payment.status = PaymentStatus.REFUNDED
        payment.pedido.status = OrderStatus.CANCELED

    async def refund(self, payment_id: UUID) -> Payment:
        payment = await self._get_payment_for_update(payment_id)
        await self._refund_payment(payment)
        return await self.repository.update(payment)

    async def process_webhook(
        self,
        payment_id: UUID,
        target_status: PaymentStatus,
        idempotency_key: str,
    ) -> Payment:
        normalized_key = self._normalize_idempotency_key(idempotency_key)
        self._ensure_webhook_status(target_status)
        processed_payment = await self.repository.get_by_idempotency_key(normalized_key)

        if processed_payment is not None:
            if processed_payment.id != payment_id:
                self._raise_idempotency_conflict(payment_id, normalized_key)
            return processed_payment

        payment = await self._get_payment_for_update(payment_id)

        if payment.idempotency_key == normalized_key:
            return payment

        if payment.idempotency_key is not None:
            self._raise_idempotency_conflict(payment_id, normalized_key)

        if target_status is PaymentStatus.APPROVED:
            await self._approve_payment(payment)
        else:
            await self._refuse_payment(payment)

        payment.idempotency_key = normalized_key
        return await self.repository.update(payment)
