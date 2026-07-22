from decimal import Decimal

from app.modules.product.models import Category, Product


def test_category_and_product_relationship_is_bidirectional() -> None:
    category = Category(
        nome="Eletronicos",
        slug="eletronicos",
    )
    product = Product(
        nome="Teclado mecanico",
        descricao="Teclado com switches mecanicos.",
        sku="TEC-MEC-001",
        preco=Decimal("299.90"),
        categoria=category,
    )

    assert product.categoria is category
    assert product in category.produtos
