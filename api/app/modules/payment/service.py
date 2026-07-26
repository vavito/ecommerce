from uuid import UUID

from app.modules.order.enums import OrderStatus
from app.modules.order.models import OrderItem
from app.modules.stock.service import StockService
from app.shared.exceptions import ConflictException, NotFoundException

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

    async def _get_payment_for_update(self, payment_id: UUID) -> Payment:
        payment = await self.repository.get_by_id_for_update(payment_id)

        if payment is None:
            raise NotFoundException(
                code="PAYMENT_NOT_FOUND",
                message="Pagamento nao encontrado.",
                details={"payment_id": str(payment_id)},
            )

        return payment

    async def approve(self, payment_id: UUID) -> Payment:
        payment = await self._get_payment_for_update(payment_id)
        self._ensure_transition(payment, PaymentStatus.APPROVED)

        for item in self._ordered_items(payment):
            await self.stock_service.confirm_reservation(
                item.produto_id,
                item.quantidade,
            )

        payment.status = PaymentStatus.APPROVED
        payment.pedido.status = OrderStatus.PAID
        return await self.repository.update(payment)

    async def refuse(self, payment_id: UUID) -> Payment:
        payment = await self._get_payment_for_update(payment_id)
        self._ensure_transition(payment, PaymentStatus.REFUSED)

        for item in self._ordered_items(payment):
            await self.stock_service.release_reservation(
                item.produto_id,
                item.quantidade,
            )

        payment.status = PaymentStatus.REFUSED
        payment.pedido.status = OrderStatus.CANCELED
        return await self.repository.update(payment)

    async def refund(self, payment_id: UUID) -> Payment:
        payment = await self._get_payment_for_update(payment_id)
        self._ensure_transition(payment, PaymentStatus.REFUNDED)

        for item in self._ordered_items(payment):
            await self.stock_service.increase(
                item.produto_id,
                item.quantidade,
            )

        payment.status = PaymentStatus.REFUNDED
        payment.pedido.status = OrderStatus.CANCELED
        return await self.repository.update(payment)
