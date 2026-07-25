from enum import StrEnum


class CartStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ABANDONED = "ABANDONED"
