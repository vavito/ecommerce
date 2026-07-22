from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.product.models import Category, Product
from app.modules.product.schemas import (
    CategoryOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)


def test_product_create_validates_and_converts_price() -> None:
    schema = ProductCreate(
        categoria_id=uuid4(),
        nome="Teclado mecanico",
        descricao="Teclado com switches mecanicos.",
        sku="TEC-MEC-001",
        preco="299.90",
    )

    assert schema.preco == Decimal("299.90")


@pytest.mark.parametrize(
    "price",
    ["0", "-1.00", "10.999", "100000000.00"],
)
def test_product_create_rejects_invalid_price(price: str) -> None:
    with pytest.raises(ValidationError):
        ProductCreate(
            categoria_id=uuid4(),
            nome="Teclado mecanico",
            descricao=None,
            sku="TEC-MEC-001",
            preco=price,
        )


def test_product_update_supports_partial_changes() -> None:
    schema = ProductUpdate(preco="249.90")

    assert schema.model_dump(exclude_unset=True) == {
        "preco": Decimal("249.90"),
    }


def test_category_and_product_outputs_accept_orm_models() -> None:
    now = datetime.now(UTC)
    category = Category(
        id=uuid4(),
        nome="Eletronicos",
        slug="eletronicos",
        ativo=True,
        criado_em=now,
        atualizado_em=now,
    )
    product = Product(
        id=uuid4(),
        categoria_id=category.id,
        nome="Teclado mecanico",
        slug="teclado-mecanico",
        descricao=None,
        sku="TEC-MEC-001",
        preco=Decimal("299.90"),
        ativo=True,
        criado_em=now,
        atualizado_em=now,
    )

    category_output = CategoryOut.model_validate(category)
    product_output = ProductOut.model_validate(product)

    assert category_output.id == category.id
    assert product_output.id == product.id
    assert product_output.slug == product.slug
    assert product_output.preco == Decimal("299.90")
