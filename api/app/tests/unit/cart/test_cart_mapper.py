from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.modules.cart.enums import CartStatus
from app.modules.cart.mapper import CartMapper
from app.modules.cart.models import Cart, CartItem


def test_cart_mapper_returns_items_subtotals_and_estimated_total() -> None:
    now = datetime.now(UTC)
    cart = Cart(
        id=uuid4(),
        usuario_id=uuid4(),
        status=CartStatus.OPEN,
        criado_em=now,
        atualizado_em=now,
        itens=[
            CartItem(
                id=uuid4(),
                produto_id=uuid4(),
                quantidade=2,
                preco_unitario_atual=Decimal("299.90"),
                criado_em=now,
                atualizado_em=now,
            ),
            CartItem(
                id=uuid4(),
                produto_id=uuid4(),
                quantidade=3,
                preco_unitario_atual=Decimal("49.90"),
                criado_em=now,
                atualizado_em=now,
            ),
        ],
    )

    output = CartMapper.to_output(cart)

    assert output.id == cart.id
    assert output.usuario_id == cart.usuario_id
    assert output.status is CartStatus.OPEN
    assert len(output.itens) == 2
    assert output.itens[0].subtotal == Decimal("599.80")
    assert output.itens[1].subtotal == Decimal("149.70")
    assert output.total_estimado == Decimal("749.50")
    assert output.criado_em == now
    assert output.atualizado_em == now


def test_cart_mapper_returns_zero_total_for_empty_cart() -> None:
    now = datetime.now(UTC)
    cart = Cart(
        id=uuid4(),
        usuario_id=uuid4(),
        status=CartStatus.OPEN,
        criado_em=now,
        atualizado_em=now,
        itens=[],
    )

    output = CartMapper.to_output(cart)

    assert output.itens == []
    assert output.total_estimado == Decimal("0.00")
