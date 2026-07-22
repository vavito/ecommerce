from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.modules.product.mapper import ProductMapper
from app.modules.product.models import Product
from app.modules.product.schemas import ProductCreate


def test_product_mapper_converts_create_schema_to_entity() -> None:
    schema = ProductCreate(
        categoria_id=uuid4(),
        nome="Teclado mecanico",
        descricao="Teclado com switches mecanicos.",
        sku="TEC-MEC-001",
        preco=Decimal("299.90"),
    )

    product = ProductMapper.to_entity(schema)

    assert product.categoria_id == schema.categoria_id
    assert product.nome == schema.nome
    assert product.descricao == schema.descricao
    assert product.sku == schema.sku
    assert product.preco == schema.preco


def test_product_mapper_converts_entity_to_output() -> None:
    now = datetime.now(UTC)
    product = Product(
        id=uuid4(),
        categoria_id=uuid4(),
        nome="Teclado mecanico",
        descricao=None,
        sku="TEC-MEC-001",
        preco=Decimal("299.90"),
        ativo=True,
        criado_em=now,
        atualizado_em=now,
    )

    output = ProductMapper.to_output(product)

    assert output.id == product.id
    assert output.categoria_id == product.categoria_id
    assert output.nome == product.nome
    assert output.descricao is None
    assert output.sku == product.sku
    assert output.preco == product.preco
    assert output.ativo is True
