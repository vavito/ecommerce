from enum import StrEnum


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REFUSED = "REFUSED"
    REFUNDED = "REFUNDED"


class PaymentMethod(StrEnum):
    CREDIT_CARD = "CREDIT_CARD"
    PIX = "PIX"
    BOLETO = "BOLETO"
