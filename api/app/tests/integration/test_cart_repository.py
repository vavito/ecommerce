from decimal import Decimal
from uuid import uuid4

from app.core.database import async_session_maker
from app.modules.cart.enums import CartStatus
from app.modules.cart.models import Cart, CartItem
from app.modules.cart.repository import CartRepository
from app.modules.product.models import Category, Product
from app.modules.user.models import User


async def test_cart_repository_finds_open_cart_by_user() -> None:
    unique_value = uuid4().hex

    async with async_session_maker() as session:
        try:
            user = User(
                nome="Joao",
                email=f"joao-{unique_value}@example.com",
                cpf=unique_value[:11],
                senha_hash="hash",
            )
            session.add(user)
            await session.flush()

            repository = CartRepository(session)
            closed_cart = await repository.add(
                Cart(
                    usuario_id=user.id,
                    status=CartStatus.CLOSED,
                )
            )
            open_cart = await repository.add(
                Cart(
                    usuario_id=user.id,
                    status=CartStatus.OPEN,
                )
            )

            found_cart = await repository.get_open_by_user_id(user.id)

            assert found_cart is open_cart
            assert found_cart is not closed_cart
            assert found_cart.status is CartStatus.OPEN
            assert found_cart.itens == []
        finally:
            await session.rollback()


async def test_cart_repository_persists_updates_and_deletes_items() -> None:
    unique_value = uuid4().hex

    async with async_session_maker() as session:
        try:
            user = User(
                nome="Maria",
                email=f"maria-{unique_value}@example.com",
                cpf=unique_value[:11],
                senha_hash="hash",
            )
            category = Category(
                nome="Informatica",
                slug=f"informatica-cart-{unique_value}",
                ativo=True,
            )
            session.add_all([user, category])
            await session.flush()

            product = Product(
                categoria_id=category.id,
                nome="Mouse sem fio",
                slug=f"mouse-cart-{unique_value}",
                descricao=None,
                sku=f"MOUSE-CART-{unique_value}",
                preco=Decimal("149.90"),
                ativo=True,
            )
            session.add(product)
            await session.flush()

            repository = CartRepository(session)
            cart = await repository.add(
                Cart(
                    usuario_id=user.id,
                    status=CartStatus.OPEN,
                )
            )
            item = await repository.add_item(
                CartItem(
                    carrinho_id=cart.id,
                    produto_id=product.id,
                    quantidade=1,
                    preco_unitario_atual=product.preco,
                )
            )

            item_by_id = await repository.get_item_by_id(item.id)
            item_by_product = await repository.get_item_by_product_id(
                cart.id,
                product.id,
            )

            item.quantidade = 3
            updated_item = await repository.update_item(item)

            assert item_by_id is item
            assert item_by_product is item
            assert updated_item.quantidade == 3

            await repository.delete_item(item)

            assert await repository.get_item_by_id(item.id) is None
        finally:
            await session.rollback()


async def test_cart_repository_returns_none_when_cart_and_item_do_not_exist() -> None:
    async with async_session_maker() as session:
        repository = CartRepository(session)

        assert await repository.get_open_by_user_id(uuid4()) is None
        assert await repository.get_item_by_id(uuid4()) is None
        assert await repository.get_item_by_product_id(uuid4(), uuid4()) is None
