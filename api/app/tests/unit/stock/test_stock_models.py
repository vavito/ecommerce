from decimal import Decimal

from sqlalchemy import CheckConstraint

from app.modules.product.models import Product
from app.modules.stock.models import Stock


def test_stock_belongs_to_product_and_enforces_domain_constraints() -> None:
    product = Product(
        nome="Teclado mecanico",
        slug="teclado-mecanico",
        descricao=None,
        sku="TEC-MEC-001",
        preco=Decimal("299.90"),
    )
    stock = Stock(
        produto=product,
        quantidade=10,
        quantidade_reservada=3,
    )
    check_constraint_names = {
        constraint.name
        for constraint in Stock.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert stock.produto is product
    assert stock.quantidade == 10
    assert stock.quantidade_reservada == 3
    assert stock.quantidade_disponivel == 7
    assert Stock.__table__.c.produto_id.unique is True
    assert "ck_stocks_quantidade_non_negative" in check_constraint_names
    assert "ck_stocks_quantidade_reservada_non_negative" in check_constraint_names
    assert "ck_stocks_quantidade_reservada_lte_quantidade" in check_constraint_names
