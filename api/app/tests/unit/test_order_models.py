from decimal import Decimal

from sqlalchemy import CheckConstraint

from app.modules.order.enums import OrderStatus
from app.modules.order.models import Order, OrderItem
from app.modules.product.models import Product
from app.modules.user.models import User


def test_order_belongs_to_user_and_supports_planned_statuses() -> None:
    user = User(
        nome="Joao",
        email="joao-order@example.com",
        cpf="12345678901",
        senha_hash="hash",
    )
    order = Order(
        usuario=user,
        status=OrderStatus.PENDING_PAYMENT,
        valor_produtos=Decimal("299.90"),
        valor_frete=Decimal("20.00"),
        valor_total=Decimal("319.90"),
        endereco_snapshot={
            "cep": "01001000",
            "rua": "Praca da Se",
            "numero": "1",
            "complemento": None,
            "bairro": "Se",
            "cidade": "Sao Paulo",
            "estado": "SP",
        },
    )

    assert order.usuario is user
    assert order.status is OrderStatus.PENDING_PAYMENT
    assert set(OrderStatus) == {
        OrderStatus.PENDING_PAYMENT,
        OrderStatus.PAID,
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
        OrderStatus.CANCELED,
    }


def test_order_item_preserves_snapshots_and_domain_constraints() -> None:
    product = Product(
        nome="Teclado mecanico",
        slug="teclado-mecanico-order",
        descricao=None,
        sku="TEC-MEC-ORDER",
        preco=Decimal("299.90"),
    )
    order = Order(
        status=OrderStatus.PENDING_PAYMENT,
        valor_produtos=Decimal("599.80"),
        valor_frete=Decimal("20.00"),
        valor_total=Decimal("619.80"),
        endereco_snapshot={"cidade": "Sao Paulo", "estado": "SP"},
    )
    item = OrderItem(
        pedido=order,
        produto=product,
        nome_produto_snapshot=product.nome,
        sku_snapshot=product.sku,
        quantidade=2,
        preco_unitario_snapshot=product.preco,
        preco_total=Decimal("599.80"),
    )
    order_check_names = {
        constraint.name
        for constraint in Order.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    item_check_names = {
        constraint.name
        for constraint in OrderItem.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert item.pedido is order
    assert item.produto is product
    assert item in order.itens
    assert item.nome_produto_snapshot == "Teclado mecanico"
    assert item.sku_snapshot == "TEC-MEC-ORDER"
    assert item.preco_unitario_snapshot == Decimal("299.90")
    assert item.preco_total == Decimal("599.80")
    assert "ck_orders_valor_produtos_positive" in order_check_names
    assert "ck_orders_valor_frete_non_negative" in order_check_names
    assert "ck_orders_valor_total_positive" in order_check_names
    assert "ck_orders_valor_total_consistent" in order_check_names
    assert "ck_order_items_quantidade_positive" in item_check_names
    assert "ck_order_items_preco_unitario_snapshot_positive" in item_check_names
    assert "ck_order_items_preco_total_positive" in item_check_names
    assert "ck_order_items_preco_total_consistent" in item_check_names
