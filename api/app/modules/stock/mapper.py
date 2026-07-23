from .models import Stock
from .schemas import StockOut


class StockMapper:
    @staticmethod
    def to_output(stock: Stock) -> StockOut:
        return StockOut.model_validate(stock)
