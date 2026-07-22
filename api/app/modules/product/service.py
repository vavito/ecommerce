from decimal import Decimal
from uuid import UUID

from app.shared.exceptions import (
    BusinessRuleException,
    ConflictException,
    NotFoundException,
)

from .models import Product
from .repository import ProductRepository
from .schemas import ProductUpdate


class ProductService:
    def __init__(self, repository: ProductRepository) -> None:
        self.repository = repository

    @staticmethod
    def _normalize_sku(sku: str) -> str:
        normalized_sku = sku.strip().upper()

        if not normalized_sku:
            raise BusinessRuleException(
                code="INVALID_PRODUCT_SKU",
                message="SKU do produto nao pode ser vazio.",
            )

        return normalized_sku

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized_name = name.strip()

        if not normalized_name:
            raise BusinessRuleException(
                code="INVALID_PRODUCT_NAME",
                message="Nome do produto nao pode ser vazio.",
            )

        return normalized_name

    @staticmethod
    def _validate_price(price: Decimal) -> None:
        if price <= 0:
            raise BusinessRuleException(
                code="INVALID_PRODUCT_PRICE",
                message="Preco do produto deve ser maior que zero.",
            )

    async def _ensure_sku_is_available(
        self,
        sku: str,
        *,
        current_product_id: UUID | None = None,
    ) -> None:
        existing_product = await self.repository.get_by_sku(sku)

        if existing_product is not None and existing_product.id != current_product_id:
            raise ConflictException(
                code="SKU_ALREADY_EXISTS",
                message="SKU ja cadastrado.",
            )

    async def _ensure_category_exists(self, category_id: UUID) -> None:
        category = await self.repository.get_category_by_id(category_id)

        if category is None:
            raise NotFoundException(
                code="CATEGORY_NOT_FOUND",
                message="Categoria nao encontrada.",
                details={"category_id": str(category_id)},
            )

    async def get_product(self, product_id: UUID) -> Product:
        product = await self.repository.get_by_id(product_id)

        if product is None:
            raise NotFoundException(
                code="PRODUCT_NOT_FOUND",
                message="Produto nao encontrado.",
                details={"product_id": str(product_id)},
            )

        return product

    async def create_product(self, product: Product) -> Product:
        product.nome = self._normalize_name(product.nome)
        product.sku = self._normalize_sku(product.sku)
        self._validate_price(product.preco)

        await self._ensure_category_exists(product.categoria_id)
        await self._ensure_sku_is_available(product.sku)

        return await self.repository.add(product)

    async def update_product(
        self,
        product_id: UUID,
        schema: ProductUpdate,
    ) -> Product:
        product = await self.get_product(product_id)
        updates = schema.model_dump(exclude_unset=True)

        for field, value in updates.items():
            if value is None and field != "descricao":
                raise BusinessRuleException(
                    code="INVALID_PRODUCT_UPDATE",
                    message=f"Campo {field} nao pode ser nulo.",
                )

        if "nome" in updates:
            updates["nome"] = self._normalize_name(updates["nome"])

        if "sku" in updates:
            normalized_sku = self._normalize_sku(updates["sku"])

            if normalized_sku != product.sku:
                await self._ensure_sku_is_available(
                    normalized_sku,
                    current_product_id=product.id,
                )

            updates["sku"] = normalized_sku

        if "preco" in updates:
            self._validate_price(updates["preco"])

        if (
            "categoria_id" in updates
            and updates["categoria_id"] != product.categoria_id
        ):
            await self._ensure_category_exists(updates["categoria_id"])

        if isinstance(updates.get("descricao"), str):
            updates["descricao"] = updates["descricao"].strip() or None

        for field, value in updates.items():
            setattr(product, field, value)

        return await self.repository.update(product)

    async def list_products(
        self,
        *,
        nome: str | None = None,
        categoria_id: UUID | None = None,
        ativo: bool | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Product], int]:
        return await self.repository.list(
            nome=nome,
            categoria_id=categoria_id,
            ativo=ativo,
            offset=offset,
            limit=limit,
        )
