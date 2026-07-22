import asyncio
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.modules.product.models import Category, Product


@dataclass(frozen=True, slots=True)
class CategorySeed:
    nome: str
    slug: str


@dataclass(frozen=True, slots=True)
class ProductSeed:
    categoria_slug: str
    nome: str
    descricao: str
    sku: str
    preco: Decimal


CATEGORY_SEEDS = (
    CategorySeed(nome="Eletronicos", slug="eletronicos"),
    CategorySeed(nome="Informatica", slug="informatica"),
    CategorySeed(nome="Livros", slug="livros"),
)

PRODUCT_SEEDS = (
    ProductSeed(
        categoria_slug="eletronicos",
        nome="Fone de ouvido Bluetooth",
        descricao="Fone sem fio com estojo de carregamento.",
        sku="FONE-BT-001",
        preco=Decimal("199.90"),
    ),
    ProductSeed(
        categoria_slug="eletronicos",
        nome="Monitor ultrawide",
        descricao="Monitor ultrawide de 34 polegadas.",
        sku="MON-UW-001",
        preco=Decimal("2499.90"),
    ),
    ProductSeed(
        categoria_slug="informatica",
        nome="Teclado mecanico",
        descricao="Teclado mecanico com iluminacao.",
        sku="TEC-MEC-001",
        preco=Decimal("299.90"),
    ),
    ProductSeed(
        categoria_slug="informatica",
        nome="Mouse sem fio",
        descricao="Mouse ergonomico com conexao sem fio.",
        sku="MOUSE-SF-001",
        preco=Decimal("149.90"),
    ),
    ProductSeed(
        categoria_slug="livros",
        nome="Arquitetura de software",
        descricao="Livro introdutorio sobre arquitetura de software.",
        sku="LIV-ARQ-001",
        preco=Decimal("89.90"),
    ),
    ProductSeed(
        categoria_slug="livros",
        nome="Python para APIs",
        descricao="Livro pratico sobre desenvolvimento de APIs com Python.",
        sku="LIV-PYT-001",
        preco=Decimal("79.90"),
    ),
)


async def get_or_create_category(
    session: AsyncSession,
    seed: CategorySeed,
) -> tuple[Category, bool]:
    category = await session.scalar(select(Category).where(Category.slug == seed.slug))

    if category is not None:
        return category, False

    category = Category(
        nome=seed.nome,
        slug=seed.slug,
        ativo=True,
    )
    session.add(category)
    await session.flush()

    return category, True


async def create_product_if_missing(
    session: AsyncSession,
    category: Category,
    seed: ProductSeed,
) -> bool:
    product = await session.scalar(select(Product).where(Product.sku == seed.sku))

    if product is not None:
        return False

    session.add(
        Product(
            categoria_id=category.id,
            nome=seed.nome,
            descricao=seed.descricao,
            sku=seed.sku,
            preco=seed.preco,
            ativo=True,
        )
    )

    return True


async def seed_database() -> tuple[int, int]:
    async with async_session_maker() as session:
        try:
            categories_by_slug: dict[str, Category] = {}
            created_categories = 0
            created_products = 0

            for category_seed in CATEGORY_SEEDS:
                category, created = await get_or_create_category(
                    session,
                    category_seed,
                )
                categories_by_slug[category.slug] = category
                created_categories += int(created)

            for product_seed in PRODUCT_SEEDS:
                created = await create_product_if_missing(
                    session,
                    categories_by_slug[product_seed.categoria_slug],
                    product_seed,
                )
                created_products += int(created)

            await session.commit()

            return created_categories, created_products
        except Exception:
            await session.rollback()
            raise


async def main() -> None:
    created_categories, created_products = await seed_database()
    print(
        "Seed concluido: "
        f"{created_categories} categorias e {created_products} produtos criados."
    )


if __name__ == "__main__":
    asyncio.run(main())
