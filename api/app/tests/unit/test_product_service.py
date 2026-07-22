from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.product.models import Category, Product
from app.modules.product.repository import ProductRepository
from app.modules.product.schemas import ProductUpdate
from app.modules.product.service import ProductService
from app.shared.exceptions import (
    BusinessRuleException,
    ConflictException,
    NotFoundException,
)


async def test_create_product_normalizes_and_persists_valid_product() -> None:
    repository = AsyncMock(spec=ProductRepository)
    service = ProductService(repository)
    category = Category(id=uuid4(), nome="Eletronicos", slug="eletronicos")
    product = Product(
        categoria_id=category.id,
        nome="  Teclado mecanico  ",
        descricao=None,
        sku="  tec-mec-001  ",
        preco=Decimal("299.90"),
    )
    repository.get_category_by_id.return_value = category
    repository.get_by_sku.return_value = None
    repository.get_by_slug.return_value = None
    repository.add.return_value = product

    result = await service.create_product(product)

    assert result is product
    assert product.nome == "Teclado mecanico"
    assert product.sku == "TEC-MEC-001"
    assert product.slug == "teclado-mecanico"
    repository.get_category_by_id.assert_awaited_once_with(category.id)
    repository.get_by_sku.assert_awaited_once_with("TEC-MEC-001")
    repository.get_by_slug.assert_awaited_once_with("teclado-mecanico")
    repository.add.assert_awaited_once_with(product)


async def test_create_product_rejects_duplicate_sku() -> None:
    repository = AsyncMock(spec=ProductRepository)
    service = ProductService(repository)
    category_id = uuid4()
    product = Product(
        categoria_id=category_id,
        nome="Teclado mecanico",
        descricao=None,
        sku="TEC-MEC-001",
        preco=Decimal("299.90"),
    )
    repository.get_category_by_id.return_value = Category(
        id=category_id,
        nome="Eletronicos",
        slug="eletronicos",
    )
    repository.get_by_sku.return_value = Product(
        id=uuid4(),
        categoria_id=category_id,
        nome="Outro teclado",
        slug="outro-teclado",
        descricao=None,
        sku=product.sku,
        preco=Decimal("199.90"),
    )

    with pytest.raises(ConflictException) as exc_info:
        await service.create_product(product)

    assert exc_info.value.code == "SKU_ALREADY_EXISTS"
    repository.add.assert_not_awaited()


async def test_create_product_rejects_non_positive_price() -> None:
    repository = AsyncMock(spec=ProductRepository)
    service = ProductService(repository)
    product = Product(
        categoria_id=uuid4(),
        nome="Teclado mecanico",
        descricao=None,
        sku="TEC-MEC-001",
        preco=Decimal("0"),
    )

    with pytest.raises(BusinessRuleException) as exc_info:
        await service.create_product(product)

    assert exc_info.value.code == "INVALID_PRODUCT_PRICE"
    repository.get_category_by_id.assert_not_awaited()
    repository.get_by_sku.assert_not_awaited()
    repository.add.assert_not_awaited()


async def test_create_product_rejects_missing_category() -> None:
    repository = AsyncMock(spec=ProductRepository)
    service = ProductService(repository)
    category_id = uuid4()
    product = Product(
        categoria_id=category_id,
        nome="Teclado mecanico",
        descricao=None,
        sku="TEC-MEC-001",
        preco=Decimal("299.90"),
    )
    repository.get_category_by_id.return_value = None

    with pytest.raises(NotFoundException) as exc_info:
        await service.create_product(product)

    assert exc_info.value.code == "CATEGORY_NOT_FOUND"
    assert exc_info.value.details == {"category_id": str(category_id)}
    repository.get_by_sku.assert_not_awaited()
    repository.add.assert_not_awaited()


async def test_get_product_raises_not_found_for_missing_product() -> None:
    repository = AsyncMock(spec=ProductRepository)
    service = ProductService(repository)
    product_id = uuid4()
    repository.get_by_id.return_value = None

    with pytest.raises(NotFoundException) as exc_info:
        await service.get_product(product_id)

    assert exc_info.value.code == "PRODUCT_NOT_FOUND"
    assert exc_info.value.details == {"product_id": str(product_id)}


async def test_update_product_applies_partial_changes() -> None:
    repository = AsyncMock(spec=ProductRepository)
    service = ProductService(repository)
    product = Product(
        id=uuid4(),
        categoria_id=uuid4(),
        nome="Teclado mecanico",
        slug="teclado-mecanico",
        descricao="Descricao antiga",
        sku="TEC-MEC-001",
        preco=Decimal("299.90"),
        ativo=True,
    )
    schema = ProductUpdate(
        nome="  Teclado atualizado  ",
        descricao="   ",
        sku="tec-mec-002",
        preco=Decimal("349.90"),
    )
    repository.get_by_id.return_value = product
    repository.get_by_sku.return_value = None
    repository.update.return_value = product

    result = await service.update_product(product.id, schema)

    assert result is product
    assert product.nome == "Teclado atualizado"
    assert product.slug == "teclado-mecanico"
    assert product.descricao is None
    assert product.sku == "TEC-MEC-002"
    assert product.preco == Decimal("349.90")
    repository.get_by_sku.assert_awaited_once_with("TEC-MEC-002")
    repository.update.assert_awaited_once_with(product)


async def test_create_product_adds_suffix_to_duplicate_slug() -> None:
    repository = AsyncMock(spec=ProductRepository)
    service = ProductService(repository)
    category = Category(id=uuid4(), nome="Eletronicos", slug="eletronicos")
    product = Product(
        categoria_id=category.id,
        nome="Cafeteira Eletrica",
        descricao=None,
        sku="CAF-002",
        preco=Decimal("199.90"),
    )
    existing_product = Product(
        id=uuid4(),
        categoria_id=category.id,
        nome="Cafeteira Eletrica",
        slug="cafeteira-eletrica",
        descricao=None,
        sku="CAF-001",
        preco=Decimal("149.90"),
    )
    repository.get_category_by_id.return_value = category
    repository.get_by_sku.return_value = None
    repository.get_by_slug.side_effect = [existing_product, None]
    repository.add.return_value = product

    result = await service.create_product(product)

    assert result.slug == "cafeteira-eletrica-2"
    assert repository.get_by_slug.await_count == 2
