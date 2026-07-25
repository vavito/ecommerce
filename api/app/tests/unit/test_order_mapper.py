from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.modules.order.enums import OrderStatus
from app.modules.order.mapper import OrderMapper
from app.modules.order.models import Order, OrderItem
from app.modules.order.schemas import AddressSnapshotOut, OrderItemOut, OrderOut


def test_order_mapper_returns_complete_order_with_items_and_totals() -> None:
    order_id = uuid4()
    user_id = uuid4()
    product_id = uuid4()
    timestamp = datetime.now(UTC)
    order = Order(
        id=order_id,
        usuario_id=user_id,
        status=OrderStatus.PENDING_PAYMENT,
        valor_produtos=Decimal("299.90"),
        valor_frete=Decimal("15.00"),
        valor_total=Decimal("314.90"),
        endereco_snapshot={
            "cep": "01001000",
            "rua": "Praca da Se",
            "numero": "1",
            "complemento": None,
            "bairro": "Se",
            "cidade": "Sao Paulo",
            "estado": "SP",
        },
        criado_em=timestamp,
        atualizado_em=timestamp,
        itens=[
            OrderItem(
                id=uuid4(),
                pedido_id=order_id,
                produto_id=product_id,
                nome_produto_snapshot="Teclado mecanico",
                sku_snapshot="TEC-001",
                quantidade=1,
                preco_unitario_snapshot=Decimal("299.90"),
                preco_total=Decimal("299.90"),
            )
        ],
    )

    result = OrderMapper.to_output(order)

    assert isinstance(result, OrderOut)
    assert isinstance(result.endereco_snapshot, AddressSnapshotOut)
    assert isinstance(result.itens[0], OrderItemOut)
    assert result.id == order_id
    assert result.usuario_id == user_id
    assert result.status is OrderStatus.PENDING_PAYMENT
    assert result.valor_produtos == Decimal("299.90")
    assert result.valor_frete == Decimal("15.00")
    assert result.valor_total == Decimal("314.90")
    assert result.endereco_snapshot.cidade == "Sao Paulo"
    assert len(result.itens) == 1
    assert result.itens[0].produto_id == product_id
    assert result.itens[0].nome_produto_snapshot == "Teclado mecanico"
    assert result.itens[0].preco_unitario_snapshot == Decimal("299.90")
    assert result.itens[0].preco_total == Decimal("299.90")
