from datetime import UTC, datetime
from uuid import uuid4

from app.modules.stock.mapper import StockMapper
from app.modules.stock.models import Stock


def test_stock_mapper_converts_entity_to_output() -> None:
    now = datetime.now(UTC)
    stock = Stock(
        id=uuid4(),
        produto_id=uuid4(),
        quantidade=10,
        quantidade_reservada=3,
        criado_em=now,
        atualizado_em=now,
    )

    output = StockMapper.to_output(stock)

    assert output.id == stock.id
    assert output.produto_id == stock.produto_id
    assert output.quantidade == 10
    assert output.quantidade_reservada == 3
    assert output.quantidade_disponivel == 7
    assert output.criado_em == now
    assert output.atualizado_em == now
