from .models import Payment
from .schemas import PaymentOut


class PaymentMapper:
    @staticmethod
    def to_output(payment: Payment) -> PaymentOut:
        return PaymentOut.model_validate(payment)
